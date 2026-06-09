# GSD Core workflow 借鉴评估

## 评估边界

本评估只看机制先进程度，不考虑当前实现成本。

被评估对象是 `gsd-build/get-shit-done`，也就是 GSD Core 这一套面向 Claude Code、Codex、OpenCode 等运行时的元提示、上下文工程和规格驱动开发系统。

它不是一个单纯任务看板。它更像一套围绕 `.planning/` 文件和 agent workflow 组织起来的“AI 项目执行方法”：先把项目愿景、需求、路线、阶段上下文、计划、执行总结和验收结果拆成不同文件，再由命令把这些文件喂给不同阶段的 AI。

ai-board 的定位仍然不变：

> 本地优先、git 联动、可验证、可审计的 AI 项目治理 CLI。

所以本评估的重点不是“ai-board 要不要变成 GSD”，而是：GSD 哪些流程机制能提升 ai-board 对规划、验证、审计和跨会话连续性的治理能力。

## GSD Core 的核心机制

GSD Core 解决的主问题是 context rot：长会话里上下文越来越脏，AI 输出质量逐步下降。它的应对方式不是让一个会话一直记住所有事情，而是把项目上下文拆成稳定文件，再让不同阶段用不同上下文重新开始。

它的主流程可以概括为：

1. `new-project`：通过提问、研究、需求整理和路线图生成项目骨架。
2. `discuss-phase`：在具体阶段执行前，把灰区和实现偏好问清楚，形成阶段上下文。
3. `plan-phase`：研究、拆原子计划，并检查计划是否覆盖需求。
4. `execute-phase`：按 wave 执行计划，能并行的并行，有依赖的顺序执行。
5. `verify-work`：把自动验证和人工 UAT 分开，记录用户逐项确认结果。
6. `progress --next`：根据当前产物自动判断下一步该讨论、规划、执行、验证、发布还是开启新里程碑。

它的关键文件投影是：

| 文件 | 机制作用 | 对 ai-board 的启发 |
| --- | --- | --- |
| `PROJECT.md` | 项目愿景、价值、边界、约束、关键决策 | 对应 ai-board 的项目方向、决策记录和当前状态，但 GSD 对生命周期更清楚 |
| `REQUIREMENTS.md` | v1/v2/out-of-scope、需求 ID、需求到 phase 的追踪 | ai-board 缺少需求级 traceability，可借鉴 coverage gate |
| `ROADMAP.md` | phase、依赖、成功标准、进度 | ai-board 有路线文档，但还没有结构化阶段完成检查 |
| `STATE.md` | 当前阶段、决策、阻塞、待办、跨会话记忆 | ai-board 的当前状态相似，但应增加“短而新的会话接力”约束 |
| `PLAN.md` | 原子任务、实施步骤、验证步骤 | ai-board task 有验收标准，但缺少计划质量 gate |
| `SUMMARY.md` | 任务做了什么、改了什么、交接信息 | 对应 ai-board 的 events、history、review 方向 |
| `UAT.md` / `VERIFICATION.md` | 自动验证与人工验收证据 | 直接影响 0.3 verification evidence 设计 |

## 机制先进性排序

### 1. Progress router：比普通 next 更强

GSD 的 `progress --next` 不是简单列出下一条任务，而是读当前 planning artifacts 后判断项目正处于哪一步：

- 项目是否缺基础 planning 结构；
- 当前 phase 是否已经 discuss；
- 是否已经 plan；
- 是否已有执行 summary；
- 是否有 verification 或 UAT debt；
- 是否可以 ship；
- 是否应该进入下一 phase 或 milestone。

这比 ai-board 当前 `next` 更先进。ai-board 的 `next` 目前主要围绕 active、scheduled、inbox、scope lock、notice 和 blocked 状态给动作建议；它还不能很好地回答：

- 看板空了，但路线文档里是否还有下一阶段；
- 当前任务完成了，但验证债务是否还在；
- 计划文档和当前状态是否互相矛盾；
- 已经讨论出的阶段意图是否没有拆进任务池。

对 ai-board 的优化方向：

- 增强 `next` 为“工作流路由器”，而不是只做候选任务列表。
- 当 active/scheduled/inbox 都为空但路线文档有“下一阶段 / 后续待拆 / phase”时，提示先拆下一批任务。
- 当存在 deferred verification、未引用验证证据或 UAT debt 时，优先提示验收收口。
- 当当前状态说有后续方向但 board 没有占位任务时，提示路线断档。

### 2. Requirements / Decision Coverage Gate：直接命中 ai-board 当前短板

GSD 的 plan 阶段会把计划和需求对照，检查需求是否被覆盖；阶段讨论里形成的决策，也会进入后续研究和规划。

这点很关键，因为 ai-board 刚暴露过同类问题：用户和 AI 已经讨论出长期方向，但 AI 只把眼前文档任务排进看板；做完后需求池清空，下一轮看不到“后面还要做 skill、CLI 或验证闭环”。

