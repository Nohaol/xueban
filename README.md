# xueban

`xueban` 是一个运行在电脑端的家长伴学工作台原型。它用 `FastAPI + OpenCV` 接入本机摄像头或手机 `IP Webcam`，在浏览器里提供实时学习画面、专注状态、事件记录、AI 建议和视频源管理。

当前仓库聚焦于产品代码：本地后端、浏览器控制台和必要的运行说明文档。

## What It Does

- 实时视频画面预览
- 本机摄像头和网络视频源切换
- 专注度、视线、坐姿、稳定性、在座状态分析
- 离座、分心、超时离座等事件记录
- 家长提醒入口和 DeepSeek 建议能力
- 多页面控制台：`Dashboard`、`Advice`、`Review`、`Devices`
- 小学、初中、高中三种学习模式与分层提醒策略
- 小智 MCP 提醒队列、语音切换工具和播报回执
- 单一分层知识库：语文、数学、英语与学习方法
- 一键重置：回到默认本机摄像头并清空当前会话状态

## Stack

- Backend: `FastAPI`, `uvicorn`
- Vision: `MediaPipe Face Landmarker`, `OpenCV`, `numpy`
- Frontend: static `HTML + CSS + JavaScript`
- AI: `DeepSeek` API

## Project Structure

```text
.
├─ backend/
│  ├─ main.py                  # FastAPI app entry
│  ├─ engine.py                # camera capture and focus analysis
│  ├─ study_modes.py           # three-stage learning policies
│  ├─ runtime_state.py         # cross-process stage state
│  ├─ reminder_policy.py       # reminder thresholds and cooldowns
│  ├─ xiaozhi_mcp_runtime.py   # MCP process lifecycle
│  ├─ schemas.py               # request/response models
│  ├─ deepseek_client.py       # DeepSeek integration
│  ├─ run_server.py            # local startup helper
│  ├─ requirements.txt
│  └─ static/
│     ├─ parent-console.html   # legacy console
│     ├─ parent-console-v2.html
│     ├─ parent-console-v2.css
│     └─ parent-console-v2.js
├─ xiaozhi_bridge/             # Xiaozhi MCP tool server
├─ knowledge_base/             # layered study knowledge base
├─ tests/                      # backend and frontend contracts
├─ DESIGN.md
├─ PLATFORM_USAGE.md
├─ docs/
│  ├─ backend-service.md
│  ├─ configuration/           # console role and acceptance checklist
│  └─ defense_assets/          # defense-ready PNG, SVG and CSV
└─ README.md
```

## Setup

Recommended Python version: `3.10+`

Create a virtual environment and install dependencies:

```powershell
cd D:\path\to\xueban
py -3.12 -m venv .venv-backend
.\.venv-backend\Scripts\python.exe -m pip install -r backend\requirements.txt
```

If you already manage Python dependencies elsewhere, you can install directly:

```powershell
py -3.12 -m pip install -r backend\requirements.txt
```

## Run Locally

Start the backend from the project root:

```powershell
.\.venv-backend\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Or use the helper script:

```powershell
.\.venv-backend\Scripts\python.exe backend\run_server.py
```

Open the app in your browser:

- V2 console: `http://127.0.0.1:8000/v2`
- Legacy console: `http://127.0.0.1:8000/`
- Health check: `http://127.0.0.1:8000/health`

## Video Sources

### Local camera

The default source is local camera `0`, exposed in the UI as `本机摄像头`.

### Android phone via IP Webcam

Typical addresses:

```text
http://192.168.x.x:8080/video
http://192.168.x.x:8080/shot.jpg
```

The phone and the computer must be on the same LAN, and the URL should already be reachable from the computer browser before adding it in the app.

## Refresh and Reset Behavior

The left navigation `Refresh` action is intentionally defined as a hard reset instead of a light frame refresh.

It will:

- switch back to `local-default`
- release the current capture handle
- clear current visual-session state
- clear the snapshot layer and request a fresh first frame
- reconnect the WebSocket status channel

This is designed to behave like “restart the local backend session from scratch” without requiring a full manual relaunch.

## Environment Variables

Common options:

