# 更新日志

`ai-board` 的重要版本变化会记录在这里。以后 Release 说明和更新日志默认使用中文。

## v0.2.0 - 待发布

这个版本把 scope 约束从 `doctor` 的事后发现推进到 git 提交关口。它仍然不是运行时文件拦截或安全沙箱，而是在 commit 前检查 staged diff 是否落在 active task scope 内。

### 新增

- 新增 `scope_gate=off|suggest|required` 项目配置。默认 `suggest` 只提醒；`required` 会让 gate 在发现越界 staged 文件时返回非零。
- 新增 `ai-board gate pre-commit`，按 staged diff、active task scope 和 ai-board 记账副作用规则检查本次提交。
- 新增 `ai-board hooks install pre-commit`、`ai-board hooks status`、`ai-board hooks uninstall pre-commit`。
- pre-commit hook 使用 ai-board managed marker；遇到用户已有 foreign hook 时不会覆盖，只输出人工合并片段。
- `doctor` 会检查 `scope_gate=required` 下 hook 是否缺失、非托管或不可用；`suggest` 模式只提醒，不作为失败项。

### 调整

- README、README_en 和 `ai-board skills get core` 会说明 scope gate 是 git 提交关口，不是运行时文件拦截；标准 Git 仍允许通过 `--no-verify` 绕过本地 hook。
- ai-board 自身记账副作用继续不要求写进业务 task scope；scope gate 只检查业务 staged 文件。

### 测试

- 补充 staged diff scope gate 回归：无 active task、合法 scope、根 scope、前缀陷阱、过期锁、rename/delete、记账副作用和真实 git index。
- 补充 hook 命令回归：安装、状态、卸载、foreign hook 不覆盖、required 模式 doctor fail / managed hook pass。

### 发布前验证

- `uv run ai-board conflicts --fail-on-conflict`
- `uv run ai-board doctor --fail-on-issue`
- `uv run --with ruff ruff check .`
- `uv run python -m unittest discover -s tests`
- `uv run --python 3.12 --with build python -m build`
- `uv run --with twine twine check dist/*`

## v0.1.20 - 2026-06-03

这个版本根据真实使用反馈，重点收窄 AI 默认接手提示，并把容易漏读的项目治理规则前置到 CLI 输出里。

### 调整

- `ai-board skills get core` 默认输出改为约 80 行的接手检查单：优先提醒 onboarding、git 检查、`next`、生成 Markdown 源关系、blocked 复核、排期/start、验收/归档等第一屏动作。
- 详细工作流、notice 响应协议和命令参考继续保留在 `ai-board skills get core --full`，避免默认提示词过长导致 agent 忽略关键动作。
- `next` 和 `doctor` 在非 git 项目中会给出编码前 git 检查建议：确认项目根、初始化 git、补 `.gitignore`、创建初始提交，但仍不静默执行 `git init`。
- `next` 和 `doctor` 发现 blocked 任务时会提示先复核，而不是按时间久远自动归档；只有确认需求废弃、被替代、已满足或不再符合当前方向后才 archive，仍需继续则 reopen 后重新排期。
- 当项目方向发生变化时，默认 guide 会提醒先复核 inbox、scheduled 和 blocked 任务，再启动新的实现任务。
- AI 指南和 README 已明确 task `scope` 描述业务修改范围；`.ai-board/board.json`、事件/消息日志和生成看板的自动更新属于 ai-board 自身记账副作用，不需要每次写进业务 scope。

### 测试

- 补充默认 guide 瘦身、`--full` 细节保留、blocked 复核、git 接手提醒、scope 副作用说明的回归测试。

### 发布前验证

- `uv run ai-board conflicts --fail-on-conflict`
- `uv run ai-board doctor --fail-on-issue`
- `uv run --with ruff ruff check .`
- `uv run python -m unittest discover -s tests`
- `uv run --python 3.12 --with build python -m build`
- `uv run --with twine twine check dist/*`

## v0.1.11 - 2026-05-30

这个版本主要修补真实多 agent 使用中暴露出的协作防撞和任务收口缺口，让 agent 更少被迫手改 `.ai-board/board.json`。

### 修复

- 修复根 scope `.` 与子路径不被判定为冲突的问题。现在 `.` 会作为整个项目处理，与 `src`、`docs`、具体文件等任意子路径重叠。
- `next` 复用核心 scope 冲突判断，避免候选任务判断和 `start` / `conflicts` 出现两套结果。
- blocked 任务现在可以通过 CLI 正常收口：过期或不再处理的 blocked 任务可直接 `archive`，需要继续处理的 blocked 任务可 `reopen --reason` 回到 scheduled。

