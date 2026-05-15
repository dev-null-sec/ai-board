# Claude 多进程协作实测准备

## 目标

先完成前置准备，不直接进入正式双 Claude 协作测试。

本次准备要确认四件事：

- 临时测试项目可用，并已由 `ai-board` 初始化。
- Claude Code CLI 可调用。
- Claude 进程能在测试项目中使用最新版 `ai-board`，看到 `tell/inbox` notice 能力。
- 监工侧能通过命令记录状态、事件、消息、锁和测试结果。

## 临时项目

路径：

```text
D:\Backup\Documents\服务器远程运维\ai-board\tmp\claude-multi-agent-test
```

项目内容：

- `sample_app/math_tools.py`
- `sample_app/text_tools.py`
- `tests/test_math_tools.py`
- `tests/test_text_tools.py`

基线验证：

```powershell
uv run --with pytest pytest
```

结果：4 条测试通过。

## ai-board 初始化和版本确认

临时项目已执行：

```powershell
uv run ai-board init --project-name "Claude multi-agent test"
```

初始化后发现一个重要问题：临时项目第一次 `uv run ai-board` 使用的是旧环境里的 ai-board，命令集中没有 `tell`、`inbox`、`reopen`、`config`。

为保证测试用的是当前仓库最新版，已在临时项目中执行：

```powershell
uv pip install --editable ..\..
```

安装后确认：

- `uv run ai-board --help` 能看到 `tell`、`inbox`、`reopen`、`config`。
- `uv run ai-board skills get core` 能看到 notice 响应协议。
- `uv run ai-board doctor --fail-on-issue` 通过。

正式测试时应要求 Claude 使用：

```powershell
uv run ai-board ...
```

不要让 Claude 直接依赖裸 `ai-board`，因为裸命令当前指向用户级安装，可能不是本仓库最新版。

## Claude 可调用性

已确认：

```powershell
claude --version
```

结果：

```text
2.1.121 (Claude Code)
```

Claude 的 ai-board skill 已同步到：

```text
C:\Users\Administrator\.claude\skills\ai-board\SKILL.md
```

该 skill 只保留发现入口，完整规则仍要求从 `ai-board skills get core` 读取。

## Claude 探针

已在临时项目执行一次非交互式探针：

```powershell
claude -p "你是在一个临时测试项目中做前置探针。请不要修改任何文件。只运行或判断这些命令是否可用：uv run ai-board status；uv run ai-board skills get core。回答两点：1. 当前 ai-board status 摘要；2. core guide 里是否能看到 tell/inbox notice 命令。" --permission-mode bypassPermissions --allowedTools "Bash(uv run ai-board status),Bash(uv run ai-board skills get core)"
```

结果：

- Claude 成功调用 `uv run ai-board status`。
- Claude 确认当前测试项目为空板。
- Claude 确认 core guide 中能看到 `tell`、`inbox`、`ack`、`resolve` 以及 notice 响应流程。

## 已预置测试任务

临时项目看板已预置：

- `T-0001 Agent A: extend math tools`
  - 新增 `multiply(left, right)` 并补测试。
  - 预期写范围：`sample_app/math_tools.py`、`tests/test_math_tools.py`。
- `T-0002 Agent B: extend text tools`
  - 新增 `normalize_spaces(text)` 并补测试。
  - 预期写范围：`sample_app/text_tools.py`、`tests/test_text_tools.py`。
- `T-0003 Agent C: shared verification notice drill`
  - 触发一次 `tell -> inbox -> ack -> board 校验 -> resolve`。
  - 不要求新增功能，重点记录 notice 协作行为。

## 监工方案

正式测试时，监工只做记录和边界提醒，不替 Claude 设计每一步实现。

建议监控命令：

```powershell
uv run ai-board status
uv run ai-board locks
uv run ai-board conflicts --fail-on-conflict
uv run ai-board doctor --fail-on-issue
uv run ai-board history
uv run ai-board inbox --agent claude-00 --all
uv run ai-board inbox --agent claude-01 --all
Get-Content .ai-board\events.jsonl
Get-Content .ai-board\messages.jsonl
uv run --with pytest pytest
```

正式测试的关键观察点：

- 两个 Claude 是否各自 claim 身份，而不是共用同一身份。
- 是否先用 `next` / `locks` 判断任务和 scope。
- 是否用窄 scope 启动任务。
- 遇到共享验证资源时，是否使用 notice，而不是靠聊天上下文。
- 收到 notice 后是否先校验 board 状态，再 ack/resolve。
- 完成任务后是否写清 verification 和 leftovers，并归档释放锁。

## 当前结论

前置准备已满足继续正式测试的条件。

唯一需要注意的是：Claude 正式测试 prompt 必须明确要求使用 `uv run ai-board`，否则可能误用用户级旧版 `ai-board`。
