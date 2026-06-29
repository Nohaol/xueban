# 小智伴学三学段模式与知识库 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不刷写 ESP32 固件的前提下，为单个小智智能体增加小学、初中、高中语音模式、电脑端同步、分层提醒策略和一个可验证调用的统一知识库。

**Architecture:** 以 GitHub 仓库 `Nohaol/xueban` 的 V2 家长端为产品基线，在后端增加可持久化的学段状态和跨进程 MCP 工具，在视觉引擎与提醒策略中统一读取同一份学段配置。小智控制台使用一个智能体，通过角色提示词维护会话学段并调用 MCP 同步；一个知识库文档用明确的学段与学科标签支持检索。

**Tech Stack:** Python 3.10+、FastAPI、Pydantic、FastMCP、filelock、OpenCV/MediaPipe、HTML/CSS/JavaScript、pytest、DOCX。

---

## 文件结构

- Create: `xueban-master/backend/study_modes.py`：三学段定义、校验和提示策略。
- Create: `xueban-master/backend/runtime_state.py`：线程与跨进程安全的学段状态持久化。
- Create: `xueban-master/backend/reminder_policy.py`：按学段执行持续时间、阈值、冷却和频率控制。
- Create: `xueban-master/backend/xiaozhi_bridge.py`：提醒队列及学段同步操作。
- Create: `xueban-master/backend/xiaozhi_mcp_runtime.py`：MCP 桥接进程生命周期。
- Create: `xueban-master/xiaozhi_bridge/focus_reminder_mcp.py`：暴露给小智的 MCP 工具。
- Create: `xueban-master/xiaozhi_bridge/README.md`：接入与启动说明。
- Create: `xueban-master/tests/test_study_modes.py`。
- Create: `xueban-master/tests/test_runtime_state.py`。
- Create: `xueban-master/tests/test_reminder_policy.py`。
- Create: `xueban-master/tests/test_xiaozhi_bridge.py`。
- Modify: `xueban-master/backend/engine.py`：读取持久化学段并运行自动提醒。
- Modify: `xueban-master/backend/main.py`：设置、控制和 MCP 管理接口。
- Modify: `xueban-master/backend/schemas.py`：学段和 MCP 请求模型。
- Modify: `xueban-master/backend/requirements.txt`：增加 `filelock`、`fastmcp`、`websockets`、`pytest`。
- Modify: `xueban-master/backend/static/parent-console-v2.html`：三段式模式控件与同步状态。
- Modify: `xueban-master/backend/static/parent-console-v2.js`：统一读写后端学段，不再仅保存在浏览器。
- Modify: `xueban-master/backend/static/parent-console-v2.css`：模式控件和同步状态样式。
- Create: `xueban-master/knowledge_base/小智分层伴学知识库.md`：知识库可维护源文件。
- Create: `xueban-master/knowledge_base/小智分层伴学知识库.docx`：上传到小智平台的唯一文档。
- Create: `xueban-master/docs/xiaozhi-agent-role-prompt.txt`：控制台角色提示词。
- Create: `xueban-master/docs/xiaozhi-console-checklist.md`：控制台配置与验收记录。

### Task 1: 建立当前 GitHub 基线和测试入口

**Files:**
- Inspect: `xueban-master/README.md`
- Inspect: `xueban-master/backend/requirements.txt`
- Create: `xueban-master/tests/conftest.py`

- [ ] **Step 1: 对比本地和 GitHub master 的关键文件**

读取远端 `backend/main.py`、`backend/engine.py`、`backend/schemas.py` 和三个 V2 前端文件，逐个对比本地副本。保留本地独有资料，不覆盖与本任务无关的内容。

- [ ] **Step 2: 创建测试路径初始化**

```python
# xueban-master/tests/conftest.py
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
```

- [ ] **Step 3: 安装和检查依赖**

Run:

```powershell
C:\Users\86153\anaconda3\python.exe -m pip install -r backend\requirements.txt
C:\Users\86153\anaconda3\python.exe -m pip install pytest filelock fastmcp websockets
```

Expected: 命令退出码为 0，`pytest --version` 可正常输出版本。

