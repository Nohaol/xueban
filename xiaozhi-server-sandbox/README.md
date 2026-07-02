# 本地小智服务

本目录已经包含可运行的 `xiaozhi-server` 核心源码、必要本地模型、项目定制文件和 Windows 启停脚本。

主要增量：

- WindowsSpeech 中文语音识别
- Windows SAPI 本地语音合成
- 开机三学段选择与家长端状态同步
- MQTT/UDP 主动播报服务启动链路
- 自动检测当前 WLAN IP

完整部署说明见 [LOCAL_DEPLOYMENT.md](LOCAL_DEPLOYMENT.md)。脚本中的 Python、Node 和上游源码路径需按实际电脑调整。

服务端入口位于：

```text
source-complete/xiaozhi-esp32-server-main/main/xiaozhi-server/app.py
```

该目录同时包含 `requirements.txt`、`core/`、`config/`、`models/` 和
`plugins_func/`。运行日志、缓存、临时音频、个人配置和密钥未上传。