这不是单纯模型问题，也不是单纯工具问题，而是当前流程缺少一个 gate：

> 规划产生后，工具没有检查“关键决策和后续阶段是否已经进入可持久读取的位置”。

对 ai-board 的优化方向：

- 在 `doctor` 或未来 `plan check` 中增加 planning coverage warning。
- 检查路线文档里的“阶段 / 后续待拆 / 决策”是否至少有：
  - 路线文档记录；
  - 当前状态摘要；
  - inbox placeholder；
  - 或明确标记为暂不拆。
- 不要求自然语言强理解，但可以做轻量约定：路线文档用固定标题或短标记表达“后续待拆”“已落入需求池”“暂缓原因”。
- 对“只排当前切片，但没有记录后续阶段”的情况给 warning。

### 3. Verification debt / UAT persistence：应进入 0.3 核心设计

GSD 把自动验证和人工 UAT 分开，这是比“测试通过”自由文本更成熟的地方。

自动测试只能证明一部分事情：命令能跑、单测能过、静态检查没有报错。但很多 AI 开发问题是“功能实现了，却不是用户想要的样子”。GSD 的 `verify-work` 会把可测试交付项列出来，逐项让用户确认，并把失败项转成修复计划。

ai-board 0.3 原本就计划做 verification evidence。结合 GSD，应把证据分成几类：

| 类型 | 含义 | 可信度 |
| --- | --- | --- |
| automated | 工具实际运行命令并记录退出码、时间、输出摘要 | 高 |
| manual | agent 或用户手工说明验证过 | 中 |
| uat | 用户逐项确认功能是否符合预期 | 高，但依赖人工反馈 |
| deferred | 当前不能全量验证，记录原因和后续条件 | 不是通过，是债务 |
| blocked | 验证无法完成，需要外部条件 | 阻塞项 |

对 ai-board 的优化方向：

- 0.3 不应只做 `verify --run`，还应设计 verification debt 模型。
- `complete` 可以允许引用 automated/manual/uat 证据，但 deferred 必须作为遗留项展示。
- `review` 和 `next` 应优先暴露未收口的 deferred / blocked verification。

### 4. Phase / wave planning：适合借鉴为“规划质量原则”，不适合默认变成复杂调度器

GSD 的 phase 和 wave 机制很强：它把一个阶段拆成多个原子计划，再按依赖和文件冲突分组执行。能并行的计划进入同一个 wave，有依赖或冲突的计划排到后面。

机制上这比 ai-board 现在的 scheduled/inbox 更高级，尤其适合大型功能开发。

但 ai-board 不应默认变成 wave 调度平台。更适合的借鉴方式是：

- 在规划文档中引入“phase / slice / dependency”描述；
- 对多任务并行时提醒“垂直切片优先，水平分层容易冲突”；
- 多 agent 开启后，`next` 可以提示哪些 scheduled task 与 active scope 不冲突，近似形成轻量 wave；
- 不做复杂 milestone executor，不替用户启动子 agent。

### 5. Closed phase / stale artifact gate：适合强化 doctor

GSD 对已经完成的 phase 有关闭语义，也会检测 STATE、SUMMARY、UAT、ROADMAP 是否不一致。

ai-board 目前对 task 生命周期较严格，但对路线文档、当前状态和归档记录之间的一致性还弱。比如：

- 任务已归档，但当前状态仍说它是下一步；
- 路线文档写了 0.3 是 verification evidence，但 board 没有对应占位；
- blocked 任务实际已经不符合方向，但没有复核；
- 生成看板过期可以查，但路线文档和 board 的关系还不能查。

对 ai-board 的优化方向：

- `doctor` 增加路线断档和 stale current status 提醒。
- 归档任务后，如果它是当前状态里的“下一步”，提示更新当前状态。
- 对“已完成 / 已归档”的路线阶段不允许被静默改写，至少要求记录决策或新增任务说明。

### 6. Handoff / pause-work：适合补 ai-board 的暂停与交接能力

GSD 的 `pause-work` / `resume-work` 解决的是“会话中断后如何继续”。ai-board 当前有 `unlock`、`rescope`、`reopen`，但对“任务没完成，我先停一下，下次从哪里接”还不够自然。

对 ai-board 的优化方向：

- 继续推进 `pause/resume` 和 `note` 评估。
- 暂停不应等同于失败，也不应强行 complete/archive。
- 暂停时应记录：
  - 已完成的部分；
  - 当前阻塞或等待；
  - 已验证和未验证；
  - 下次恢复建议；
  - 是否释放 scope lock。

### 7. Context projection freshness：应成为 ai-board 文档瘦身后的内核

GSD 强的一点是每个 planning 文件都有明确消费者。不是“写很多文档让 AI 读”，而是“不同阶段读不同投影”。

ai-board 现在的 README 和 skill 已经在瘦身，但项目内 docs 还可以更明确地定义：

- 哪个文件给新 agent 接手读；
- 哪个文件给路线规划读；
- 哪个文件给验收审计读；
- 哪个文件是生成视图，不能手改；
- 哪个文件是历史档案，只在回溯时读。