- [ ] **Step 4: 运行基线语法检查**

Run:

```powershell
C:\Users\86153\anaconda3\python.exe -m py_compile backend\main.py backend\engine.py backend\schemas.py
node --check backend\static\parent-console-v2.js
```

Expected: 两条命令均无错误输出。

### Task 2: 实现三学段配置模块

**Files:**
- Create: `xueban-master/backend/study_modes.py`
- Test: `xueban-master/tests/test_study_modes.py`

- [ ] **Step 1: 编写失败测试**

```python
# xueban-master/tests/test_study_modes.py
import pytest

from backend.study_modes import get_study_mode, normalize_stage


def test_stage_aliases_are_normalized():
    assert normalize_stage("小学") == "primary"
    assert normalize_stage("初中") == "middle"
    assert normalize_stage("高中") == "high"


def test_unknown_stage_is_rejected():
    with pytest.raises(ValueError):
        normalize_stage("大学")


def test_mode_policy_matches_approved_design():
    primary = get_study_mode("primary")
    middle = get_study_mode("middle")
    high = get_study_mode("high")
    assert (primary.score_threshold, primary.persist_seconds, primary.cooldown_seconds, primary.max_per_10_minutes) == (55, 20, 180, 2)
    assert (middle.score_threshold, middle.persist_seconds, middle.cooldown_seconds, middle.max_per_10_minutes) == (65, 15, 120, 3)
    assert (high.score_threshold, high.persist_seconds, high.cooldown_seconds, high.max_per_10_minutes) == (70, 25, 240, 2)
```

- [ ] **Step 2: 验证测试失败**

Run:

```powershell
C:\Users\86153\anaconda3\python.exe -m pytest tests\test_study_modes.py -v
```

Expected: FAIL，提示 `backend.study_modes` 不存在。

- [ ] **Step 3: 实现配置模块**

```python
# xueban-master/backend/study_modes.py
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class StudyMode:
    key: str
    label: str
    score_threshold: int
    persist_seconds: int
    cooldown_seconds: int
    max_per_10_minutes: int
    reminder: str

    def as_dict(self) -> dict:
        return asdict(self)


STUDY_MODES = {
    "primary": StudyMode(
        "primary", "小学", 55, 20, 180, 2,
        "我们先把眼睛放回题目上，完成这一小步就很棒。",
    ),
    "middle": StudyMode(
        "middle", "初中", 65, 15, 120, 3,
        "先把注意力放回当前任务，我们完成这一小段再休息。",
    ),
    "high": StudyMode(
        "high", "高中", 70, 25, 240, 2,
        "回到当前目标，先完成这一题组，再统一复盘。",
    ),
}

ALIASES = {
    "primary": "primary", "小学": "primary", "小学生": "primary",
    "middle": "middle", "初中": "middle", "初中生": "middle",
    "high": "high", "高中": "high", "高中生": "high",
}


def normalize_stage(value: str) -> str:
    key = ALIASES.get(str(value or "").strip().lower())
    if not key:
        raise ValueError("invalid_study_stage")
    return key


def get_study_mode(value: str) -> StudyMode:
    return STUDY_MODES[normalize_stage(value)]
```

- [ ] **Step 4: 验证测试通过**

Run:

```powershell
C:\Users\86153\anaconda3\python.exe -m pytest tests\test_study_modes.py -v
```

Expected: 3 passed。

### Task 3: 实现跨进程学段状态

**Files:**
- Create: `xueban-master/backend/runtime_state.py`
- Test: `xueban-master/tests/test_runtime_state.py`

- [ ] **Step 1: 编写失败测试**

```python
# xueban-master/tests/test_runtime_state.py
from backend.runtime_state import RuntimeStateStore


def test_stage_is_persisted_with_source(tmp_path):
    store = RuntimeStateStore(tmp_path / "state.json")
    result = store.set_stage("初中", source="voice")
    reloaded = RuntimeStateStore(tmp_path / "state.json").read()
    assert result["studyStage"] == "middle"
    assert reloaded["studyStage"] == "middle"
    assert reloaded["stageLabel"] == "初中"
    assert reloaded["stageSource"] == "voice"
    assert reloaded["stageUpdatedAt"] > 0


def test_default_stage_is_middle(tmp_path):
    store = RuntimeStateStore(tmp_path / "state.json")
    assert store.read()["studyStage"] == "middle"
```

