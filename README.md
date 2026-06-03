# ai-board

给 AI agent 用的本地计划看板。它把需求、排期、正在改的文件范围、验收结果和遗留问题记录下来，让 AI 接手项目时不用只靠聊天记录猜。

[English](https://github.com/dev-null-sec/ai-board/blob/v0.1.20/README_en.md) | 中文

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="CLI ai-board" src="https://img.shields.io/badge/CLI-ai--board-0B1F4D">
  <img alt="License MIT" src="https://img.shields.io/badge/License-MIT-green">
</p>

![ai-board logo](https://raw.githubusercontent.com/dev-null-sec/ai-board/v0.1.20/assets/ai-board.png)

当前正式版本：`v0.1.20`。

## 为什么做这个

AI 写代码时，很多混乱不是代码本身造成的，而是项目状态没有一个稳定地方保存。

一个需求刚说完，AI 可能立刻开改；又插进来一个 bug，它也继续改。几轮之后，原来的计划在哪里、当前任务算不算做完、哪些文件已经被另一个会话碰过，就很容易散在聊天记录里。

`ai-board` 只处理这类项目事实：需求进不进看板、排到哪一批、谁在做、scope 是哪些文件、验收跑了什么、还有什么没收尾。聊天继续负责讨论细节，看板负责留下可恢复的状态。

它不是 Jira，也不是 Web 项目管理系统。现在就是一个本地 CLI，一个 `.ai-board/board.json`，再生成两份 Markdown 看板给人和 AI 读。

## 最短路径

一般不需要人手动敲一串命令，直接把这段给 AI：

```text
请安装 ai-board 并接手当前项目：
1. 优先用 pipx install ai-board 安装用户级 CLI。
2. 如果 pipx 不可用，再用 uv tool install ai-board。
3. 安装后运行 ai-board onboard --init-if-missing。
4. 按该 agent 的 skill 安装方式，把 https://github.com/dev-null-sec/ai-board.git 里的 skills/ai-board/SKILL.md 放到对应 agent 的 skills 目录；除非该 agent 已经安装过这个 skill。
```

自己安装时：

```powershell
pipx install ai-board
```

没有 `pipx` 但有 `uv`：

```powershell
uv tool install ai-board
```

想试 GitHub 上的当前源码版：

```powershell
pipx install "git+https://github.com/dev-null-sec/ai-board.git"
```

## 人和 AI 怎么配合

`ai-board` 更适合这样用：人说清楚意图，AI 负责安装、接手、排期、启动任务、记录验收和归档。人不用记命令，提示词也不该写成长规则；短、准、能触发流程就够。

### 第一次接手

给 AI 这段提示词：

```text
用 ai-board 接手这个项目。
先 onboard；信息不够就问我，不要猜方向或直接编码。
```

这句话会让 AI 自己处理安装、初始化和读取内置指南。空项目先问目标、用户和第一版范围；已有项目先整理状态，再把后续开发放进看板。

### 提新需求

平时不要让 AI 直接“顺手改一下”。更稳的说法是：

```text
把这个需求进 ai-board。
判断它是否属于当前任务；不属于就排期，别直接开改。
```

需要立刻处理时，可以说得更明确：

```text
这个问题优先处理。
先写入 ai-board 并说明插队原因，再 start、声明 scope、修改和验收。
```

### 多 agent 开发

默认是单 agent 轻量模式。如果确实要同时开两个 AI 会话，先让其中一个会话启用多 agent：

```text
开启 ai-board 多 agent 协作。
每个会话先 claim 身份；改前查 scope，收到 notice 先收口。
```

### 看进度

问 AI 就行：

```text
看 ai-board：现在做什么？下一步做什么？
```

AI 背后会用 `status`、`next`、`show`、`doctor` 这些命令读状态。命令细节留给 agent，人的工作是确认方向、优先级和验收口径。

## 它保存哪些东西

| 内容 | 放在哪里 |
| --- | --- |
| 任务、状态、负责人、scope、验收结果 | `.ai-board/board.json` |
| 当前看板 | `docs/计划看板.md` |
| 归档看板 | `docs/归档计划看板.md` |
| 操作历史 | `.ai-board/events.jsonl` |
| agent notice | `.ai-board/messages.jsonl` |

`board.json` 是唯一写入源，Markdown 只是生成视图。任务状态、依赖、scope、验收这些字段需要被程序读取、排序和校验，放在 JSON 里更稳；Markdown 留给人读。

任务 `scope` 描述的是本轮业务修改范围。CLI 写操作自动更新 `.ai-board/board.json`、事件/消息日志和生成看板，这是 ai-board 自己的记账副作用；除非任务本身就是修改这些文件，否则不用把它们每次都写进 scope。

## 几个默认选择

| 设计 | 当前做法 |
| --- | --- |
| 单 agent 开发 | 默认轻量，不强制处理多 agent notice 和 scope 冲突。 |
| 多 agent 协作 | 项目级可选开关，默认关闭。需要并行开发时开启。 |
| git | 默认 `git_integration=suggest`，没有 git 时提示初始化，但不会静默 `git init`。 |
| 看板语言 | 默认中文，可改成 `en-US`。 |
| scope | 记录文件或小目录，不做语义级代码冲突判断。 |

多 agent 开启方式：

```powershell
ai-board config set multi_agent_enabled true
```

开启后，重叠 scope 会被拦住，`next --agent` 会显示 notice，`complete` / `archive` 会提醒未收口消息。单 agent 开发时，它不会强制你天天看 notice、处理 inbox 或被 active scope 冲突拦住。

git 强制模式：

```powershell
ai-board config set git_integration required
```

临时实验目录可以关闭 git 检查：

```powershell
ai-board config set git_integration off
```

## 常见问题

<details>
<summary><strong>为什么不用 Markdown 直接管理任务？</strong></summary>

Markdown 很适合读，不适合当结构化状态源。任务状态、负责人、scope、依赖、验收结果这些字段需要稳定读写。格式一旦被人或 AI 改散，工具就很难判断哪些是内容，哪些是结构。

所以 `ai-board` 用 JSON 存状态，再生成 Markdown 看板。

</details>

<details>
<summary><strong>Markdown 看板可以手动改吗？</strong></summary>

不建议。下一次 CLI 写操作或 `ai-board render` 会重新生成 Markdown，手改内容可能被覆盖。改任务状态、负责人、scope、验收结果时走 CLI。

</details>

<details>
<summary><strong>为什么不自动 git init？</strong></summary>

AI 开发最好有可回滚点，但项目根目录、父级仓库、临时目录、大文件、密钥和已有未完成改动都可能需要确认。`ai-board` 会提醒，不会静默初始化 git，也不会自动提交用户已有改动。

</details>

<details>
<summary><strong>多 agent 防冲突能防到什么程度？</strong></summary>

只能防路径重叠。比如一个任务锁了 `src/api`，另一个任务要改 `src/api/handler.py`，开启多 agent 后会被拦住。

它不理解两个不同文件之间的业务耦合，也不是跨机器强锁。真正并行开发时，scope 还是要写窄，任务边界也要写清楚。

</details>

<details>
<summary><strong>只能给 Codex 用吗？</strong></summary>

不是。仓库里带了 Codex 可读的 skill stub，但 CLI 本身只是普通命令行工具。Claude、其他 agent，或者人手动敲命令都能用。关键是让 agent 先读 `ai-board skills get core`，按当前版本的规则操作。

</details>

## 当前边界

| 已支持 | 暂不做 |
| --- | --- |
| 本地 CLI | Web 登录 |
| JSON 真相源 | 云同步 |
| Markdown 生成视图 | 手写 Markdown 当数据库 |
| 事件日志和 `history` | 完整审计系统 |
| `doctor` 项目自检 | 语义级代码冲突判断 |
| git-first 提示和 required 门禁 | 静默初始化 git 或自动提交 |
| 可选多 agent 路径级 scope 防撞 | 跨机器协作锁 |
| 轻量 agent notice | 实时聊天系统 |

## 项目结构

```text
src/ai_board/          CLI 核心
skills/ai-board/       给 AI agent 的 discovery skill
tests/                 测试
docs/                  这个项目自己的计划和状态文档
examples/demo-project/ 示例项目
```

## 开发

```powershell
uv sync
uv run python -m unittest discover -s tests
uv run --with ruff ruff check .
```

本地安装当前工作区版本：

```powershell
uv tool install --editable .
```

发布前检查：

```powershell
uv run ai-board conflicts --fail-on-conflict
uv run ai-board doctor --fail-on-issue
uv run --with build python -m build
uv run --with twine twine check dist/*
```

## License

MIT License. See [LICENSE](./LICENSE).
