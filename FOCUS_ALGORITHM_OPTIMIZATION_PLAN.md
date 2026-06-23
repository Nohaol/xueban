# 专注度识别算法严谨优化思路

本文档用于指导 `focus_lab` 后续算法优化。目标不是把阈值调得“看起来更灵”，而是建立一套可验证、可复现、可迁移到后端的专注度识别流程。

当前实现位于 `focus_lab/focus_features.py`，核心流程是：

```text
Face Landmarker landmarks
-> compute_features()
-> compute_score()
-> FocusAnalyzer.update()
-> status / score / presence
```

当前问题主要来自三点：

1. 单帧特征权重过高，转头、眨眼、低头会被瞬时放大。
2. 缺少个人校准，不同摄像头角度和不同坐姿会导致 yaw、pitch、eyeOpenRatio 阈值不稳定。
3. `focused / distracted / away` 直接由扣分公式映射，缺少状态机和置信度，容易抖动。

## 1. 优化目标

优化后，算法应该满足以下标准：

1. 离开座位时稳定返回 `away`，不是异常。
2. 正常看屏幕、低头写字都可以被识别为有效学习状态。
3. 短暂转头、眨眼、低头不立刻判为分心。
4. 持续看向侧边、频繁大幅移动、长时间闭眼才降低状态。
5. 每一次判断都有可解释字段，例如 `reasonCodes`、`confidence`、`subScores`。
6. 同一段视频反复跑，输出结果一致，方便调参和回归测试。

建议最终返回结构：

```json
{
  "status": "focused",
  "score": 82.4,
  "confidence": 0.86,
  "presence": true,
  "activity": "screen_or_writing",
  "reasonCodes": ["face_visible", "head_stable", "eyes_open"],
  "subScores": {
    "presence": 1.0,
    "headOrientation": 0.82,
    "eyeState": 0.9,
    "motionStability": 0.76,
    "taskPosture": 0.8
  },
  "features": {}
}
```

## 2. 第一层：把原始特征做准

### 2.1 使用 Face Landmarker 的变换矩阵优先估计头姿

当前 `estimate_head_pose()` 使用 `solvePnP` 和手写 3D 模型估计 yaw/pitch/roll。这种方式能跑，但精度强依赖 3D 模型假设和摄像头角度。

MediaPipe Face Landmarker 已经可以输出 `facial_transformation_matrixes`。下一步应优先从该矩阵解算头部姿态，`solvePnP` 只作为 fallback。

执行建议：

1. 在 `landmark_debug.py` 中打印 `result.facial_transformation_matrixes` 是否存在。
2. 新增 `estimate_head_pose_from_matrix(matrix)`。
3. 对同一段视频同时输出 `matrixYaw/matrixPitch` 和 `pnpYaw/pnpPitch`。
4. 用人工观察选择更稳定的一组。

验收标准：

- 正对摄像头时 yaw 接近个人基线，而不是必须接近 0。
- 左右转头时 yaw 单调变化。
- 低头写字时 pitch 变化明显，但不会影响 yaw 稳定性。

### 2.2 眼睛开合改为双眼分别计算

当前 `eyeOpenRatio` 是左右眼平均值。戴眼镜、侧脸、光线差时，单眼可能异常，平均值会误导判断。

建议输出：

```json
{
  "leftEyeOpenRatio": 0.28,
  "rightEyeOpenRatio": 0.31,
  "eyeOpenRatio": 0.295,
  "eyeReliable": true
}
```

判断闭眼时不要只看绝对值，应结合个人基线：

```text
eye_closed = current_eye_ratio < calibrated_eye_open_ratio * 0.55
```

验收标准：

- 正常眨眼不会触发 `distracted`。
- 连续闭眼超过 1-1.5 秒才触发疲劳或不专注原因。
- 一只眼被遮挡时 `eyeReliable=false`，眼部特征降权。

### 2.3 增加脸框和关键点质量指标

每帧先判断这帧是否可靠，再决定是否用于评分。

建议增加字段：

```json
{
  "faceBoxArea": 0.18,
  "faceCenterX": 0.51,
  "faceCenterY": 0.44,
  "landmarkQuality": 0.92,
  "frameReliable": true
}
```

质量规则：