- [ ] **Step 2: 验证测试失败**

Run:

```powershell
C:\Users\86153\anaconda3\python.exe -m pytest tests\test_runtime_state.py -v
```

Expected: FAIL，提示 `backend.runtime_state` 不存在。

- [ ] **Step 3: 实现原子读写和文件锁**

`RuntimeStateStore` 使用 `FileLock(f"{path}.lock")`，默认状态为：

```python
{
    "studyStage": "middle",
    "stageLabel": "初中",
    "stageSource": "default",
    "stageUpdatedAt": 0,
    "xiaozhiMcpUrl": "",
    "xiaozhiMcpToken": "",
    "awayTimeoutMinutes": 15,
}
```

`set_stage(stage, source)` 必须调用 `normalize_stage`，写入临时文件后用 `Path.replace()` 原子替换，并返回包含 `policy` 的完整状态。

- [ ] **Step 4: 验证测试通过**

Run:

```powershell
C:\Users\86153\anaconda3\python.exe -m pytest tests\test_runtime_state.py -v
```

Expected: 2 passed。

### Task 4: 实现分层提醒策略

**Files:**
- Create: `xueban-master/backend/reminder_policy.py`
- Test: `xueban-master/tests/test_reminder_policy.py`

- [ ] **Step 1: 编写失败测试**

```python
# xueban-master/tests/test_reminder_policy.py
from backend.reminder_policy import ReminderPolicy


def distracted_payload(score=40):
    return {
        "status": "distracted",
        "focusScore": score,
        "awaySeconds": 0,
        "metrics": {"posture": 80},
    }


def test_primary_waits_twenty_seconds():
    policy = ReminderPolicy(clock=lambda: 100.0)
    assert policy.observe(distracted_payload(), "primary") is None
    policy.clock = lambda: 119.0
    assert policy.observe(distracted_payload(), "primary") is None
    policy.clock = lambda: 121.0
    assert policy.observe(distracted_payload(), "primary")["studyStage"] == "primary"


def test_high_school_message_is_not_childish():
    policy = ReminderPolicy(clock=lambda: 100.0)
    policy.observe(distracted_payload(), "high")
    policy.clock = lambda: 126.0
    reminder = policy.observe(distracted_payload(), "high")
    assert "题组" in reminder["text"]
    assert "小朋友" not in reminder["text"]
```

- [ ] **Step 2: 验证测试失败**

Run:

```powershell
C:\Users\86153\anaconda3\python.exe -m pytest tests\test_reminder_policy.py -v
```

Expected: FAIL，提示 `backend.reminder_policy` 不存在。

- [ ] **Step 3: 实现策略**

`ReminderPolicy` 必须：

- 接受可注入的 `clock`。
- 状态从专注切到分心时记录开始时间。
- 读取 `get_study_mode(stage)`。
- 只有 `focusScore < score_threshold` 且持续时间达到 `persist_seconds` 才返回提醒。
- 使用每学段独立冷却和最近 10 分钟频率队列。
- 返回 `text`、`studyStage`、`stageLabel`、`policyVersion="stage-v1"`。

- [ ] **Step 4: 验证测试通过**

Run:

```powershell
C:\Users\86153\anaconda3\python.exe -m pytest tests\test_reminder_policy.py -v
```

Expected: 2 passed。

### Task 5: 扩展提醒队列和 MCP 学段工具

**Files:**
- Create: `xueban-master/backend/xiaozhi_bridge.py`
- Create: `xueban-master/xiaozhi_bridge/focus_reminder_mcp.py`
- Test: `xueban-master/tests/test_xiaozhi_bridge.py`

- [ ] **Step 1: 编写失败测试**

