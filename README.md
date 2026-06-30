# 小智伴学（xueban）

小智伴学是一套面向家庭学习场景的桌面学伴机器人系统。摄像头在电脑端分析在座、视线、姿态和动作稳定度；当持续分心达到学段阈值时，本地服务会通过 MQTT 与 UDP/TTS 下行，让 ESP32 小智机器人无需按键即可主动开口提醒。

## 已实现能力

- 本地摄像头与 IP Webcam 视频源
- MediaPipe + OpenCV 专注度分析
- 家长端留言主动播报
- 摄像头分心事件自动播报
- 小学、初中、高中三学段策略
- 开机语音选择学段，仅在真正改变时播报确认
- WindowsSpeech 中文识别与按键自然对话
- DeepSeek + 轻量知识库问答
- MQTT 唤醒与 UDP/TTS 主动语音下行
- 本地智能体运行中心与 IP 地址诊断
- 131 项自动化测试

## 页面入口

启动后打开：

- 家长端：`http://127.0.0.1:8000/v2`
- 本地智能体运行中心：`http://127.0.0.1:8000/local-agent`
- 健康检查：`http://127.0.0.1:8000/health`
- 只读状态接口：`http://127.0.0.1:8000/local-agent/status`

## 目录

```text
backend/                    家长端、专注分析、提醒策略与状态接口
focus_lab/                  专注度算法实验与评估
knowledge_base/             三学段学习知识资料
xiaozhi_bridge/             MCP 提醒工具桥
xiaozhi-server-sandbox/     本地服务脚本与中文 ASR/TTS 增量
xiaozhi-esp32/              ESP32 主动播报相关固件增量
docs/defense_assets/        早期答辩素材
docs/defense_assets_20260630/ 最新 8 张答辩 PNG 与 SVG 源文件
tests/                      自动化测试
```

## 启动家长端

Python 3.10+：

```powershell
python -m pip install -r backend/requirements.txt
$env:XIAOZHI_ACTIVE_SPEECH_URL="http://127.0.0.1:18007/study-alert"
$env:XIAOZHI_ACTIVE_SPEECH_DEVICE_ID="90:70:69:0e:a4:ac"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

完整本地服务的启动方式见 [xiaozhi-server-sandbox/LOCAL_DEPLOYMENT.md](xiaozhi-server-sandbox/LOCAL_DEPLOYMENT.md)。

## USB 与网络

日常运行不需要 USB。机器人需独立供电，并与电脑连接同一可互相访问的局域网。电脑当前使用 DHCP，IP 变化后，固件仍访问旧地址就会出现“检查新版本失败”。

比赛演示推荐在路由器中为电脑设置 DHCP 地址保留，或始终使用同一个固定手机热点。详细说明见 [USB断开与IP变化说明](docs/USB断开与IP变化说明.md)。

## 测试

只运行本项目测试目录，避免 ESP-IDF 组件测试被一并收集：

```powershell
python -m pytest tests -q
```

当前结果：`131 passed`。

## 安全说明

仓库不包含 `.env`、DeepSeek API Key、MCP Token、MQTT 密钥、运行日志、模型、设备 Flash 备份或构建缓存。所有密钥只在本地运行时配置。
