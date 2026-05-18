# ai-board

[English](https://github.com/dev-null-sec/ai-board/blob/v0.1.0-alpha.4/README_en.md) | 中文

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="CLI ai-board" src="https://img.shields.io/badge/CLI-ai--board-0B1F4D">
  <img alt="License MIT" src="https://img.shields.io/badge/License-MIT-green">
</p>

![ai-board logo](https://raw.githubusercontent.com/dev-null-sec/ai-board/v0.1.0-alpha.4/assets/ai-board.png)

给 AI agent 用的本地计划看板。你跟 AI 对话提需求，它帮你排期、跟踪、防冲突，而不是直接开改。

当前版本：`v0.1.0-alpha.4`，仍是 alpha，重点修正新项目接手门禁和 agent skill 安装口径。

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
请安装 ai-board 并接手当前项目：
1. 优先用 pipx install ai-board 安装用户级 CLI。
2. 如果 pipx 不可用，再用 uv tool install ai-board。
3. 安装后运行 ai-board onboard --init-if-missing。
4. 按该 agent 的 skill 安装方式，把 https://github.com/dev-null-sec/ai-board.git 里的 skills/ai-board/SKILL.md 放到对应 agent 的 skills 目录；除非该 agent 已经安装过这个 skill。
```

AI 会检查环境、装 CLI、放 skill 文件、读版本匹配的使用说明。全程不用你手动操作。

如果你想自己装：

```powershell
pipx install ai-board
```

没有 `pipx` 但有 `uv`：

```powershell
uv tool install ai-board
```

想安装 GitHub 上的最新源码版时，再使用：

```powershell
pipx install "git+https://github.com/dev-null-sec/ai-board.git"
```

## 命令速查

大部分时候你不需要敲命令，跟 AI 对话就行。但如果你想看状态或手动操作：

```powershell
ai-board status                      # 当前任务分布
ai-board show T-0001                 # 查看某个任务详情
ai-board render                      # 重新生成 Markdown 看板
ai-board lang zh-CN                  # 查看中文输出的环境变量设置方式
```

完整命令参考：`ai-board --help` 或 `ai-board skills get core --full`。

## 工作方式

整体流程很简单：

```text
你 / AI 提需求
        ↓
ai-board CLI 写入 .ai-board/board.json
        ↓
render 生成 Markdown 看板
        ↓
AI / 人读取状态，继续推进
```

| 设计点 | 说明 |
| --- | --- |
| 真相源 | `.ai-board/board.json` 是唯一写入源，Markdown 看板只是生成视图。 |
| 看板渲染 | `add`、`schedule`、`start`、`complete`、`archive` 等 CLI 写操作会自动刷新 Markdown；`ai-board render` 是手动修复和配置变更后的兜底命令。 |
| 多 agent | 重叠文件范围默认被拦住；这是路径级防撞，不是理解代码语义的万能锁。 |
| 项目配置 | `.ai-board/config.json` 可设置默认语言、默认泳道、默认 agent 类型和默认租约。 |
| scope lock | 默认 240 分钟租约；可通过项目配置调整；任务 `complete` 后释放 agent 身份，`archive` 把已验收任务移出当前看板。 |
| 多泳道 | 一个看板可以分平台开发、课程内容、文档等泳道，但只有一个真相源。 |
| 简单依赖 | 任务可以声明依赖，`start` 默认会挡住依赖未完成的任务；复杂依赖图暂时不做。 |
| 自检 | `doctor` 检查 board、生成文档、事件日志、scope 冲突和 agent 状态。 |
| 历史 | `history` 从 `.ai-board/events.jsonl` 查看任务变更记录。 |
| agent notice | `tell` / `inbox` 提供轻量跨 agent 提醒，`inbox --fail-on-unresolved` 可用于收口检查；它不是实时聊天。 |
| 生命周期 | `inbox → scheduled → active → done → archived`。 |

默认生成中文看板。如果项目主要使用英文，可以把 `.ai-board/config.json` 里的 `language` 改成 `en-US`，再运行 `ai-board render`。正常通过 CLI 改任务时不需要手动 render；只有手改配置、拉取代码后怀疑生成视图过期，或 `doctor` 提示 stale 时才需要运行。

`doctor` 的轻量业务检查可以通过 `.ai-board/config.json` 调整，例如 active 任务多久算停滞、agent lease 剩多久开始提醒、哪些 scope 算过宽。

CLI 默认输出英文，方便 AI、脚本和 CI 稳定使用。人手动看时可以用 `AI_BOARD_LANG=zh-CN` 或 `ai-board --lang zh-CN status` 切到中文；不想记环境变量就运行 `ai-board lang zh-CN`。

如果要改安装口径、接手流程或命令规则，优先改 `ai-board skills get core` 对应的内置指南；仓库里的 `skills/ai-board/SKILL.md` 只负责发现入口。

## FAQ

<details>
<summary><strong>ai-board 会保存 AI 的聊天记录或上下文吗？</strong></summary>

不是。`ai-board` 不会把 AI 脑子里的上下文原样保存下来，也不会假装恢复一整段对话记忆。

它保存的是项目推进需要稳定存在的东西：需求、优先级、状态、负责人、scope、验收结果、遗留问题。换句话说，聊天可以断，模型可以换，但项目计划不应该只活在聊天记录里。

</details>

<details>
<summary><strong>为什么不用 Markdown 直接管理任务，而要用 JSON？</strong></summary>

Markdown 适合给人读，不适合当稳定的数据源。任务状态、负责人、scope、依赖、验收结果这些字段需要被程序可靠地读取、校验、排序和更新；如果都写在 Markdown 里，AI 或人一改格式，工具就很难判断哪些是内容、哪些是结构。

所以 `ai-board` 用 `.ai-board/board.json` 存结构化数据，再生成 Markdown 给人看。简单说：JSON 负责准确，Markdown 负责好读。

</details>

<details>
<summary><strong>Markdown 看板可以手动改吗？</strong></summary>

不建议。真正存数据的是 `.ai-board/board.json`，它更像这个小工具的本地数据库。`docs/计划看板.md` 和 `docs/归档计划看板.md` 只是从 JSON 渲染出来的阅读视图，给人和 AI 快速扫一眼用。

如果你手改 Markdown，下一次 CLI 写操作或 `ai-board render` 可能会覆盖它。要改任务状态、负责人、scope、验收结果，走 CLI。

</details>

<details>
<summary><strong>为什么要封装成 CLI，而不是只靠文档约束？</strong></summary>

只靠文档约束，AI 很容易漏步骤：忘了排期、忘了写 scope、忘了归档，或者两个 agent 同时改同一片文件。

CLI 的价值不是“更高级”，而是把这些动作变成固定入口：`add`、`schedule`、`start`、`complete`、`archive`。该拦的冲突由工具拦，该写入的状态由工具写，不全靠 AI 自觉。

</details>

<details>
<summary><strong>它能替代上下文吗？</strong></summary>

不能，也不该替代。

上下文适合讨论细节、解释取舍、临时判断；`ai-board` 适合保存那些不能丢的项目事实。两者配合起来，AI 接手项目时先看 board 和 docs，再根据当前对话继续推进，而不是只靠“我好像记得之前说过什么”。

</details>

<details>
<summary><strong>init 会覆盖我已有的项目文档吗？</strong></summary>

默认不会。`ai-board init` 会创建 `AGENTS.md`、`docs/当前状态.md`、`docs/开发规范.md` 等 AI 原生开发文档；如果同名文件已经存在，默认写成 `.example`，避免直接盖掉你的内容。

</details>

<details>
<summary><strong>只能给 Codex 用吗？</strong></summary>

不是。仓库里带了 Codex 可读的 skill stub，因为我自己主要在这个环境里用；但 CLI 本身是普通命令行工具。Claude、其他 agent，甚至人手动敲命令都能用。关键是让 agent 先读 `ai-board skills get core`，按当前版本的规则操作。

</details>

<details>
<summary><strong>多 agent 防冲突能防到什么程度？</strong></summary>

它能防最常见的路径重叠：比如一个 agent 已经锁了 `src/api`，另一个 agent 默认不能再启动 `src/api/handler.py` 的任务。

它不会理解“两个不同文件其实有业务耦合”，也不是跨机器协作锁。需要真正并行开发时，scope 还是要写窄，任务边界也要说清楚。

</details>

## 项目结构

```text
src/ai_board/          CLI 核心
skills/ai-board/       给 AI agent 的 discovery skill
tests/                 测试
docs/                  这个项目自己的计划和状态文档
```

## 当前边界

不是 Jira，不是 Web 项目管理系统。当前版本先把本地 CLI、JSON 真相源、事件日志、doctor 自检、多 agent 路径级防撞和 Markdown 视图跑顺。

| 已支持 | 暂不做 |
| --- | --- |
| 本地 CLI | Web 登录 |
| JSON 真相源 | 云同步 |
| Markdown 生成视图 | 自动排期 |
| 简单依赖校验 | 复杂依赖图 |
| 事件日志和 `history` | OS 级文件锁 |
| `doctor` 项目自检 | 语义级代码冲突判断 |
| 多 agent 路径级 scope 防撞 | 跨机器协作锁 |
| 轻量 agent notice | 实时聊天系统 |

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