```python
# xueban-master/tests/test_xiaozhi_bridge.py
from backend.runtime_state import RuntimeStateStore
from backend.xiaozhi_bridge import ReminderStore


def test_voice_stage_sync_and_stage_metadata(tmp_path):
    state = RuntimeStateStore(tmp_path / "state.json")
    reminders = ReminderStore(tmp_path / "reminders.json", state_store=state)
    stage = state.set_stage("高中", "voice")
    item = reminders.enqueue("managed_ai_reminder", "回到当前目标。")
    assert stage["studyStage"] == "high"
    assert item["studyStage"] == "high"
    assert item["stageLabel"] == "高中"
    assert item["policyVersion"] == "stage-v1"
```

- [ ] **Step 2: 验证测试失败**

Run:

```powershell
C:\Users\86153\anaconda3\python.exe -m pytest tests\test_xiaozhi_bridge.py -v
```

Expected: FAIL，提示桥接模块不存在。

- [ ] **Step 3: 实现队列**

`ReminderStore` 使用 `FileLock` 和原子 JSON 写入，提供：

```python
enqueue(command: str, text: str, focus_payload: dict | None = None) -> dict
pop_next() -> dict
acknowledge(reminder_id: str, spoken: bool = True) -> dict
snapshot() -> dict
```

每个提醒包含 `studyStage`、`stageLabel` 和 `policyVersion`。

- [ ] **Step 4: 暴露 MCP 工具**

```python
@mcp.tool()
def set_study_stage(stage: str, source: str = "voice") -> dict:
    return state_store.set_stage(stage, source)


@mcp.tool()
def get_study_stage() -> dict:
    return state_store.read()


@mcp.tool()
def check_study_focus_and_remind_child() -> dict:
    return reminder_store.pop_next()


@mcp.tool()
def mark_study_reminder_spoken(reminder_id: str, spoken: bool = True) -> dict:
    return reminder_store.acknowledge(reminder_id, spoken)
```

- [ ] **Step 5: 验证测试通过**

Run:

```powershell
C:\Users\86153\anaconda3\python.exe -m pytest tests\test_xiaozhi_bridge.py -v
```

Expected: 1 passed。

### Task 6: 接入 FastAPI、视觉引擎和 MCP 进程

**Files:**
- Modify: `xueban-master/backend/engine.py`
- Modify: `xueban-master/backend/main.py`
- Modify: `xueban-master/backend/schemas.py`
- Create: `xueban-master/backend/xiaozhi_mcp_runtime.py`

- [ ] **Step 1: 更新请求模型**

`RuntimeSettings` 保持原字段并新增 `stageSource`；增加：

```python
class StudyStageCommand(BaseModel):
    stage: Literal["primary", "middle", "high"]
    source: Literal["parent", "voice", "system"] = "parent"


class McpEndpointConfig(BaseModel):
    endpoint: str = Field(min_length=1, max_length=2048)
```

- [ ] **Step 2: 让引擎读取统一状态**

删除引擎内重复的 `_settings["ageMode"]` 所有权。`get_payload()` 从
`RuntimeStateStore` 读取当前模式并增加：

```python
payload["studyStage"] = state["studyStage"]
payload["stageLabel"] = state["stageLabel"]
```

每次得到视觉分析结果后调用 `ReminderPolicy.observe(payload, state["studyStage"])`，产生提醒时写入 `ReminderStore`。

- [ ] **Step 3: 接入 API**

新增或更新：

```text
GET  /settings
POST /settings
GET  /study-stage
POST /study-stage
GET  /mcp/status
POST /mcp/config
POST /mcp/start
POST /mcp/stop
```

`POST /settings` 与 `POST /study-stage` 必须写入同一个 `RuntimeStateStore`。
`/control` 对家长留言和 AI 话术调用 `ReminderStore.enqueue()`。

- [ ] **Step 4: 实现 MCP 生命周期**

`xiaozhi_mcp_runtime.py` 必须验证 endpoint 以 `wss://api.xiaozhi.me/mcp/` 开头，
使用当前 Python 解释器启动桥接进程，写入 PID 与脱敏后的 endpoint 状态，
停止时只终止由本模块创建且 PID 匹配的进程。

- [ ] **Step 5: 运行完整后端测试和语法检查**

Run:

