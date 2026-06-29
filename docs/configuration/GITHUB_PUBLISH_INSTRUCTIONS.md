# GitHub publish instructions

## Current state

- Target repository: `Nohaol/xueban`
- Prepared branch: `codex/study-modes-mcp-kb`
- Commit: `feat: add staged study modes and MCP learning workflow`
- Local validation: 95 tests passed

The Git credential currently available on this computer belongs to
`yiluo5823`. GitHub rejected direct write access to `Nohaol/xueban` with HTTP
403, so the delivery is also provided as a ZIP and a Git Bundle.

## Publish with an authorized account

Authenticate Git with an account that has write access to `Nohaol/xueban`,
then run in the prepared repository:

```powershell
cd D:\小智ai\_publish\xueban
git push -u origin codex/study-modes-mcp-kb
```

Open:

```text
https://github.com/Nohaol/xueban/compare/master...codex/study-modes-mcp-kb
```

Create a draft pull request titled:

```text
[codex] add staged study modes and MCP learning workflow
```

## Restore from the Git Bundle

```powershell
git clone D:\小智ai\小智伴学_Git提交包_20260628.bundle xueban-delivery
cd xueban-delivery
git remote set-url origin https://github.com/Nohaol/xueban.git
git push -u origin codex/study-modes-mcp-kb
```

The ZIP is intended for browsing and manual upload. The Bundle is preferred
when commit history and the prepared branch should be retained.