```powershell
$env:FOCUS_FORCE_MOCK='0'
$env:FOCUS_CAMERA_SOURCE='0'
$env:FOCUS_LOCAL_PROBE_COUNT='2'
$env:FOCUS_SOURCE_RETRY_SECONDS='2.5'
$env:FOCUS_STREAM_OPEN_TIMEOUT_MS='1500'
$env:FOCUS_STREAM_READ_TIMEOUT_MS='900'
```

Meaning:

- `FOCUS_FORCE_MOCK`: force mock mode
- `FOCUS_CAMERA_SOURCE`: default local camera index
- `FOCUS_LOCAL_PROBE_COUNT`: how many local camera slots to expose
- `FOCUS_SOURCE_RETRY_SECONDS`: retry cooldown after source failure
- `FOCUS_STREAM_OPEN_TIMEOUT_MS`: network stream open timeout
- `FOCUS_STREAM_READ_TIMEOUT_MS`: network stream read timeout

## Three Study Modes

The runtime exposes one shared stage state for the parent console and MCP
process:

| Mode | Focus threshold | Persistent distraction | Cooldown |
| --- | ---: | ---: | ---: |
| Primary | 55 | 20 s | 180 s |
| Middle | 65 | 15 s | 120 s |
| High | 70 | 25 s | 240 s |

The stage can be changed from the parent console or through
`set_study_stage`. The robot confirms the selected mode by voice.

## Xiaozhi MCP Reminder Loop

The MCP bridge publishes five tools:

- `set_study_stage`
- `get_study_stage`
- `check_study_focus_and_remind_child`
- `mark_study_reminder_spoken`
- `inspect_study_reminder_queue`

The focus engine creates a reminder only after the stage-specific persistence,
cooldown, and rate-limit rules are satisfied. Xiaozhi leases the reminder,
speaks `reminderText`, and acknowledges it after playback.

Configure the endpoint only at runtime. Never commit the endpoint URL or token.
See [deployment and acceptance](docs/configuration/DEPLOYMENT_AND_ACCEPTANCE.md).

## Knowledge Base

The editable source and upload-ready document are stored in
[`knowledge_base/`](knowledge_base/). The document covers Chinese, mathematics,
English, study planning, focus reminders, and review methods for all three
stages.

## Defense Assets

Presentation-ready evidence is available in
[`docs/defense_assets/`](docs/defense_assets/):

- eight 1920x1080 PNG graphics
- editable SVG flowcharts
- a UTF-8 acceptance matrix CSV

These assets use the warm visual system from the project business-plan deck.

## Current Boundary

The MCP integration is tool-call driven. Camera analysis can enqueue reminders,
but guaranteed speech from a completely idle ESP32 device without a wake/button
event requires firmware-level push playback support and remains the next-stage
upgrade.

## DeepSeek Configuration

Create `.env` in the project root if you want AI suggestions:

```env
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_REASONING_MODEL=deepseek-v4-pro
DEEPSEEK_MIN_INTERVAL_SECONDS=120
DEEPSEEK_STREAM=false
DEEPSEEK_THINKING_TYPE=enabled
DEEPSEEK_REASONING_EFFORT=high
```

Do not commit `.env` to GitHub.

## Development Checks

Check frontend JavaScript:

```powershell
node --check backend\static\parent-console-v2.js
```

Check Python syntax:

```powershell
.\.venv-backend\Scripts\python.exe -m py_compile backend\main.py backend\engine.py backend\run_server.py
```

## Notes

- The V2 dashboard uses a snapshot-refresh strategy rather than a native streaming player.
- Network video sources can fail fast and retry with cooldown instead of freezing the whole session.
- The connection label in the top-right now distinguishes between stable local video and a reconnecting WebSocket status channel.
- Only delivery-ready visual assets are included. Raw PPT projects, local
  research folders, tokens, logs, runtime queues, camera images, and private
  integration material remain excluded.

## Ignore Before Publishing

Make sure these are not uploaded:

- `.env`
- `__pycache__/`
- `*.pyc`
- `.venv-backend/`
- `.venv-focus/`
- backend runtime logs such as `backend/*.log`
