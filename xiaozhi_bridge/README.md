# 小智伴学 MCP 桥接

该桥接把电脑端持久化的学段状态和提醒队列暴露为五个 MCP 工具：

- `set_study_stage`
- `get_study_stage`
- `check_study_focus_and_remind_child`
- `mark_study_reminder_spoken`
- `inspect_study_reminder_queue`

## 启动

后端的 `/mcp/config`、`/mcp/start` 和 `/mcp/stop` 接口负责管理桥接进程。
接入点必须以 `wss://api.xiaozhi.me/mcp/` 开头。完整令牌只保存在本地运行
状态和子进程环境变量中，公开状态仅显示脱敏后的末四位。

默认使用工作区中的 `mcp-calculator-main/mcp_pipe.py`。如位置不同，可在创建
后端运行时对象时传入 `pipe_script`。桥接工具和后端通过
`backend/runtime/runtime_state.json` 与 `xiaozhi_reminders.json` 共享状态。

MCP 是由小智调用电脑端工具的通道，不是设备主动 TTS 推送通道。工具返回
`hasReminder=true` 时，小智朗读 `reminderText`，然后调用
`mark_study_reminder_spoken`；无提醒时不打扰学生。

每次 MCP 工具调用都会追加到
`backend/runtime/xiaozhi_mcp_calls.jsonl`。日志只记录学段安全字段和队列
状态摘要，不记录 MCP URL、token 或提醒正文。提醒必须先由检查工具领取为
`delivered`，之后才能确认成 `spoken` 或 `skipped`；重复确认终态是幂等操作。