```powershell
C:\Users\86153\anaconda3\python.exe -m pytest tests -v
C:\Users\86153\anaconda3\python.exe -m py_compile backend\main.py backend\engine.py backend\schemas.py backend\study_modes.py backend\runtime_state.py backend\reminder_policy.py backend\xiaozhi_bridge.py backend\xiaozhi_mcp_runtime.py
```

Expected: 全部测试通过，无语法错误。

### Task 7: 更新 V2 家长端

**Files:**
- Modify: `xueban-master/backend/static/parent-console-v2.html`
- Modify: `xueban-master/backend/static/parent-console-v2.js`
- Modify: `xueban-master/backend/static/parent-console-v2.css`

- [ ] **Step 1: 将年龄下拉框改为三段式学段控件**

HTML 使用三个单选按钮：

```html
<fieldset class="stage-control" aria-label="学习模式">
  <legend>学习模式</legend>
  <label><input type="radio" name="studyStage" value="primary">小学</label>
  <label><input type="radio" name="studyStage" value="middle">初中</label>
  <label><input type="radio" name="studyStage" value="high">高中</label>
</fieldset>
<p class="stage-sync" id="stageSyncStatus">等待同步</p>
```

- [ ] **Step 2: 删除浏览器独立计算的学段阈值**

前端不再用 `scoreOffset` 和 `intervalOffset` 推导策略。保存或加载时直接使用后端返回的：

```json
{
  "studyStage": "middle",
  "stageLabel": "初中",
  "policy": {
    "score_threshold": 65,
    "persist_seconds": 15,
    "cooldown_seconds": 120,
    "max_per_10_minutes": 3
  }
}
```

- [ ] **Step 3: 增加模式同步反馈**

语音端修改时，WebSocket payload 的 `studyStage` 变化会更新三段式控件，并显示
“已由小智语音切换为初中模式”；家长端修改显示“已由家长端切换为初中模式”。

- [ ] **Step 4: 检查 JavaScript 和页面布局**

Run:

```powershell
node --check backend\static\parent-console-v2.js
```

Expected: 无错误。

在 1440x900 和 390x844 两个视口检查 Devices、Dashboard、Advice、Review，
确认无文字截断、控件重叠或横向溢出。

### Task 8: 制作唯一知识库文档

**Files:**
- Create: `xueban-master/knowledge_base/小智分层伴学知识库.md`
- Create: `xueban-master/knowledge_base/小智分层伴学知识库.docx`

- [ ] **Step 1: 编写知识库源文件**

必须包含以下完整章节：

1. 调用规则与 `[小学]`、`[初中]`、`[高中]` 标签。
2. 三学段的讲解语气、步骤和禁止行为。
3. 小学语文、数学、英语核心方法与示例。
4. 初中语文、数学、英语核心方法与示例。
5. 高中语文、数学、英语核心方法与示例。
6. 通用任务拆解、错题复盘、学习计划。
7. 分心、离座、疲劳、坐姿的分层提醒话术。
8. 验证题：“小智知识库的三阶校验口令是什么？”
9. 唯一答案：“星芽、知桥、远帆”。

- [ ] **Step 2: 生成 DOCX**

标题使用微软雅黑 16 磅，一级标题 14 磅，正文 10.5 磅，1.3 倍行距；
目录后分页，三学段各自从新页开始；表格不跨页破坏。

- [ ] **Step 3: 渲染并检查**

使用文档渲染工具生成逐页 PNG，确认：

- 无空白页、截断、乱码和溢出。
- 标题层级清晰。
- 检索关键词不被图片替代。
- 唯一校验短语以可搜索文字存在。

### Task 9: 准备并配置小智智能体

**Files:**
- Create: `xueban-master/docs/xiaozhi-agent-role-prompt.txt`
- Create: `xueban-master/docs/xiaozhi-console-checklist.md`

- [ ] **Step 1: 写入角色提示词**

使用以下核心文本，最终控制在平台 2000 字限制内：