- 脸太小：`faceBoxArea < 0.03`，降低置信度。
- 脸太靠边：`faceCenterX < 0.15` 或 `> 0.85`，降低置信度。
- landmarks 跳变过大：降低当前帧权重。

这一步可以减少“检测到了脸，但其实特征点很差”的误判。

## 3. 第二层：做个人和摄像头校准

专注度识别不能完全使用固定阈值。摄像头放在屏幕上方、侧边、桌面低角度时，正常学习姿态的 yaw/pitch 基线完全不同。

### 3.1 增加 10 秒校准流程

新增 `focus_lab/calibrate.py`，采集三种状态：

1. `screen`：正对屏幕 5 秒。
2. `writing`：低头写字 5 秒。
3. `away`：离开画面 3 秒。

生成：

```text
focus_lab/config/calibration.json
```

建议结构：

```json
{
  "screen": {
    "yawMedian": 3.2,
    "pitchMedian": -4.5,
    "eyeOpenMedian": 0.29,
    "faceBoxAreaMedian": 0.16
  },
  "writing": {
    "yawMedian": 2.8,
    "pitchMedian": -18.0,
    "eyeOpenMedian": 0.24
  },
  "thresholds": {
    "yawSoftDelta": 15,
    "yawHardDelta": 25,
    "pitchWritingDelta": 25,
    "eyeClosedRatio": 0.55
  }
}
```

### 3.2 所有阈值改成相对基线

不要再判断：

```text
abs(yaw) > 20
```

改成：

```text
abs(yaw - calibrated_screen_yaw) > yawSoftDelta
```

低头写字也不要直接因为 pitch 大扣分。应判断它是否接近 `writingPitch` 区间：

```text
if pitch near writing_baseline and yaw stable:
    activity = "writing"
    do not apply heavy pitch penalty
```

验收标准：

- 改变摄像头角度后，重新校准即可恢复合理判断。
- 低头写字能长期保持 `focused` 或 `uncertain`，不应长期 `distracted`。

## 4. 第三层：从扣分公式升级为子评分

当前 `score = 100 - penalties` 可解释，但不够稳定。建议改成多个 `0-1` 子评分加权。

建议子评分：

```text
presenceScore        是否稳定有人
headOrientationScore 是否看向学习区域
eyeStateScore        是否睁眼/非疲劳
motionStabilityScore 是否动作稳定
taskPostureScore     是否符合屏幕学习或低头写字姿态
```

建议第一版权重：

```text
score =
  0.30 * presenceScore +
  0.25 * headOrientationScore +
  0.15 * eyeStateScore +
  0.15 * motionStabilityScore +
  0.15 * taskPostureScore
```

再乘以 100。

关键点：

- `presenceScore` 不等于单帧是否有人，要看最近 2-3 秒。
- `headOrientationScore` 看 yaw 相对基线偏差。
- `taskPostureScore` 同时接受 `screen` 和 `writing` 两类学习姿态。
- `eyeStateScore` 只在眼部可靠时生效，不可靠时降低权重或用默认中性值。

验收标准：

- CSV 中能看到每个子评分。
- 状态错误时可以明确知道是哪一项拉低了分数。

## 5. 第四层：增加状态机，减少抖动

不要让每一帧直接决定最终状态。建议引入状态机：

```text
focused
uncertain
distracted
away
fatigue
```

状态转换使用持续时间，而不是单帧阈值。

建议规则：

```text
focused -> uncertain:
  score < 70 持续 1.0 秒

uncertain -> distracted:
  score < 50 持续 2.0 秒

distracted -> focused:
  score > 78 持续 2.0 秒

any -> away:
  recentFaceRatio < 0.2 持续 1.0 秒

away -> uncertain:
  检测到人脸持续 1.0 秒

any -> fatigue:
  eyesClosed 持续 1.5 秒，且 presence=true
```

这比 `score >= 75` 直接映射更可靠。

输出中增加：

```json
{
  "statusDurationMs": 3200,
  "pendingStatus": "distracted",
  "pendingDurationMs": 800
}
```

验收标准：

- 快速转头 0.5 秒不会立刻跳 `distracted`。
- 离开座位 1 秒左右进入 `away`。
- 回到座位后先进入 `uncertain`，稳定后再回到 `focused`。

## 6. 第五层：建立样本集和量化评估