### 调整

- `ai-board skills get core` 已把 stale blocked 清理规则提前到 compact prompt 和 rules of thumb：不要手改 `board.json`，该归档就 `archive`，要继续就 `reopen --reason`。
- 保持 blocked 任务不能直接 `complete`，避免跳过重新启动和验收。

### 测试

- 补充协作防撞安全回归：根 scope 变体规范化、根锁阻塞 start/rescope、force 后由 `conflicts` / `doctor` 报告、过期根锁释放阻塞、solo 模式显式冲突揭示、`next` 对候选和验证范围的提示。
- 补充 blocked 生命周期测试和 AI guide 规则测试。

### 发布前验证

- `uv run ai-board conflicts --fail-on-conflict`
- `uv run ai-board doctor --fail-on-issue`
- `uv run --with ruff ruff check .`
- `uv run python -m unittest discover -s tests`
- `uv run --python 3.12 --with build python -m build`
- `uv run --with twine twine check dist/*`

## v0.1.1 - 2026-05-30

这个版本主要修正 active 任务中途调整 scope 时的协作体验，避免 agent 为了释放锁被迫手改 `.ai-board/board.json`。

### 新增

- 新增 `ai-board rescope TASK --agent AGENT --scope ...`：active 任务中途需要缩小、扩大或恢复 scope 时，可以通过 CLI 更新范围并重新加锁。
- `rescope` 支持同步更新 `--verify-scope`，用于把写入范围和验收范围一起说清楚。
- 新增 `-v` / `--version`，可直接输出当前 CLI 版本。

### 调整

- `unlock` 不再清空任务 scope，只释放 `lock_owner` 和租约；scope 继续作为任务历史保留。
- 冲突检测、`locks`、`next` 和 onboard lock notice 只把带有效 `lock_owner` 的 active task 视为占用锁；已 unlock 的 active task 不再挡住其他任务。
- `doctor` 在发现 active task 没有 scope 时，会提示可执行的 `rescope` 修复命令。
- `ai-board skills get core` 已补充 rescope / unlock 的协作说明，减少 agent 手改 JSON 的概率。

### 发布前验证

- `uv run ai-board conflicts --fail-on-conflict`
- `uv run ai-board doctor --fail-on-issue`
- `uv run --with ruff ruff check .`
- `uv run python -m unittest discover -s tests`
- `uv run --with build python -m build`
- `uv run --with twine twine check dist/*`

## v0.1.0 - 2026-05-29

首个正式版本。这个版本把前几个 alpha 中验证过的 AI 原生项目接手、任务看板、事件日志、doctor 自检、可选多 agent 协作和发布流程合并成一个不带预发布后缀的版本。

### 新增

- 新增项目级 `multi_agent_enabled` 开关：新项目默认关闭多 agent 协作提示和 scope 冲突强拦截；需要并行 AI 开发时通过 `ai-board config set multi_agent_enabled true` 单独开启。
- 新增项目级 `git_integration` 配置：默认 `suggest`，onboard / doctor 会建议无 git 项目先初始化以便回滚，但不会静默运行 `git init` 或自动提交用户已有改动；可切到 `required` 或 `off`。
- `doctor` 增加 git 集成状态检查：`suggest` 只提示不失败，`required` 会在无 git 时失败，`off` 跳过。

### 调整

- README / README_en 改为正式版 `v0.1.0` 口径，不再把当前版本称为 alpha。
- `ai-board skills get core` 明确 solo 默认、多 agent opt-in，以及 git-first 但不静默初始化的工作方式。
- 保留 alpha 阶段已经验证的能力：onboard 方向门禁、JSON 真相源、Markdown 渲染、事件日志、notice inbox、scope lock、共享验证资源、Claude 多进程实测流程和发布 workflow。

### 发布前验证

- `uv run ai-board conflicts --fail-on-conflict`
- `uv run ai-board doctor --fail-on-issue`
- `uv run --with ruff ruff check .`
- `uv run python -m unittest discover -s tests`
- `uv run --with build python -m build`
- `uv run --with twine twine check dist/*`

## v0.1.0-alpha.4 - 2026-05-18

第四个 alpha 版本，重点修正新项目接手门禁和 agent skill 安装口径，避免 AI 根据目录名或少量文件自顾自写方向规划。

