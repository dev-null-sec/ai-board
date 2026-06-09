# ai-board

给 AI agent 用的本地任务看板。把项目状态从聊天记录里搬出来，放进文件。

[English](./README_en.md) | 中文

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="License MIT" src="https://img.shields.io/badge/License-MIT-green">
</p>

![ai-board logo](https://raw.githubusercontent.com/dev-null-sec/ai-board/v0.3.0/assets/ai-board.png)

当前版本：`v0.3.0`。

## 解决什么问题

用 AI 写代码，最常见的翻车不是 AI 不会写——是写到后面，项目状态全散在聊天记录里。早期定的方向、中间改过的方案、哪个功能是谁加的、改完验收了没有，这些信息聊完就丢了。切个 session，AI 就不知道之前怎么约定的。

ai-board 做的事很简单：用一个 JSON 文件存任务、scope、状态和验收记录，用 CLI 读写，再自动生成一份给人看的 Markdown 看板。状态不在 prompt 里，在文件里——不会被压缩、不会被遗忘、不同 agent 之间共享。

这对断连和换 session 也很有用。你说“继续”的时候，AI 不必靠压缩后的聊天上下文猜上次做到哪一步，而是先读看板、当前状态和任务历史，再接着推进。ai-board 不保存聊天内容，但保存项目推进所需的事实。

## 怎么用

你不是在敲命令，你是在对 AI 说话。ai-board 的 CLI 是给 AI 调的，不是给你记快捷键的。

第一次用：

> 用 ai-board 接手这个项目。

AI 会自己装 CLI、跑 onboard、问你方向问题。空项目不会直接写代码，先让你确认目标。

日常开发：

> 把这个需求进 ai-board。如果不属于当前任务就排期。

想看进度：

> ai-board 现在什么状态？下一步做什么？

安装：

```bash
pipx install ai-board
```

接手项目：

```bash
ai-board onboard --init-if-missing
```

日常流程（供 AI agent 参考）：

```bash
ai-board add "添加用户认证" --priority P0 --acceptance "登录接口返回 JWT"
ai-board start <task-id> --agent claude --scope src/auth src/middleware
# ... 干活 ...
ai-board complete <task-id> --verification "单元测试全绿，手动测了登录和过期"
```

多 agent 协作时先 `ai-board config set multi_agent_enabled true`，然后每个 agent 先 claim 身份再 start。scope 重叠会被拦住。

## 能管住什么，管不住什么

**管得住的**：需求记录、任务状态、scope 归属。add 进去的东西有迹可循，complete 了有验收记录，doctor 能检查项目健康状态——active 任务有没有 scope、验收写了没、锁过期了没有。

**管不住的**：AI 在运行时写什么文件。scope gate 是个 git pre-commit 钩子，它拦的是 commit 不是 AI 动手——AI 想写错文件照样先写了，钩子只是在提交关口拦一道。`git commit --no-verify` 一行就能绕过去。scope 冲突检测也只是路径前缀匹配，两个不同文件有业务耦合它看不出来。

所以这东西说到底不是保险箱。它更像一套逼 AI 先记账再动手的流程：你可以随口说“帮我改一下”，但接手了 ai-board 的 AI 应该先把需求进看板、声明 scope，再开始动代码。它管不住模型运行时每一次手抖，但能让“这次为什么改、打算改哪些文件、改完怎么验收”留下记录。真失控了，也不是聊天记录里翻半天，而是能直接看任务、scope 和 git diff。

## 它存什么

| 数据 | 文件 | 说明 |
| --- | --- | --- |
| 任务、状态、scope、验收 | `.ai-board/board.json` | 唯一数据源，CLI 写入 |
| 操作历史 | `.ai-board/events.jsonl` | 可审计的变更日志 |
| 当前看板 | `docs/计划看板.md` | 自动渲染，不手改 |
| 归档看板 | `docs/归档计划看板.md` | 自动渲染 |
| 护栏文档 | `AGENTS.md`、`docs/开发规范.md` 等 | AI 行为约束 |

JSON 是机器读的，Markdown 是人读的。写入永远走 CLI，保证两边一致。

## 边界

| 已支持 | 暂不做 |
| --- | --- |
| 本地 CLI，JSON 数据源 | Web 登录、云同步 |
| Markdown 自动渲染 | 手写 Markdown 当数据库 |
| 单 agent 默认模式 | 强制多 agent 流程 |
| 可选多 agent scope 防撞 | 语义级代码冲突检测、跨机器锁 |
| doctor 项目自检 | 自动修复 |
| 可选 pre-commit scope gate | 运行时文件拦截 |
| AGENTS.md 护栏生成 | 自动执行护栏规则 |

## 开发

```bash
uv sync
uv run python -m unittest discover -s tests
uv run --with ruff ruff check .
```

## License

MIT. See [LICENSE](./LICENSE).
