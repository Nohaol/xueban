# Focus Lab 调试运行指南

## 环境激活

打开 PowerShell，在项目根目录执行：

```powershell
.\.venv-focus\Scripts\Activate.ps1
```

看到前缀 `(.venv-focus)` 即激活成功。

---

## 一、摄像头探测

**目的：** 确认哪个摄像头编号可用。

```powershell
python focus_lab\camera_probe.py
```

**预期输出：**

```
camera 0: ok, 640x480
camera 1: unavailable
...
```

**如果全部 unavailable：**
1. 关掉微信、腾讯会议、Zoom 等可能占用摄像头的软件
2. Windows 设置 → 隐私 → 摄像头 → 允许桌面应用访问
3. 插 USB 摄像头再试

---

## 二、FaceMesh 特征点验证

**目的：** 确认 MediaPipe 能正常检测人脸并输出 478 个关键点。

```powershell
python focus_lab\landmark_debug.py
```

**窗口说明：**
- 绿色小点 = 478 个人脸关键点
- 浅绿色连线 = 面部轮廓、眼、眉、嘴
- 左上角显示当前帧检测到的人脸数量和关键点数
- 无人脸时显示红色 "No face detected"

**验证清单：**
- [ ] 画面窗口能正常弹出
- [ ] 面对摄像头时能看到关键点覆盖在脸上
- [ ] 控制台不断输出 `ts=... faces=1`（有脸）或 `faces=0`（无脸）
- [ ] 转头、低头、离开画面时检测状态能变化
- [ ] 按 `q` 能正常退出

**如果窗口没弹出：** 检查是否在远程桌面/SSH 环境，GUI 窗口需要物理显示器。

**如果检测不到人脸：**
- 确保光线充足，面部正对摄像头
- 检查 `focus_lab\models\face_landmarker.task` 文件是否存在且不是 0 字节

---

## 三、实时专注度监测

**目的：** 看到完整的专注度评分 + 特征值 + 状态分类。

```powershell
python focus_lab\run_realtime.py
```

**窗口布局：**
```
┌──────────────────────────┬──────────┐
│                          │ Status   │
│    摄像头画面             │ Score    │
│    + 人脸关键点           │ Presence │
│                          │ Yaw      │
│                          │ Pitch    │
│                          │ EyeOpen  │
│                          │ Gaze     │
│                          │ Stability│
│                          │ FaceRatio│
│                          │ FPS      │
└──────────────────────────┴──────────┘
```

**顶部色条：** 绿色=focused, 黄色=uncertain, 橙色=distracted, 红色=away

**快捷键：**

| 键 | 作用 |
|----|------|
| `q` | 退出 |
| `s` | 保存当前帧到 `outputs/frame_YYYYMMDD_HHMMSS.jpg` |
| `r` | 开始/停止录制，视频存到 `outputs/recording_YYYYMMDD_HHMMSS.avi` |
| `c` | 手动循环状态预览（不改变分析结果，只是 UI 测试） |

**验证清单：**
- [ ] 正对摄像头坐好 → Status 显示 `FOCUSED`，Score > 75
- [ ] 转头看向侧面 → Score 下降，Status 可能变 `UNCERTAIN` 或 `DISTRACTED`
- [ ] 站起来离开座位 → Status 变 `AWAY`，Score → 0
- [ ] 低头看书写字 → Score 不应降到 distracted（pitch 不扣重分）
- [ ] 短暂转头马上回正 → 不会立刻误报（有 2 秒滑窗平滑）

---

## 四、视频回放分析

**目的：** 用录制好的视频离线调试阈值，输出 CSV 数据。

先录制一段测试视频（用 `run_realtime.py` 按 `r`），然后：

```powershell
# 实时速度回放
python focus_lab\replay_video.py focus_lab\outputs\recording_20240528_120000.avi

# 快速回放（不限制帧率，尽快跑完）
python focus_lab\replay_video.py focus_lab\outputs\recording_20240528_120000.avi --fast 60

# 输出 CSV 方便分析
python focus_lab\replay_video.py focus_lab\outputs\recording_20240528_120000.avi --csv focus_lab\outputs\metrics.csv

# 无窗口静默跑（纯出 CSV）
python focus_lab\replay_video.py focus_lab\outputs\recording_20240528_120000.avi --csv focus_lab\outputs\metrics.csv --no-show
```

**CSV 字段：**