```text
你叫小智，是桌面学习陪伴机器人。你服务小学、初中和高中学生。
每个新会话都把学习模式视为“未选择”，不要从长期记忆继承学段。
首次有效对话先问：“请选择小学、初中或高中模式。”
识别到学段后调用 set_study_stage，成功后明确说“已进入X模式”。
用户随时可说“切换到X模式”。无法判断时只重复三个选项，不猜测。

小学模式：亲切具体，每次只给一个小步骤，多用生活化例子和鼓励。
初中模式：平等清楚，先确认目标，再用问题引导概念和步骤。
高中模式：简洁尊重，强调推理链、时间目标、错因定位和自主复盘。
不要直接包办作业，不羞辱、不贴标签，不把一次分心解释为态度问题。

凡涉及语文、数学、英语、学习方法、学习计划或分层讲解，必须先调用
search_knowledge。查询词必须包含当前学段和学科，再依据结果回答。
如果知识库没有结果，要明确说明，不得编造教材结论。

学习过程中可调用 check_study_focus_and_remind_child。若
hasReminder=true，按当前模式温和朗读 reminderText，随后调用
mark_study_reminder_spoken；若无提醒，不打扰孩子。MCP不可用时继续
当前对话，并说明电脑端同步暂未完成。
```

- [ ] **Step 2: 创建知识库**

名称：`小智分层伴学知识库`

描述：

```text
本文档包含小学、初中、高中三个学段的语文、数学、英语知识框架，
分层讲解方法、学习计划、专注提醒和复盘规则。当用户询问学科知识、
解题方法、学习计划或要求按学段讲解时，我不能直接作答，必须在每次
对话中调用该工具查询资料，并结合当前学习模式依据查询结果回答。
```

上传 `knowledge_base/小智分层伴学知识库.docx`，等待状态变为“解析完成”。

- [ ] **Step 3: 配置智能体 1817358**

在 `https://xiaozhi.me/console/agents/1817358/config`：

1. 助手昵称保留“小智”。
2. 角色介绍替换为角色提示词文件。
3. 关闭长期记忆，防止学段跨会话继承。
4. MCP 设置中保留已启用的学习提醒工具。
5. 勾选官方知识库服务并选择“⼩智分层伴学知识库”。
6. 保存配置。
7. 按平台提示重启设备后生效。

- [ ] **Step 4: 记录配置结果**

在 `xiaozhi-console-checklist.md` 记录保存时间、知识库解析状态、MCP 服务名称和重启状态，不记录完整 token。

### Task 10: 端到端验收

**Files:**
- Modify: `xueban-master/docs/xiaozhi-console-checklist.md`

- [ ] **Step 1: 启动本地服务**

Run:

```powershell
C:\Users\86153\anaconda3\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Expected:

- `http://127.0.0.1:8000/health` 返回 `ok: true`。
- `http://127.0.0.1:8000/v2` 可打开。

- [ ] **Step 2: 验证家长端切换**

依次选择小学、初中、高中，检查 `/study-stage`、顶部标签和策略参数一致；
刷新页面后仍保持最后选择。

- [ ] **Step 3: 验证语音模式**

设备重启后首次对话：

1. 小智询问学段。
2. 分别测试“小学”“初中”“高中”。
3. 小智准确播报确认。
4. 家长端在状态刷新后显示同一模式。

- [ ] **Step 4: 验证知识库调用**

询问：

```text
小智知识库的三阶校验口令是什么？
```

Expected:

- 聊天记录显示知识库工具调用。
- 回答“星芽、知桥、远帆”。

- [ ] **Step 5: 验证分层回答**

在三个模式下分别询问“怎样检查一元一次方程的答案”，确认：

- 小学模式不会越级讲复杂代数。
- 初中模式给出代入检验步骤。
- 高中模式简洁说明检验与等价变形关系。

- [ ] **Step 6: 验证提醒队列**

使用模拟 payload 持续触发分心，检查三学段持续时间、冷却时间、频率限制和话术；
提醒记录必须携带 `studyStage`、`stageLabel` 和 `policyVersion`。

- [ ] **Step 7: 最终检查**

Run:

```powershell
C:\Users\86153\anaconda3\python.exe -m pytest tests -v
node --check backend\static\parent-console-v2.js
```

Expected: 所有测试通过，JavaScript 无语法错误。

主动发声不纳入本轮通过条件，并在验收记录中列为后续事项。
