# ai-board

用 AI 写代码不难。难的是写到第十轮对话、第三个 agent 接手时，项目不变成一坨屎山。

[English](./README_en.md) | 中文

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="CLI ai-board" src="https://img.shields.io/badge/CLI-ai--board-0B1F4D">
  <img alt="License MIT" src="https://img.shields.io/badge/License-MIT-green">
</p>

![ai-board logo](https://raw.githubusercontent.com/dev-null-sec/ai-board/v0.1.20/assets/ai-board.png)

当前版本：`v0.1.20`。

## 这不是一个看板工具

如果你以为 `ai-board` 就是一个"命令行的 Trello"或者"给 AI 用的 todo list"，那你被它的外表骗了。

它做的事比任务管理深得多：**它给 vibe coding 定了一套治理范式。**

什么叫治理范式？就是当 AI 开始替你写代码时，有些事你不该全靠"信任 AI 自己会把控"——你应该有规则、有护栏、有机器的强制执行，让项目不会因为 AI 的一句"顺手改一下"而慢慢滑向混乱。

`ai-board` 就是这套护栏。它不替 AI 写代码，它替 AI **管方向、锁范围、记验收、防越界**。

## vibe coding 的核心问题

用 AI 开发的人都会经历同一个曲线：

第一周：太爽了。说一句话，AI 就把功能写好了。

第二周：开始有点乱。AI 顺手重构了不相干的文件，上次聊天的方案记不清了，同一个需求改了三个版本不知道哪个是最新的。

第三周：不敢改了。项目里东一块西一块的 AI 痕迹，有些是"当时觉得需要但后来发现不需要的"，有些是"顺手加上去的"，你不敢删因为不确定删了会坏什么。

根本原因不是 AI 不行。**根本原因是 AI 开发缺了一套外部治理机制。** 人类开发有 code review、有 CI、有项目管理工具、有团队沟通。AI 开发呢？全靠聊天记录。

`ai-board` 解决的就是这个：**把人做项目管理的那套约束，适配到 AI 驱动的开发流程里。** 但它不是把 Jira 搬进终端。它重新设计了治理模型——因为 AI 开发需要的约束和人类开发不一样。

## 这套治理范式的几个原则

### 原则一：AI 不能自行推断项目方向

一个很常见的场景：用户开了个空目录，说"帮我做个东西"。AI 一看目录名是 `api-server`，就开始规划路由、中间件、数据库。但它没问过用户：你要 REST 还是 GraphQL？用 Go 还是 Python？是不是只是一个周末项目？

`ai-board onboard` 做的事情就是拦住这个冲动。它扫描项目——空项目、轻量新项目、已有项目——然后**强制 AI 先问用户方向**，再排期，再编码。空项目猜方向是最危险的，`onboard` 直接堵死了这条路。

### 原则二：每个代码变更必须有归属

"顺手改一下"是 AI 开发里最危险的一句话。用户说了句"这个变量名不对"，AI 改了变量名，顺便优化了函数签名，重构了调用链，还加了个缓存层。三周后，没人知道那个缓存是计划内的还是顺手产物。

`ai-board` 要求每个变更挂在任务下面。任务有 scope（改哪些文件）、有验收标准（怎么算做完）、有验证结果（实际跑了什么）。需求进"需求池"，排期到"下一批"，start 到"正在进行"，complete 写验收，archive 归档。

这不仅是为了记录。它创造了一条规则：**AI 不能对非当前任务范围内的东西动手。** 用户随口说的"顺便修一下"和真正的紧急插队，都要先写入看板。

### 原则三：多 agent 不能互踩

大项目可能需要同时开多个 AI 会话并行推进。但两个 agent 同时改同一个文件就是灾难。

`ai-board` 的 scope 锁机制解决这个：agent start 任务时声明文件级 scope，别的 agent 再 start 时如果 scope 重叠就会被拦住。锁有过期机制，agent 可以续租，释放后别人才能碰。这不是分布式一致性锁，但在 AI 开发的颗粒度上够用了——至少不会两个 agent 对着同一个 `handler.py` 各改各的。

单 agent 开发时不强制这些检查，不会天天让你处理 notice 和 scope 冲突。这个渐进式设计是刻意的——一个人用的时候不想背团队的包袱。

### 原则四：验收不是"看起来对了"

AI 说"完成了"，它真的完成了吗？验收标准写了吗？验证跑了吗？遗留问题记了吗？

`ai-board` 的 complete 命令要求填写：验证结果（你跑什么了）、遗留问题（还有什么没收尾）、延后验收（哪些全量验证现在跑不了）。`doctor` 命令会检查：active 任务有没有 scope？验收标准写了没有？锁是不是过期了？看板生成的 Markdown 和 JSON 源头是不是一致？git 有没有初始化？

这些检查不是在挑刺。它们是在补 AI 开发最容易塌的那块：**完成的定义太模糊。**

## 怎么用

### 人怎么用

你不是在敲命令。你是在对 AI 说话。`ai-board` 的 UI 不是终端，是自然语言。

第一次用，给 AI 这一段：

> 用 ai-board 接手这个项目。

AI 会自己装 CLI、跑 onboard、判断项目状态、问你方向问题。空项目不会直接写代码，会先让你确认目标。

日常开发，给 AI 这一段：

> 把这个需求进 ai-board。如果不属于当前任务就排期。

AI 会判断该不该插队、加到需求池还是直接排期、scope 写什么、验收标准怎么定。

想看进度：

> ai-board 现在什么状态？下一步做什么？

AI 调用 `status`、`next`、`show`，把结果翻译成人话。

**你不是在操作 CLI。你是在指挥 AI。CLI 是 AI 手里的工具，不是你的。**

### AI 怎么用（供 Claude/Codex 等 agent 参考）

安装：

```powershell
pipx install ai-board
```

接手项目：

```powershell
ai-board onboard --init-if-missing
```

这会扫描项目、初始化看板、生成护栏文档（AGENTS.md、开发规范、当前状态等），并输出项目类型判断。

日常流程：

```powershell
ai-board add "添加用户认证" --priority P0 --acceptance "登录接口返回 JWT" --acceptance "未登录请求返回 401"
ai-board schedule <task-id>
ai-board start <task-id> --agent claude --scope src/auth src/middleware
# ... 干活 ...
ai-board complete <task-id> --verification "单元测试全绿，手动测了登录和过期"
ai-board archive <task-id>
```

多 agent 协作时先开启：

```powershell
ai-board config set multi_agent_enabled true
```

然后每个 agent 先 `claim` 身份，`start` 时声明 scope，`next` 会提示 scope 冲突和被阻塞的候选任务。

## 它和常见东西的区别

**和 Jira / Linear / Trello 的区别：** 那些是给人用的项目管理工具，核心是团队协作和可视化。`ai-board` 是给 AI agent 用的治理层，核心是方向确认、scope 锁、验收闭环和护栏规则生成。它的操作者是 AI，不是人。

**和 git 的关系：** `ai-board` 不替代 git，它依赖 git。默认配置下它会提醒你初始化 git、建议编码前提交、可以用 `git_integration=required` 强制要求。它的定位是"让 AI 在每次改动前都有可回滚点"，git 是回滚机制的底座。

**和 CLAUDE.md / AGENTS.md 的关系：** `ai-board init` 会生成 AGENTS.md 和 docs/ 下的护栏文档。这些文件告诉 AI：编码前先读计划看板，新需求先进需求池，最多同时做 1-2 个任务。没有这些规则，AI 会倾向于"听到什么就立刻改什么"——这对于多人项目和长期项目是灾难。

**和"一个超长 system prompt"的区别：** 有些人试图把规则全塞进 system prompt 里。问题在于 prompt 会被裁剪、遗忘、不同 agent 之间不共享。`ai-board` 把治理规则放在项目的文件系统里，agent 进入项目时读取，互不依赖各自的 prompt 配置。规则和项目绑定，不和 agent 绑定。

## 它保存什么

| 数据 | 文件 | 角色 |
| --- | --- | --- |
| 任务、状态、scope、锁、验收 | `.ai-board/board.json` | 唯一真相源 |
| 操作历史 | `.ai-board/events.jsonl` | 可审计的变更日志 |
| agent 间消息 | `.ai-board/messages.jsonl` | 多 agent notice |
| 当前看板（人类可读） | `docs/计划看板.md` | 生成视图，不手改 |
| 归档看板 | `docs/归档计划看板.md` | 生成视图 |
| 护栏文档 | `AGENTS.md`、`docs/开发规范.md` 等 | AI 行为约束 |

JSON 是机器读的，Markdown 是人读的。写入永远走 CLI，保证 JSON → Markdown 的生成不会散架。

## 项目结构

```text
src/ai_board/          CLI 核心（cli / operations / store / render / guardrails / onboarding / parser / skill_guides）
skills/ai-board/       给 Codex 等 agent 的 discovery skill
tests/                 测试
docs/                  这个项目自己的计划和状态
examples/demo-project/ 示例项目
```

## 当前边界

| 已支持 | 暂不做 |
| --- | --- |
| 本地 CLI，JSON 真相源 | Web 登录、云同步 |
| Markdown 生成视图 | 手写 Markdown 当数据库 |
| 单 agent 默认模式 | 强制多 agent 流程 |
| 可选多 agent scope 防撞 | 语义级代码冲突检测、跨机器锁 |
| 事件日志和 `history` | 完整审计系统 |
| `doctor` 项目自检 | 自动修复 |
| git 提示和 required 门禁 | 静默 `git init` / `git commit` |
| AGENTS.md 护栏生成 | 自动执行护栏规则 |

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

## License

MIT License. See [LICENSE](./LICENSE).