| 列 | 含义 |
|----|------|
| timestamp_ms | 模拟时间戳 (ms) |
| status | focused / uncertain / distracted / away |
| score | 0-100 专注度分数 |
| presence | True/False 是否有人 |
| headYaw | 头部水平偏转角度 |
| headPitch | 头部垂直俯仰角度 |
| eyeOpenRatio | 眼睛开合比例 |
| gazeScore | 视线代理分 0-1 |
| motionStability | 动作稳定性 0-1 |

---

## 五、API 服务

**目的：** 启动 HTTP/WebSocket 服务，模拟小程序后端。

```powershell
python -m uvicorn focus_lab.serve_api:app --host 0.0.0.0 --port 8010
```

**测试端点：** 浏览器或另一个终端访问：

```powershell
# 健康检查
curl http://127.0.0.1:8010/health

# 当前状态
curl http://127.0.0.1:8010/state

# 截图
curl http://127.0.0.1:8010/snapshot.jpg -o test.jpg

# 视频流（浏览器直接打开）
# http://127.0.0.1:8010/video_feed
```

**`/state` 返回示例（有人）：**

```json
{
  "ok": true,
  "mode": "camera",
  "status": "focused",
  "score": 82.5,
  "presence": true,
  "reason": "face_detected",
  "features": {
    "faceVisible": true,
    "headYaw": 4.2,
    "headPitch": -2.5,
    "eyeOpenRatio": 0.31,
    "gazeScore": 0.84,
    "motionStability": 0.76
  },
  "updatedAt": 1716930000000
}
```

**`/state` 返回示例（无人）：**

```json
{
  "ok": true,
  "mode": "camera",
  "status": "away",
  "score": 0,
  "presence": false,
  "reason": "face_not_detected",
  "features": {
    "faceVisible": false,
    "headYaw": null,
    "headPitch": null,
    "eyeOpenRatio": null,
    "gazeScore": 0,
    "motionStability": 0
  },
  "updatedAt": 1716930000000
}
```

**注意：** 无人脸时返回 200 且 status=away，不是 500 错误。这是设计行为。

---

## 六、调阈值指南

核心参数在 `focus_features.py` 中：

**状态判定（`compute_score` 函数）：**

```python
# 离座判定：最近 2 秒人脸比例 < 30%
if recent_face_ratio < 0.3:
    return ("away", 0.0, False)

# 分数 → 状态映射
score >= 75  → focused
score >= 50  → uncertain
score <  50  → distracted
```

**惩罚项（100 分扣分制）：**

```python
| 条件                        | 扣分 | 说明                    |
|----------------------------|------|------------------------|
| 人脸比例 < 70%             | -20  | 人脸断断续续            |
| yaw 绝对值 > 30°           | -25  | 头大幅转向              |
| yaw 绝对值 > 20°           | -10  | 头中度转向              |
| 持续大角度偏头 (每帧)       | -2   | 累积扣分                |
| 眼睛开合 < 0.15            | -15  | 基本闭眼                |
| 持续闭眼 (每帧)            | -3   | 累积扣分                |
| 动作稳定性 < 0.3           | -15  | 频繁大幅移动            |
| 动作稳定性 < 0.5           | -5   | 中等移动                |
```

**时间平滑（`FocusAnalyzer.update`）：**

```python
smoothed_score = 0.8 * previous_score + 0.2 * current_score
```

- Alpha = 0.2：越接近 1 响应越快，越接近 0 越平滑
- 窗口 = 2 秒 × 15 fps = 30 帧

**如果需要调整：** 修改 `focus_features.py` 中的数字，重新跑 `replay_video.py` 看同一段视频的分数变化。

---

## 七、常见问题

**Q: `ImportError: No module named 'mediapipe'`**

```powershell
.\.venv-focus\Scripts\Activate.ps1   # 确保激活了虚拟环境
python -m pip install -r focus_lab\requirements.txt
```

**Q: MediaPipe 报错 `Model file does not exist`**

检查 `focus_lab\models\face_landmarker.task` 是否存在。重新下载：

```powershell
python -c "import urllib.request; urllib.request.urlretrieve('https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task', r'focus_lab\models\face_landmarker.task')"
```

**Q: 摄像头打开失败**

```powershell
python focus_lab\camera_probe.py   # 先确认哪个 index 可用
```

然后修改对应脚本中 `cv2.VideoCapture(0, cv2.CAP_DSHOW)` 的编号。

**Q: 窗口卡住或黑屏**

按 `q` 退出重跑。如果反复出现，去掉 `cv2.CAP_DSHOW` 试试：
```python
cap = cv2.VideoCapture(0)  # 不指定后端
```
