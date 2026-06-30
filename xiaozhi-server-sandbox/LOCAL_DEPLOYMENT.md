# Local Parallel Deployment

- Upstream: `https://github.com/xinnan-tech/xiaozhi-esp32-server`
- Source archive: `xiaozhi-server-complete.zip`, downloaded and ZIP-validated 2026-06-29.
- Complete source: `D:\小智ai\xiaozhi-server-sandbox\source-complete\xiaozhi-esp32-server-main`
- Deployment directory: `D:\小智ai\xiaozhi-server-sandbox\deployment`
- Parent console port `8000` remains reserved and unchanged.
- Self-hosted console: `http://127.0.0.1:18002`
- Self-hosted WebSocket: `ws://127.0.0.1:18000/xiaozhi/v1/`
- Self-hosted HTTP/OTA base port: `18003`
- Official XiaoZhi console, MCP endpoint, and existing firmware are not modified.
- Do not copy `.env`, database files, or service secrets into public deliverables.
- Docker deployment is deferred because Windows currently has no paging file and
  Docker Desktop exits while launching its backend processes.
- The first working path uses the upstream-supported Python source deployment on
  ports `18000` and `18003`.
- Active reminder API: `http://127.0.0.1:18007/study-alert`.
- Start the parent console with active speech enabled by running
  `START_PARENT_ACTIVE.ps1`. It targets device `90:70:69:0e:a4:ac`.
- If the local device is offline, reminders stay pending in the existing MCP
  queue, so the official-console fallback remains available.

## Verified device deployment

- Device MAC: `90:70:69:0e:a4:ac`
- Chip: ESP32-S3, 16 MB flash, 8 MB PSRAM
- Board: `otto-robot`
- Active-speech firmware:
  `xiaozhi-esp32/releases/v2.2.6_otto-robot-local-active.zip`
- Original 16 MB flash backup:
  `xiaozhi-esp32/releases/device-backup-9070690ea4ac/full-flash-original-20260629.bin`
- `START_SOURCE.ps1` and `START_MQTT_GATEWAY.ps1` now detect the current WLAN
  IPv4 address automatically.
- Keep the computer on a stable LAN address for demonstrations. The device's
  current firmware and MQTT settings target `10.143.97.5`; rebuild or update
  the OTA setting after moving to a different network.

## Current product entry points

- Parent console: `http://127.0.0.1:8000/v2`
- Local agent operations center: `http://127.0.0.1:8000/local-agent`
- Safe status API: `http://127.0.0.1:8000/local-agent/status`
- Start all local services: `START_ALL.ps1`

The local agent page is read-only. It exposes device connectivity, the current
study stage, the five service ports, active-speech status, recent reminder
results, and a current-IP versus firmware-target-IP warning. It never exposes
MCP tokens, model keys, MQTT credentials, or other secrets.

## USB and network behavior

USB is not required during normal operation. It is used for flashing, serial
diagnostics, or temporary power only. After flashing, the robot needs separate
power and must share a mutually reachable LAN with the computer.

The computer currently receives its WLAN address through DHCP. A reconnect,
lease renewal, network switch, or hotspot restart can change that address.
Because the active firmware points to `http://10.143.97.5:18003/a`, an address
change can cause the device to report that version checking failed. Use a DHCP
reservation or a stable hotspot for demonstrations. The detailed Chinese guide
is available at `docs/USB断开与IP变化说明.md`.
