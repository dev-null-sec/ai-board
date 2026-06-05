# GSD Pi vs ai-board 轻量性对比测试准备

## 目标

这份准备文档只为后续真实测试建立基线，不消耗 Claude / Anthropic API key。

后续 `T-0122` 要回答的问题是：

- ai-board 是否真的比 GSD Pi 更轻量，还是只是口头判断。
- 轻量性差异主要来自哪里：token、状态文件、命令链路、人工干预，还是工具定位差异。
- 对比结果是否需要调整 ai-board 的 1.0 方向。

## 轻量性的可测定义

本次不把“轻量”只理解成安装包小或命令少，而拆成几个可记录指标：

| 指标 | 记录方式 |
| --- | --- |
| input tokens | Anthropic Usage 按 API key / model / 时间窗口导出 |
| output tokens | Anthropic Usage 按 API key / model / 时间窗口导出 |
| cache creation / read tokens | Anthropic Usage 或 Console 明细 |
| billed cost | Anthropic Usage 对应 key 的费用 |
| request count | Anthropic Usage 请求数；没有逐请求明细时记录窗口内总请求 |
| elapsed time | 两个会话从发送任务提示词到最终验收结束的墙钟时间 |
| command count | 人工记录 agent 关键命令，不追求逐 token 级精确 |
| changed files | `git diff --name-status` |
| generated state size | `.gsd/`、`.ai-board/` 等工具状态目录总大小 |
| manual interventions | 用户或监工中途纠偏次数 |
| final verification | 测试是否通过，README 是否更新，结果是否可复现 |

结论必须区分事实、推断和不确定项。token 数据如果只能从时间窗口汇总得到，要明确窗口内是否混入其他请求。

## 隔离目录

本次准备已建立：

```text
tmp/gsd-vs-ai-board/
  seed-project/
  run-gsd/
  run-ai-board/
  reports/
```

- `seed-project` 是不可变基线，只用于复制，不在真实测试中直接修改。
- `run-gsd` 只给 GSD Pi 测试会话使用。
- `run-ai-board` 只给 ai-board 测试会话使用。
- `reports` 存放计量模板、后台 usage 导出和最终报告。

三份项目均从同一个 git baseline commit 创建：

```text
71be1000f65154ae67c844a159a77abc20884069
```

真实测试前应再次确认：

```powershell
git -C tmp/gsd-vs-ai-board/run-gsd rev-parse HEAD
git -C tmp/gsd-vs-ai-board/run-ai-board rev-parse HEAD
git -C tmp/gsd-vs-ai-board/run-gsd status --short
git -C tmp/gsd-vs-ai-board/run-ai-board status --short
```

两个运行目录必须是同一 commit，且工作区为空。

## Seed 项目

seed 是一个极小 Python CLI：

```text
calc.py
tests/test_calc.py
README.md
```

当前行为：

```powershell
uv run python calc.py add 1 2
```

输出：

```text
3
```

测试：

```powershell
uv run python -m unittest discover -s tests
```

真实对比任务是给两个 Claude Code 会话同一段提示词：

```text
你正在一个隔离测试项目中。请完成同一个小需求，用最少改动实现并验证：

给 calc.py 的 add 子命令增加 --json 输出模式。

要求：
- uv run python calc.py add 1 2 仍输出 3。
- uv run python calc.py add 1 2 --json 输出 {"operation":"add","left":1,"right":2,"result":3}。
- 更新 tests/test_calc.py。
- 更新 README.md。
- 运行 uv run python -m unittest discover -s tests。
- 不要修改测试项目以外的文件。
- 不要读取或引用另一个对比目录。
- 完成后报告：改了哪些文件、跑了什么验证、是否有遗留问题。
```

## 双 key 计量方法

真实测试使用两个 Anthropic API key，避免同一个 key 的 usage 混在一起：

| key | 用途 | 目录 |
| --- | --- | --- |
| key A | GSD Pi 测试 | `tmp/gsd-vs-ai-board/run-gsd` |
| key B | ai-board 测试 | `tmp/gsd-vs-ai-board/run-ai-board` |

安全规则：

- key 只在对应终端会话里以环境变量设置。
- 不把 key 写入文件、报告、shell history 摘要或 git commit。
- 每次测试记录绝对开始和结束时间，精确到分钟。
- 两边使用同一模型、同一地区网络条件和同一任务提示词。
- 测试期间尽量不要用这两个 key 做其他请求。
- 若后台 usage 存在延迟，记录导出时间。

推荐计量来源：

1. Anthropic Console 的 Usage 页面：按 API key、model、时间窗口过滤并导出 CSV。
2. 如果账号有管理权限，再评估 Claude Code Analytics / Admin API 是否能按 key 拉取 usage。
3. 若只能拿到聚合数据，报告中必须标注证据强度，不把聚合数据包装成逐请求精确数据。

## 会话执行骨架

### GSD Pi 会话

前置：

- 只进入 `tmp/gsd-vs-ai-board/run-gsd`。
- 只设置 key A。
- 如果需要拉取 GSD Pi 或其依赖，本机走代理。
- 不读取 `run-ai-board`、父项目 `.ai-board` 或父项目文档。

执行：

```text
打开一个全新的 Claude Code 会话，使用 key A。
在 run-gsd 中按 GSD Pi 推荐流程接手项目并完成同一段测试提示词。
```

### ai-board 会话

前置：

- 只进入 `tmp/gsd-vs-ai-board/run-ai-board`。
- 只设置 key B。
- 使用当前发布版或明确记录本仓库 editable 版本。
- 不读取 `run-gsd`、父项目 `.ai-board` 或父项目文档。

执行：

```text
打开一个全新的 Claude Code 会话，使用 key B。
在 run-ai-board 中安装/初始化 ai-board，然后完成同一段测试提示词。
```

## 报告结构

`reports/metrics-template.csv` 已提供指标表头。真实测试后建议生成：

- `reports/metrics.csv`
- `reports/gsd-transcript.md`
- `reports/ai-board-transcript.md`
- `reports/anthropic-usage-export-key-a.csv`
- `reports/anthropic-usage-export-key-b.csv`
- `reports/final-report.md`

最终报告至少包含：

- 实验条件：日期、模型、工具版本、baseline commit、目录隔离方式。
- 量化结果：token、cost、request、耗时、状态文件大小、人工干预。
- 产物结果：测试是否通过、diff 是否符合需求。
- 证据强度：哪些数据来自后台 usage，哪些来自人工记录。
- 结论：ai-board 是否更轻量；如果是，轻在哪里；如果不是，原因是什么。
- 对路线影响：是否调整 ai-board 1.0 的定位或排期。

## 已完成的准备验证

- `seed-project` 已建立 git baseline commit：`71be1000f65154ae67c844a159a77abc20884069`。
- `run-gsd` 与 `run-ai-board` 均复制自同一 baseline commit。
- 两个运行目录初始 `git status --short` 为空。
- seed 项目测试已通过：`uv run python -m unittest discover -s tests`。

## 不在本任务中做

- 不启动真实 Claude Code 双会话。
- 不设置或读取 API key。
- 不消耗 Anthropic usage。
- 不得出最终 GSD Pi vs ai-board 胜负结论。