### 调整

- `onboard` 对空项目和轻量新项目增加 `STOP` 方向确认门禁：目录名、文件名和少量 evidence 只能作为待确认假设。
- `ai-board skills get core` 明确 hard direction gate：用户确认目标、受众、初版范围和现有文件权威性前，不得写正式路线、排实现任务或开始编码。
- `docs/项目方向.md` 初始化模板增加“状态：未与用户确认”、已确认事实、待确认假设和需要询问用户的问题。
- README / README_en 和内置 guide 的安装提示词改为：应按目标 agent 的 skill 安装方式放置 `skills/ai-board/SKILL.md`，除非该 agent 已经安装过；不再写成“如需 agent skill”的可选口径。
- 已修正 GitHub 上 `v0.1.0-alpha.3` Release 的标记：不再作为 Pre-release，并显式显示为 Latest。

### 发布前验证

- `uv run ai-board conflicts --fail-on-conflict`
- `uv run ai-board doctor --fail-on-issue`
- `uv run --with ruff ruff check .`
- `uv run python -m unittest discover -s tests`
- `uv run --with build python -m build`
- `uv run --with twine twine check dist/*`

## v0.1.0-alpha.3 - 2026-05-15

第三个 alpha 版本，重点补齐多 agent 协作收口、notice 响应流程、共享验证资源、scope 误用防线和发布前口径一致性。

### 新增

- 新增 `config list/get/set`，通过 CLI 校验并读写 `.ai-board/config.json`，避免 agent 直接手改配置。
- 新增 `reopen`，done 或 archived 任务验收后发现没做完时可带原因回到 scheduled。
- 新增 `tell` / `inbox` 轻量 agent notice：支持点对点和 `all` 广播、ack、resolve。
- 新增 `inbox --fail-on-unresolved`，可作为监工或 CI 的协作消息收口检查。
- 新增共享验证资源规则和 `verify_scope` / `deferred_verification`，用于记录局部验证和等待全量验收的原因。
- 新增 `start --scope` 空格歧义检查：包含空格但不是现有路径的单个 scope 参数会被拒绝，降低多个路径误合并的风险。

### 调整

- `doctor` 增加业务健康检查：active 任务停滞、过宽 scope、空 acceptance、agent lease 即将到期、共享验证资源长期占用、生成看板 stale、事件日志 fallback 等。
- `ai-board skills get core` 增强多 agent 指南：要求同一任务保持同一个 agent 身份、按 notice 响应流程处理消息，并在 `inbox --fail-on-unresolved` 非零时不得视为干净收口。
- CLI i18n 第二轮整理：常见业务错误和 doctor issue 在 `zh-CN` 下输出中文说明，JSON 字段、状态枚举和事件名继续保持英文。
- 已完成 Claude 多进程协作实测和复测，验证 scope lock、notice 收口检查和 scope 空格误合并防线在真实 agent 协作中可用。
- README / README_en 和版本说明改为 `v0.1.0-alpha.3` 口径，补充轻量 agent notice 的能力边界。

### 当前边界

- 仍是 alpha 版本，暂不承诺稳定 API。
- scope lock 仍是路径级防撞，不做 glob、文件级强制锁或语义冲突判断。
- agent notice 是轻量提醒和收口检查，不是实时聊天系统，也不会自动改变任务状态。
- `ai-board render` 不是后台监听；正常 CLI 写操作会自动渲染，手动 render 作为修复按钮保留。
- PyPI 发布依赖 GitHub Actions 和 PyPI Trusted Publishing 配置。

### 发布前验证

- `uv run python -m unittest discover -s tests`
- `uv run --with ruff ruff check .`
- `uv run --with build python -m build`
- `uv run ai-board doctor --fail-on-issue`
- `uv run ai-board conflicts --fail-on-conflict`

## v0.1.0-alpha.2 - 2026-05-15

第二个 alpha 版本，重点补齐 AI 原生协作闭环、中文 CLI 体验、发布自动化和 PyPI 发布准备。

### 新增

