# 本地小智服务增量

这里保存本项目相对于上游 `xiaozhi-esp32-server` 的关键定制文件和 Windows 启停脚本，不重复提交完整上游仓库、模型、运行日志和本地密钥。

主要增量：

- WindowsSpeech 中文语音识别
- Windows SAPI 本地语音合成
- 开机三学段选择与家长端状态同步
- MQTT/UDP 主动播报服务启动链路
- 自动检测当前 WLAN IP

完整部署说明见 [LOCAL_DEPLOYMENT.md](LOCAL_DEPLOYMENT.md)。脚本中的 Python、Node 和上游源码路径需按实际电脑调整。