算法是否准确，不能只靠实时看窗口。必须录制固定样本，反复回放。

建议样本目录：

```text
focus_lab/data/samples/
  screen_01.avi
  writing_01.avi
  turn_left_01.avi
  away_01.avi
  phone_distraction_01.avi
  low_light_01.avi
  glasses_01.avi
```

配套标注文件：

```text
focus_lab/data/labels.csv
```

格式：

```csv
video,start_ms,end_ms,label
screen_01.avi,0,30000,focused
writing_01.avi,0,30000,focused
turn_left_01.avi,3000,9000,distracted
away_01.avi,5000,20000,away
```

新增评估脚本：

```text
focus_lab/evaluate.py
```

输出指标：

```text
overall_accuracy
away_precision / away_recall
focused_precision / focused_recall
distracted_precision / distracted_recall
state_switch_count
average_detection_delay_ms
```

验收标准：

- `away_recall >= 0.95`
- `focused_recall >= 0.85`
- `writing` 场景误判为 `distracted` 的比例 `< 10%`
- 每分钟状态切换次数不过高，例如 `< 8`

## 7. 第六层：逐步加入轻量模型，而不是一开始训练大模型

当样本 CSV 足够后，可以从规则系统升级为轻量分类器。

第一阶段仍然保留规则系统，只训练一个小模型辅助判断：

输入特征：

```text
yaw_delta
pitch_delta_screen
pitch_delta_writing
eye_open_ratio_norm
face_ratio_2s
motion_std_2s
face_center_delta
landmark_quality
```

候选模型：

- Logistic Regression
- RandomForest
- XGBoost 或 LightGBM

建议先用 Logistic Regression 或 RandomForest，原因是样本少、可解释、调试成本低。

输出：

```json
{
  "modelProbs": {
    "focused": 0.78,
    "distracted": 0.12,
    "away": 0.10
  }
}
```

上线策略：

1. 先只记录模型输出，不参与最终判断。
2. 与规则结果对比 1-2 天。
3. 确认优于规则后，再用模型概率参与 `confidence` 或 `status`。

## 8. 推荐执行顺序

不要一次性重写。按下面顺序最稳：

1. 扩展 `replay_video.py` CSV 字段，输出所有原始特征和当前状态。
2. 新增 `calibrate.py`，生成个人基线 `calibration.json`。
3. 把 yaw/pitch/eyeOpen 阈值改成相对基线。
4. 增加 `subScores`，把扣分公式改成加权子评分。
5. 增加 `reasonCodes` 和 `confidence`。
6. 增加状态机，替代单帧分数直接映射。
7. 建立 `labels.csv` 和 `evaluate.py`，用数据判断改动是否变好。
8. 在规则系统稳定后，再考虑轻量分类器。

## 9. 优先修正的现有实现点

当前代码中最值得先改的是：

1. `compute_features()` 没有真正使用 `FocusAnalyzer.nose_history` 计算稳定性，当前 `motionStability` 多数情况下是默认值 `0.5`。
2. `FocusAnalyzer.update()` 对 `away` 也做分数平滑，所以无人脸第一帧可能返回 `status=away` 但 `score` 仍不是 0。`away` 应绕过平滑，直接返回 0。
3. `reason` 现在只有 `face_detected / face_not_detected`，不足以解释为什么分心。应改成 `reasonCodes`。
4. 低头写字没有单独建模，pitch 容易被误用。应增加 `activity=writing` 的判断。
5. 头姿估计应优先验证 Face Landmarker transformation matrix，再决定是否继续使用 `solvePnP`。

建议先解决第 1 和第 2 点，因为它们会直接影响现有结果可信度。

## 10. 最小可执行里程碑

第一轮优化完成后，至少做到：

```text
python focus_lab/replay_video.py focus_lab/data/samples/writing_01.avi --csv focus_lab/outputs/writing_metrics.csv --no-show
python focus_lab/evaluate.py focus_lab/data/labels.csv focus_lab/outputs/
```

并能回答：

1. 低头写字被误判的比例是多少？
2. 离开座位多久后进入 `away`？
3. 每分钟状态切换多少次？
4. 哪个子评分最常导致 `distracted`？

只有能用这些问题验证，算法优化才算进入可控阶段。
