# Focus Lab — MediaPipe FaceMesh 专注度识别实验

独立于小程序项目的 MediaPipe 专注度分析实验目录。

## 快速开始

```powershell
# 激活虚拟环境
.\.venv-focus\Scripts\Activate.ps1

# 验证依赖
python -c "import cv2, mediapipe, numpy; print('ok')"

# 阶段 3: 扫描摄像头
python focus_lab\camera_probe.py

# 阶段 4: FaceMesh 最小验证
python focus_lab\landmark_debug.py

# 阶段 7: 实时专注度监测
python focus_lab\run_realtime.py

# 阶段 8: 回放视频分析
python focus_lab\replay_video.py data\samples\test.mp4 --csv outputs\metrics.csv

# 阶段 9: API 服务
python -m uvicorn focus_lab.serve_api:app --host 0.0.0.0 --port 8010
```

## 文件说明

| 文件 | 用途 |
|------|------|
| `camera_probe.py` | 扫描本机可用摄像头 |
| `landmark_debug.py` | FaceMesh 特征点最小验证 |
| `focus_features.py` | 专注度特征计算（纯算法，无 I/O） |
| `run_realtime.py` | 实时摄像头 + 调试 UI |
| `replay_video.py` | 视频文件离线回放，输出 CSV |
| `serve_api.py` | FastAPI 接口服务 |

## 实时调试快捷键

- `q` — 退出
- `s` — 保存当前帧到 `outputs/`
- `r` — 开始/停止录制
- `c` — 循环切换状态预览（测试 UI）

## API 端点 (serve_api.py)

- `GET /health`
- `GET /state` — 当前专注度状态 JSON
- `GET /snapshot.jpg` — 标注后的视频帧 JPEG
- `GET /video_feed` — MJPEG 视频流
- `WS /ws` — 每秒推送状态 JSON
