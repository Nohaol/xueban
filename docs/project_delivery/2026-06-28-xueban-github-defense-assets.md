# 小智伴学 GitHub 发布与答辩图片 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将本轮代码、知识库、配置资料和 8 张答辩图片整理到 GitHub 功能分支，并保留完整 ZIP 备份。

**Architecture:** 从远程仓库克隆干净副本，将 `xueban-master` 中的产品文件按白名单同步进去。答辩图片使用一个独立的 16:9 HTML 视觉源生成，逐画布导出 1920×1080 PNG，流程图同时保留 SVG；发布前运行测试、敏感信息扫描和图片尺寸检查。

**Tech Stack:** Git、FastAPI/Pytest、HTML/CSS/SVG、Playwright、PowerShell、GitHub。

---

## 文件结构

- Create: `README.md` 更新后的项目总入口。
- Create: `docs/configuration/xiaozhi-agent-role-prompt.txt`
- Create: `docs/configuration/xiaozhi-console-checklist.md`
- Create: `docs/configuration/DEPLOYMENT_AND_ACCEPTANCE.md`
- Create: `docs/defense_assets/source/xueban-task-assets.html`
- Create: `docs/defense_assets/source/render-assets.mjs`
- Create: `docs/defense_assets/01_本轮任务成果总览.png`
- Create: `docs/defense_assets/02_三学段模式切换架构.png`
- Create: `docs/defense_assets/03_专注提醒MCP闭环.png`
- Create: `docs/defense_assets/04_软硬件技术路线.png`
- Create: `docs/defense_assets/05_知识库与智能体配置.png`
- Create: `docs/defense_assets/06_工程成果数据看板.png`
- Create: `docs/defense_assets/07_完成度与下一阶段路线.png`
- Create: `docs/defense_assets/08_答辩数据表.png`
- Create: `docs/defense_assets/*.svg` 对应的可编辑流程图源文件。
- Create: `docs/defense_assets/答辩数据表.csv`
- Create: `knowledge_base/小智分层伴学知识库.md`
- Create: `knowledge_base/小智分层伴学知识库.docx`
- Create: `D:\小智ai\小智伴学_GitHub交付包_20260628.zip`

### Task 1: 建立干净 GitHub 工作副本

- [ ] **Step 1: 克隆远程仓库**

Run:

```powershell
git clone https://github.com/Nohaol/xueban.git D:\小智ai\_publish\xueban
```

Expected: `origin/master` 指向当前远程提交。

- [ ] **Step 2: 创建发布分支**

Run:

```powershell
git -C D:\小智ai\_publish\xueban switch -c codex/study-modes-mcp-kb
```

Expected: 当前分支为 `codex/study-modes-mcp-kb`。

### Task 2: 同步产品代码和配置资料

- [ ] **Step 1: 按白名单同步代码**

同步以下目录，不复制 `runtime`、日志、缓存和本地环境：

```text
backend/
focus_lab/
tests/
xiaozhi_bridge/
knowledge_base/
docs/configuration/
```

- [ ] **Step 2: 更新 README**

README 必须包含：

```text
三学段模式
知识库问答
专注提醒 MCP 闭环
家长端启动方式
答辩可视化入口
当前能力边界
```

- [ ] **Step 3: 扩充 .gitignore**

确保包含：

```gitignore
backend/runtime/
*.log
.env*
__pycache__/
*.pyc
.pytest_cache/
focus_lab/outputs/
focus_lab/data/
focus_lab/config/
```

### Task 3: 制作 8 张答辩图片

- [ ] **Step 1: 创建统一视觉源**

在 `docs/defense_assets/source/xueban-task-assets.html` 中创建 8 个
`1920×1080` 画布，统一使用：

```css
--paper: #fbf6ee;
--ink: #172338;
--orange: #ef6a32;
--green: #2f8a69;
--blue: #3478c8;
--line: #ddd2c4;
```

- [ ] **Step 2: 写入已验证数据**

仅使用以下已验证数据：

```text
3 种学习模式
5 个自定义 MCP 工具
95 项自动化测试通过
19 页可检索知识库
1 套家长端工作台
主动发声固件升级为下一阶段
```

- [ ] **Step 3: 导出图片**

Run:

```powershell
node docs/defense_assets/source/render-assets.mjs
```

Expected: 8 张 PNG 均为 `1920×1080`。

- [ ] **Step 4: 生成可编辑流程图和数据表**

流程图另存 SVG；任务矩阵另存 UTF-8 CSV。

### Task 4: 验证代码和视觉资产

- [ ] **Step 1: 运行自动化测试**

Run:

```powershell
python -m pytest tests -q
```

Expected: `95 passed`。

- [ ] **Step 2: 检查 JavaScript**

Run:

```powershell
node --check backend/static/parent-console-v2.js
node --check docs/defense_assets/source/render-assets.mjs
```

Expected: 两个命令退出码均为 `0`。

- [ ] **Step 3: 扫描敏感信息**

Run:

```powershell
rg -n "wss://api\.xiaozhi\.me/mcp/\?token=|eyJ[a-zA-Z0-9_-]+\." .
```

Expected: 产品提交目录中无 MCP URL、JWT 或完整 token。

- [ ] **Step 4: 检查图片**

检查 PNG 尺寸、文字裁切、重叠、颜色一致性，并生成一张总览拼图用于 QA。

### Task 5: 打包、提交和推送

- [ ] **Step 1: 生成 ZIP**

Run:

```powershell
Compress-Archive -Path D:\小智ai\_publish\xueban\* -DestinationPath D:\小智ai\小智伴学_GitHub交付包_20260628.zip
```

Expected: ZIP 可正常列出并包含代码、知识库、配置说明和答辩图片。

- [ ] **Step 2: 提交变更**

Run:

```powershell
git add backend focus_lab tests xiaozhi_bridge knowledge_base docs README.md .gitignore
git commit -m "feat: add staged study modes and MCP learning workflow"
```

- [ ] **Step 3: 推送功能分支**

Run:

```powershell
git push -u origin codex/study-modes-mcp-kb
```

Expected: 远程分支可访问。

- [ ] **Step 4: 创建 Draft PR**

标题：

```text
[codex] add staged study modes and MCP learning workflow
```

PR 正文说明功能、目录、测试结果、隐私边界和下一阶段主动发声工作。

