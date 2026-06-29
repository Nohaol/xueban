# Xiaozhi deployment and acceptance

## Local service

```powershell
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/v2`.

## MCP configuration

1. Copy the MCP endpoint from the Xiaozhi agent console.
2. Enter it in the parent console Devices page or call `POST /mcp/config`.
3. Start the bridge with `POST /mcp/start`.
4. Confirm that the console lists all five learning tools.

Do not write the full endpoint or token into source files, screenshots, logs,
issues, or commits.

## Agent configuration

- Role prompt: `xiaozhi-agent-role-prompt.txt`
- Long-term memory: off
- Knowledge base: `小智分层伴学知识库`
- Restart the device after saving the agent configuration.

## Acceptance evidence

- The device asks for primary, middle, or high mode in a new session.
- The selected mode is confirmed by voice and synchronized to the parent UI.
- The knowledge-base validation phrase is `星芽、知桥、远帆`.
- The local automated suite reports 95 passing tests.
- The MCP endpoint is online and exposes five custom learning tools.

## Capability boundary

The current MCP protocol is invoked during an active conversation/tool turn.
Guaranteed camera-triggered speech while an ESP32 device is fully idle requires
firmware or a supported push-TTS/audio channel and is intentionally tracked as
the next-stage upgrade.