这可以减少 AI 因为提示词太长而漏看关键规则的问题。

## 不建议借鉴的部分

以下机制即使先进，也不建议作为 ai-board 的主方向：

1. **agent runtime / control plane**
   - GSD 想让 AI 代理完成从讨论、规划、执行到验证的完整工作流。
   - ai-board 应保持 agent-agnostic：不接管 Claude、Codex、Cursor 或其他运行时。

2. **多运行时安装器**
   - GSD 的安装器覆盖大量运行时和 skill/command 格式。
   - ai-board 可以保留轻量 skill discovery，不应把主要复杂度放在适配所有 agent。

3. **默认跳过权限确认**
   - GSD 推荐无摩擦自动化。
   - ai-board 的核心是治理和审计，不应鼓励绕过用户安全边界。

4. **重型子代理编排**
   - GSD 通过 orchestrator 拉多个研究、规划、执行、验证 agent。
   - ai-board 可以记录和审计多 agent，但不应内置复杂 executor。

5. **复杂 milestone 平台**
   - ai-board 可以借鉴 phase 和 requirement coverage。
   - 但不应变成 Jira、GSD 或完整项目管理平台。

6. **token / star 营销叙事**
   - ai-board 的对比测试要保留证据和边界，不应把轻量性包装成“全面胜出”。

## 对 ai-board 路线的影响

### 已有 1.0 方向不需要改变

GSD Core 证明的不是 ai-board 应该转向，而是 ai-board 当前 1.0 路线里的几个点确实重要：

- git scope gate：把约束下沉到提交关口。
- verification evidence：不要只信 agent 自述。
- human review：让人快速审计 AI 做过什么。
- schema / migration：长期项目需要可信数据。
- planning intent persistence：关键规划不能只留在聊天里。

ai-board 仍应坚持轻量治理层定位，不做完整 coding agent。

### 0.3 verification evidence 应吸收 UAT / debt 模型

0.3 不应只保存命令输出。更完整的设计应支持：

- automated verification；
- manual verification；
- user UAT；
- deferred verification debt；
- blocked verification。

这样后续 `next` 和 `review` 才能知道“任务完成但验收未闭环”。

### 0.4 human review 应吸收 progress / forensic audit 思路

0.4 的 `review` 不应只是事件列表。它应该回答：

- 最近发生了什么；
- 哪些任务完成了；
- 改了哪些文件；
- 是否越过 scope；
- 验收证据是什么；
- 还有哪些 deferred / blocked verification；
- 当前状态、路线文档和 board 是否一致。

### T-0124 规划意图持久化需要继续工程化

已有 `规划意图持久化与阶段路线检查.md` 是正确方向，但还停留在规则层。

受 GSD 启发，后续应把它推进成：

- 结构化的 roadmap placeholder 约定；
- `next` 路线断档提醒；
- `doctor` 规划覆盖 warning；
- 可选的 requirement / decision coverage 检查。

## 建议新增或调整的任务

建议把以下工作放入需求池或后续版本规划：

1. **设计 workflow guide 拆分：plan / work / verify / review**
   - 目标：让 AI 在不同阶段读取不同短指南，而不是一个长指南背全部规则。
   - 借鉴点：GSD 的 discuss / plan / execute / verify 分段上下文。

2. **评估 roadmap placeholder 与路线断档检查**
   - 目标：看板空时不再丢失后续阶段。
   - 借鉴点：GSD 的 ROADMAP、STATE、progress router。

3. **评估 requirement / decision coverage warning**
   - 目标：规划后检查关键需求和决策有没有被任务或路线文档承接。
   - 借鉴点：GSD 的 requirements coverage gate 和 decision coverage gate。

4. **扩展 0.3 verification evidence：加入 UAT / deferred debt**
   - 目标：区分测试通过、人工确认、用户验收和验证债务。
   - 借鉴点：GSD 的 verify-work、UAT、audit-uat。

5. **评估 pause / resume / handoff note 最小机制**
   - 目标：任务未完成时有比 unlock 或手改 board 更自然的暂停方式。
   - 借鉴点：GSD 的 pause-work / resume-work。

## 最终判断

如果只看机制先进程度，GSD Core 最值得 ai-board 学的不是多 agent 编排，也不是安装器，而是这四件事：

1. **把项目记忆拆成有生命周期的上下文投影。**
2. **让 progress/next 根据产物状态路由下一步，而不是只列任务。**
3. **把需求、决策、计划、验证之间做覆盖检查。**
4. **把验证债务显式记录，不让“完成”掩盖“还没真正验收”。**

这些机制不要求 ai-board 变重。相反，它们能让 ai-board 更像一个治理层：少接管执行，多强化事实源、关口、证据和审计。

因此结论是：

> ai-board 不需要改变项目迭代方向，但需要把 GSD Core 的 planning artifacts、progress router、coverage gate 和 UAT debt 思想吸收进 0.3、0.4 以及规划意图持久化后续任务里。
