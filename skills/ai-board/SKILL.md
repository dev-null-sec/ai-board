---
name: ai-board
description: Discovery stub for the ai-board CLI. Use this to find the installed command, then read the bundled guide from ai-board skills get core.
allowed-tools: Bash(ai-board:*), Bash(pipx:*), Bash(uv:*), Bash(python:*), Bash(python3:*)
---

# ai-board

这是一个发现入口，不是完整说明书。

## 你该怎么做

1. 先确认 `ai-board` 命令在不在。
2. 如果没有，优先从 PyPI 装成用户级 CLI：`pipx install ai-board`，没有 `pipx` 再用 `uv tool install ai-board`。
3. 然后跑 `ai-board onboard --init-if-missing` 接手项目。
4. 需要规则细节时，用 `ai-board skills get core`。

## 安装顺序

优先级保持和 CLI 内置 guide 一致：

1. Python 3.10+
2. `pipx`
3. `python -m pipx`
4. `uv tool install`

常用命令：

```bash
pipx install ai-board
uv tool install ai-board
```

## 这个文件放哪

把它放到目标 agent 的 skill/skills 目录里，例如 Codex、Claude，或者其他支持 skill 的工具。

## 修改入口

以后要改安装口径、接手流程或命令规则，请改：

- CLI 内置 guide：`ai-board skills get core`
- 仓库里的源码：`src/ai_board/skill_guides.py`

这个文件只保留发现和入口，不再复制完整流程。
