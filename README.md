# ai-board

[English](./README_en.md) | 中文

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="CLI ai-board" src="https://img.shields.io/badge/CLI-ai--board-0B1F4D">
  <img alt="License MIT" src="https://img.shields.io/badge/License-MIT-green">
</p>

![ai-board logo](./assets/ai-board.png)

给 AI agent 用的本地计划看板。你跟 AI 对话提需求，它帮你排期、跟踪、防冲突，而不是直接开改。

## 为什么做这个

用 AI 写代码最大的坑不是代码质量，是上下文管理。

你跟 AI 说"帮我改一下这个"，它大概率会立刻动手。改完了你又提一个，它又立刻改。几个来回之后，你问"之前那个规划做到哪了"——它已经忘了，因为临时需求把之前的上下文冲掉了。

`ai-board` 想解决的就是这个：AI 不会因为你的临时需求丢掉之前的规划，所有需求统一进排期。紧急 bug 当然可以插队，高优先级优先处理，但不会打乱整体节奏。

初始化项目时，`ai-board` 还会拉起一套开发规范文档——项目方向、当前状态、决策记录、开发规则。这不是重点，但确实帮项目从第一天就有据可查。

## 怎么跟 AI 用

`ai-board` 主要是给 AI 用的，不需要你自己敲一堆命令。你要做的是跟 AI 对话，它来执行。

### 开始新项目

跟 AI 说：

```text
用 ai-board 接手这个项目，先规划一下方向
```

AI 会运行 `ai-board onboard --init-if-missing`，然后问你项目目标、技术栈、初版范围。你们对齐之后，它会把方向和计划写进文档，再把具体任务排进看板。不是上来就写代码，是先把"做什么、不做什么"定下来。

### 接手已有项目

跟 AI 说：

```text
用 ai-board 接管这个项目
```

AI 会扫描项目结构，梳理当前状态，生成项目方向、技术栈、风险和下一步建议等文档。梳理完之后，后续所有开发工作都通过看板管理，不再靠聊天记录猜进度。

### 提需求

日常开发中最常见的场景。以前你可能会说：

```text
这里有个 bug，帮我修一下
```

或者：

```text
把这个页面改成 xxx 样式
```

AI 会直接动手改。改完你又提一个，它又改。几个来回之后，之前的规划就丢了。

现在你这样说：

```text
这里有个 bug，加到看板里
```

```text
把这个页面改成 xxx 样式，排进下一批
```

AI 会把需求排进看板，而不是立刻动手。紧急的 bug 会标高优先级优先处理，但不会丢掉之前的任务。你随时可以问"现在在做什么"，AI 给你看的是看板状态，不是靠聊天记录猜的。

## 安装

最推荐的方式：把安装和初始化都交给 AI。给它一句话：

```text
请从 https://github.com/dev-null-sec/ai-board.git 安装 ai-board，然后运行 ai-board onboard --init-if-missing 接手当前项目。
```

AI 会检查环境、装 CLI、放 skill 文件、读版本匹配的使用说明。全程不用你手动操作。

如果你想自己装：

```powershell
pipx install "git+https://github.com/dev-null-sec/ai-board.git"
```

没有 `pipx` 但有 `uv`：

```powershell
uv tool install "git+https://github.com/dev-null-sec/ai-board.git"
```

## 命令速查

大部分时候你不需要敲命令，跟 AI 对话就行。但如果你想看状态或手动操作：

```powershell
ai-board status                      # 当前任务分布
ai-board show T-0001                 # 查看某个任务详情
ai-board render                      # 重新生成 Markdown 看板
```

完整命令参考：`ai-board --help` 或 `ai-board skills get core --full`。

## 工作方式

几个关键设计：

- `.ai-board/board.json` 是唯一写入源，Markdown 看板是生成的
- 多 agent 同时干活时，重叠的文件范围默认被拦住
- scope lock 有 240 分钟租约，到时自动释放
- 一个看板可以分多条泳道（平台开发、课程内容、文档……），但只有一个真相源
- 任务生命周期：`inbox → scheduled → active → done → archived`

## 项目结构

```text
src/ai_board/          CLI 核心
skills/ai-board/       给 AI agent 的 discovery skill
tests/                 测试
docs/                  这个项目自己的计划和状态文档
```

## 当前边界

不是 Jira，不是 Web 项目管理系统。当前版本先把本地 CLI、JSON 真相源、多 agent scope 防撞和 Markdown 视图跑顺。

暂时不做：Web 登录、云同步、自动排期、复杂依赖图、OS 级文件锁。

## 开发

```powershell
uv sync
uv run python -m unittest discover -s tests
```

本地开发想直接用 `ai-board` 命令：

```powershell
uv tool install --editable .
```

## License

MIT License. See [LICENSE](./LICENSE).
