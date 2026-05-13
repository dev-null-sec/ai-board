# ai-board

[English](./README_en.md) | 中文

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![CLI](https://img.shields.io/badge/CLI-ai--board-0B1F4D)
![License](https://img.shields.io/badge/License-MIT-green)

![ai-board logo](./assets/ai-board.png)

`ai-board` 是一个给 AI agent 用的本地计划看板 CLI。它不想替代 Jira，也不想做一个很重的项目管理系统，只是想把 AI 开发时最容易丢的那点上下文固定下来。

我做它，是因为长会话、临时插需求、多 agent、反复接手项目时，最容易乱的不是代码本身，而是“现在到底该做什么、谁在做、改哪些文件、做完怎么验收”。尤其是你隔一会儿再问 AI 项目进度，它很容易靠聊天记录和上下文猜一个答案。`ai-board` 的做法很朴素：把任务、排期、scope、验收和遗留问题放进一个结构化真相源：`.ai-board/board.json`。Markdown 看板只是给人和 AI 阅读的生成视图。

## 它解决什么

- 临时提了一个需求，先进入需求池，不让它散在聊天记录里。
- 任务要先排期、claim、写清楚 scope，再开始改文件，减少“AI 觉得自己已经知道了”的误判。
- 多 agent 同时工作时，重叠 scope 默认会被挡住，至少先把撞文件这类低级事故拦一下。
- 做完必须写验收结果和遗留问题，再归档；下一次接手不用靠猜。
- `ai-board init` 会生成 `AGENTS.md`、当前状态、决策记录、计划看板等 AI 原生项目文档，让新项目一开始就有规矩。
- 一个看板可以分多条泳道，例如平台开发、课程内容、文档治理，但仍然只有一个真相源。

这个项目最开始更像一个 skill：靠 Markdown 文档告诉 AI 怎么做。后来我把核心操作收进 CLI，是因为只靠文档有两个麻烦：一是 skill 复制出去以后容易过期，二是多 agent 协作时需要一个能稳定读写、能检查冲突的入口。现在的设计是：skill 负责让 AI 找到工具，CLI 负责真正维护状态和输出版本匹配的说明。

## AI 原生安装方式（推荐）

这是推荐方式：把安装和初始化交给 AI，让它按当前机器环境自检、安装 CLI，把 skill 放到目标 agent 的技能目录，再读取版本匹配的使用说明。

给 AI 最短的一句话是：

```text
请从 https://github.com/dev-null-sec/ai-board.git 安装 ai-board。

要求：
1. 把 CLI 安装成用户级命令，不要装进当前项目虚拟环境。
2. 把仓库里的 skills/ai-board/SKILL.md 放到当前使用的 AI agent 的 skill/skills 目录，例如 Codex、Claude 等工具自己的技能目录。
3. 安装后运行 ai-board skills get core，并按它的说明在当前项目中建立 AI 原生计划看板。
```

AI 应该同时完成两件事：安装 `ai-board` CLI，并安装 discovery skill。CLI 是真正执行任务的工具，skill 是让 Codex、Claude 这类 agent 以后能自动发现和调用它的入口。

CLI 推荐安装顺序：

1. 已有 `ai-board`：直接使用。
2. 有 Python 3.10+ 和 `pipx`：用 `pipx` 安装。
3. 有 Python 3.10+ 但没有 `pipx`：可用 `python -m pip install --user pipx` 准备 pipx，再用 `python -m pipx install` 安装。
4. 没有合适的 Python/pipx，但有 `uv`：用 `uv tool install`。

人工手动安装时分两步。

第一步，安装 CLI：

```powershell
pipx install "git+https://github.com/dev-null-sec/ai-board.git"
```

如果没有 `pipx`，但有 Python：

```powershell
python -m pip install --user pipx
python -m pipx ensurepath
python -m pipx install "git+https://github.com/dev-null-sec/ai-board.git"
```

如果只有 `uv`：

```powershell
uv tool install "git+https://github.com/dev-null-sec/ai-board.git"
```

这些安装方式都会生成全局命令：

```powershell
ai-board --help
```

本地开发时可以在仓库根目录运行：

```powershell
uv sync
uv run python -m ai_board --help
```

第二步，安装 skill：把仓库里的这个文件复制到你正在使用的 AI agent 的 skill/skills 目录里。

```text
skills/ai-board/SKILL.md
```

例如 Codex、Claude 或其他支持 skill 的 agent，都需要按各自的规则放到对应配置目录。只装 CLI 也能手动运行命令，但 agent 不一定会自动知道什么时候该用它。

## 给 AI 的项目使用提示词

项目里装好 `ai-board` 后，可以把这段话交给 AI：

```text
请接手当前项目，并使用 ai-board 管理后续开发。

工作要求：
1. 先运行 ai-board skills get core，读取当前版本的使用规则。
2. 如果项目还没有 .ai-board/board.json，先运行 ai-board init，不要覆盖已有规范文档。
3. 读取 AGENTS.md、docs/计划看板.md、docs/当前状态.md、docs/开发规范.md。
4. 新需求先进入需求池；只有排期并 start 后才开始改文件。
5. start 时必须写清楚 --scope，避免和其他 agent 撞文件。
6. 完成后写中文验收结果和遗留问题，再 archive。
```

## 人工快速开始

在任意项目根目录运行：

```powershell
ai-board init --project-name "my-project"
ai-board goal "交付第一版可用闭环"
ai-board add "补齐登录流程" --priority P1 --lane "平台开发" --source "roadmap" --acceptance "手动登录流程通过"
ai-board schedule T-0001
ai-board start T-0001 --agent codex --scope frontend/src/Login.tsx
ai-board locks
ai-board complete T-0001 --verification "手动登录流程通过" --leftovers "无"
ai-board archive T-0001
```

初始化后会生成：

```text
.ai-board/board.json
AGENTS.md
docs/开发规范.md
docs/当前状态.md
docs/决策记录.md
docs/项目方向.md
docs/页面设计.md
docs/项目路线/README.md
docs/计划看板.md
docs/归档计划看板.md
```

已有规范文档默认不会被覆盖，会生成同名 `.example`。只有确实要替换时才使用：

```powershell
ai-board init --overwrite-docs
```

## Skill 入口

仓库里提供了一个很薄的 skill stub：

```text
skills/ai-board/SKILL.md
```

它只负责让 AI 知道什么时候该用 `ai-board`，以及如何自检、安装 CLI、读取版本匹配的说明。真正的使用说明由 CLI 自己提供，避免 skill 复制出去以后过期：

```powershell
ai-board skills get core
ai-board skills get core --full
```

这套设计参考了 `agent-browser` 的做法：skill 是入口，CLI 才是版本匹配的说明书和执行工具。

## 常用命令

```powershell
ai-board status
ai-board add "任务标题" --priority P1 --lane "平台开发"
ai-board schedule T-0001
ai-board start T-0001 --agent codex --scope src README.md
ai-board locks
ai-board conflicts --fail-on-conflict
ai-board complete T-0001 --verification "测试通过" --leftovers "无"
ai-board archive T-0001
ai-board render
ai-board show T-0001
```

任务生命周期：

```text
inbox -> scheduled -> active -> done -> archived
blocked -> scheduled
```

## 工作方式

`ai-board` 有几个刻意的取舍：

- `.ai-board/board.json` 是唯一写入源。
- `docs/计划看板.md` 和 `docs/归档计划看板.md` 是生成视图，不建议手改。
- 写入 board 时会使用本地 lock 文件和原子替换，避免并发写坏 JSON。
- `start` 默认阻止和 active task 重叠的 scope；确认要重叠时才用 `--force`。
- `--lane` 用来在一个看板里区分不同工作流，而不是拆出多个互相打架的看板。
- 归档里的验收结果和遗留问题要写给人看，可以带关键命令，但不要只贴命令串。

## 项目结构

```text
src/ai_board/          CLI、状态操作、渲染和初始化模板
skills/ai-board/       给 AI agent 使用的 discovery skill
tests/                 单元测试
examples/demo-project/ 示例看板输出
docs/                  本项目自己的计划、状态和决策文档
assets/                Logo 等发布素材
```

## 开发与测试

```powershell
uv run python -m unittest discover -s tests
ai-board conflicts --fail-on-conflict
```

如果你在本地开发并希望直接得到 `ai-board` 命令：

```powershell
uv tool install --editable .
```

## 当前边界

`ai-board` 不是 Jira，也不是 Web 项目管理系统。当前版本先把本地 CLI、AI 接手规则、JSON 真相源、多 agent scope 防撞和 Markdown 视图跑顺。

暂时不做：

- Web 登录系统
- 云同步和多人权限
- 自动智能排期
- 复杂依赖图调度
- OS 级文件锁

已排期但还没做完的增强包括：scope lock 的 lease 超时、续租和解锁，以及 SQLite 后端或事件日志评估。

## License

MIT License. See [LICENSE](./LICENSE).
