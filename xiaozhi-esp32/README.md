# 小智 ESP32 固件增量

本目录保存主动播报和三学段语音选择相关的关键固件增量，不包含 ESP-IDF 工具链、构建缓存、固件压缩包或设备 Flash 备份。

`main/boards/otto-robot/config.local-active.json` 中的 IP 是本次实机验证地址。迁移网络后需要更新地址并重新构建，后续可改用 mDNS 或 UDP 服务发现。