- 新增 `ai-board next`，用于新 agent 接手时读取 active owner、scope lock、lease、生成看板 stale 状态，并推荐不冲突候选任务。
- 新增 CLI 中文输出第一版：可通过 `AI_BOARD_LANG=zh-CN` 或 `--lang zh-CN` 切换人类可读输出。
- 新增中文帮助页和常见参数错误提示；`ai-board -h` 可在中文环境下显示中文命令说明。
- 新增 `ai-board lang`，默认输出 `zh-CN` 的 PowerShell、cmd 和 bash/zsh 环境变量切换提示。
- 新增 `ai-board skills` 裸调默认列出内置 AI 使用指南。
- 新增 `show` 的人类可读默认输出，仍可用 `--format json` 输出结构化 JSON。
- 新增事件日志写入失败 fallback：写失败时输出 warning，并写入 `.ai-board/events.failed.jsonl` 供 `doctor` 提醒。
- 新增过宽 scope 提醒：默认把 `.`, `src`, `docs`, `tests` 视为偏宽 scope，提示 agent 优先使用具体文件或小目录。
- 新增计划看板自动渲染回归测试，覆盖主要 CLI 写操作刷新 Markdown 生成视图。
- 新增 GitHub Actions 发布 workflow，支持通过 PyPI Trusted Publishing 发布包。

### 调整

- 仓库里的 `skills/ai-board/SKILL.md` 收窄为 discovery stub，完整流程以 `ai-board skills get core` 为准，避免 skill 内容和 CLI 版本漂移。
- `ai-board onboard` 会显示当前 active task 的 owner、scope lock、lease 和避让提醒。
- `schedule` / `start` 遇到已 active 任务时，错误信息会带 owner、scope 和 lease，减少新 agent 抢占任务的误判。
- README 和内置 guide 统一说明：CLI 写操作会自动渲染 Markdown 看板，`ai-board render` 是配置变更、拉取后修复或 stale 提示时的兜底命令。
- README FAQ 和版面做了轻量整理，澄清 JSON 是真相源、Markdown 是生成视图、ai-board 不保存聊天上下文。

### 当前边界

- 仍是 alpha 版本，暂不承诺稳定 API。
- scope lock 仍是路径级防撞，不做 glob、文件级强制锁或语义冲突判断。
- `ai-board render` 不是后台监听；正常 CLI 写操作会自动渲染，手动 render 作为修复按钮保留。
- PyPI 发布依赖 GitHub Actions 和 PyPI Trusted Publishing 配置。

### 发布前验证

- `uv run python -m unittest discover -s tests`
- `uv run --with ruff ruff check .`
- `uv run python -m build`
- `uv run python -m ai_board doctor --fail-on-issue`
- `uv run python -m ai_board conflicts --fail-on-conflict`

## v0.1.0-alpha.1 - 2026-05-14

首个可试用 alpha 版本。

### 新增

- 新增 AI 原生接手流程：`ai-board onboard --init-if-missing`。
- 使用 `.ai-board/board.json` 作为本地唯一真相源。
- 自动生成 Markdown 看板视图到 `docs/`。
- `ai-board init` 可生成 AI 原生开发规范文档。
- 任务工作流命令：`add`、`schedule`、`start`、`complete`、`archive`、`block`、`status`、`show`。
- Agent 身份池：`agents claim`、`agents list`、`agents release`。
- 路径级 scope lock、锁租约、`renew`、`unlock`、`locks` 和冲突检查。
- 任务泳道、来源、验收标准和简单依赖校验。
- `.ai-board/events.jsonl` 事件日志和 `history` 命令。
- `doctor` 项目健康检查。
- `.ai-board/config.json` 项目配置，支持默认语言、默认泳道、默认 agent 类型和默认租约。
- 生成看板支持中文 / 英文基础文案。
- `ai-board skills get core` 内置 AI 使用说明。
- GitHub Actions CI：ruff、Python 3.10/3.11/3.12 单元测试、wheel/sdist 构建。

### 调整

- 业务层预期错误改为使用 `BoardError`，不再主要依赖 `SystemExit`。
- `complete` 会释放任务拥有者的 agent 身份，同时保留任务历史 owner。
- scope 路径会做规范化，并拒绝绝对路径和跳出项目根的路径。
- `board.lock` 写入元数据，并支持 stale lock 恢复。
- Python 包元数据使用 `license = "MIT"`。

### 当前边界

- 这是 alpha 版本，不是稳定工作流引擎。
- scope lock 是路径级防撞，不理解代码语义。
- 依赖校验保持简单，不提供完整 planning graph。
- 暂未包含 SQLite 存储、`reopen`、更完整的 agent 恢复、PyPI 发布和静态类型检查。

### 发布前验证

- `ruff check .`
- `python -m unittest discover -s tests`
- `python -m build`
- `ai-board doctor --fail-on-issue`
- `ai-board conflicts --fail-on-conflict`
