# Task / 子任务 T07：正式集成与三层职责核验
最后修改时间: 2026-11-11 16:34:20

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[后端三层职责审视与业务组织调整](../../intent/20261111-backend-responsibility-alignment.md)。
- 权威总计划：[方案修订 1](../../plan/20261111-backend-responsibility-alignment.md)，任务 ID：T07。
- 权威协调根与代码工作区：`D:/SourceCodes/mywork/agent-relay`；依赖、执行登记和交付仲裁只以总计划为准。

## Handoff basis / 交接依据

- 用户已授权自主实施；执行者为主会话，分配编号 ALIGN-T07-20261111-01。接收、基线及前置见本文记录，最终组合见下文。
- 协议入口为总计划 Coordination 的 SpecFlow skill 与协作契约；方案 Accepted 不能替代实现交付接受或阶段授权。
- 执行者可写本文接收、进展、交付与最后修改时间，不自行将 task 或总登记置为接受；架构说明按本节点产品范围维护。
- 接收、阻塞和交付在执行会话回报可复制摘要，由用户转交主会话；不自动向聊天室发送。完成开发集成不自动进入整体 Verification。

## Goal and acceptance / 目标与验收

主要结果：当前有效交付在正式装配中组合成立，并有完整三层职责对应、开发检查与可供整体 Verification 使用的快照。覆盖全部 A01—A10 和 R01—R08 的集成核对。

- T01—T06 的接受版本与当前组合一致；上游演进没有让已接受下游过时，所有前置实际产物可访问，必要开发检查完成或有明确未执行说明。
- 房间/话题、成员、消息、上下文与投递正式路径均调用各自应用能力；简单读取直接使用所需查询端口，provider 与 bootstrap 不补写业务决策。
- 旧整用例仓储、旧 service 方法、重复 Protocol、无用事件/类型和内部旧导入依照 T01 决定完成处理，无长期双路径；不把必要 SQL 原子操作当作残留业务误删。
- 架构说明以真实调用链解释决策者、用例与技术实现，逐项记录 R01—R08 的处理结果、文件、证据及保留理由；A01—A10 均有结果。
- 公开接入、数据库/编码、共享事务、RPC/流式边界、并发竞争、未知结果和资源生命周期保持；当前最终快照有真实开发检查记录。

## Inputs and eligibility / 输入与可开始条件

直接依赖与版本条件只查总计划。需要其列明的全部已接受实现及传递输入，派发前复核当前 HEAD、组合差异、局部检查和无关修改。若缺少核心能力或上游实现未满足验收，退回所属节点/主会话处理，不将未完成核心业务归入集成补丁。

## Scope and files / 范围与文件

- `bootstrap/http.py`、相关 infrastructure 能力工厂、HTTP provider/route 和其他入口的剩余组合调整。
- `docs/design/backend-architecture.md` 更新为实际目录、责任、调用链和生命周期说明；不改独立 `docs/design/codex-integration-capabilities.md`。
- `tests/room_fixtures.py`、`tests/session_fixtures.py`、`tests/sqlalchemy_message_fixtures.py`、必要 fake 和生产装配边界/入口测试；本节点只补组合证据，不延迟接管各节点本应交付的测试。
- 可精确删除已无消费者的本任务旧路径；共享契约或核心流程新增变更先由主会话判断返工/修订。不修改前端、历史迁移、真实库或运行服务。

## Technical decisions / 局部技术设计

- 逐条走查目标用例的领域决策、应用编排和基础设施动作，静态导入通过不能代替职责审查；同时核对接口返回值不含 ORM/Session 或原始协议对象。
- 统一事务仍使用既有 Database/SQLAlchemyTransaction。HTTP 请求在成功响应开始前提交；独立短动作完成后才 RPC；WebSocket 每次补取短读，等待时不持有 Session。
- 借入 Database 由调用方关闭，自建 Engine 在 runner 停止/锁释放后 dispose；构造、启动、提交、取消失败路径同样检查。
- 工厂和 provider 只连接对象、选择适当作用域；业务默认值、状态转换、授权策略不迁入装配代码。
- 最终清单包含本任务文件和必要背景文件的实际版本，删除项明确标记；证据与组合快照关联，不使用旧 474 项结果替代本次检查。

## Implementation outline / 实施安排

1. 核对当前有效交付、传递输入及共享文件组合，发现失效版本回报主会话。
2. 完成剩余正式接线、消费者与旧路径清理，验证每条能力不依赖临时适配。
3. 更新架构说明和 R01—R08 结果，检查 A01—A10 对应证据及范围差异。
4. 按最新授权执行完整开发检查，记录最终清单、风险与未完成项，提交主会话审查。

## Checks and delivery / 检查与交付

计划使用现有项目入口，届时依用户最新要求执行并记录；本次编写 task 没有执行下列命令：

- `uv run --locked pytest tests/unit -q`：默认业务测试不依赖临时 SQLite、FastAPI 或模拟协议子进程。
- `uv run --locked pytest -o addopts=-ra tests -q`：完整后端回归，包含临时库、HTTP/WS、CLI/MCP、模拟协议、后台竞争及正式装配边界。
- `uv run --locked mypy src tests`、`uv run --locked mypy migrations`、`uv run --locked ruff check .`、`uv run --locked ruff format --check .`。
- `git diff --check`、`git diff --cached --check`：保留已有暂存状态，不自动格式化范围外文件或 Git 暂存。
- 静态核对所有旧路径引用、domain/application 依赖方向及 DTO 边界；逐项审查事务、投影、条件更新、driver/runner 和关闭的实际调用链。
- 不运行含独立前端工作的 `make test/check` 作为本任务门槛，不访问真实服务、Codex 会话或开发库。未执行项如实记录原因和结论边界。

交付形成本文的 R01—R08 与 A01—A10 对应表、实际文件/版本清单、检查结果和剩余风险，供主会话审查并在用户要求后进行整体 Verification；不预先创建验收通过结论。

## Risks / 风险

- 所有节点各自通过不代表组合成立；共享模型、作用域、driver 和夹具的后续修改必须复核前置有效性。
- 全局格式或测试失败可能来自独立变更，需明确归属并协调，不越界修复或把失败记成通过。
- 架构说明应反映最终代码，不能把规划目录或未使用抽象描述为已落地。

## Reception and progress / 接收与进展

2026-11-11 16:18:10 主会话接收 ALIGN-T07-20261111-01/rev1。实际 HEAD 03b45fd，已复核当前工作区包含 contracts-v1（签名去重在集成中补正）、resources-v1、members-v1、messages-v1、context-v1、delivery-v1 及局部检查；原冻结实现因统一 scope/视图导入/接口拆分合法演进，最终组合统一核对。独立 web/视觉过程文档保持，按用户自主实施授权完成开发检查与架构说明，不进入整体 Verification。

## Delivery and review / 交付与审查

2026-11-11 16:21:00，主会话提交并审查接受 ALIGN-integrated-v1（ALIGN-T07-20261111-01/rev1）。实际组合以 HEAD `03b45fd632f25d0a051dc0de76a4035b1035988a` 的工作区改动为准，包含已接受 T01—T06 及契约补正 ALIGN-contracts-v1.1；T05 对共享 scope、视图及消费者的演进已纳入组合重验，无上游失效。更新 [架构说明](../../design/backend-architecture.md)，核对各业务入口、事务所有者和旧路径；测试专用 RoomWorkflow/ContextWorkflow 只是多服务夹具，不存在于产品装配。

本任务修改后端源码、相关测试与架构说明，删除旧上下文入口；独立视觉文档和 `web/` 修改不属于本任务。

完整开发检查：`uv run --locked pytest tests/unit -q` 47 passed；`uv run --locked pytest -o addopts=-ra tests -q` 488 passed（82.95s）；`uv run --locked mypy src tests` 141 文件、`uv run --locked mypy migrations` 2 文件、`uv run --locked ruff check .`、`uv run --locked ruff format --check .` 216 文件、`git diff --check` 与 `git diff --cached --check` 全部通过。AST 检查 97 个产品 Python 文件，application/domain 无反向依赖；27 个公开业务/上下文 Pydantic 类与 HEAD 的 AST 定义一致。实际快照、当前验收、独立修改和真实环境限制另见整体验证报告。

| 审视项 | 实际结果与证据 |
| --- | --- |
| R01 | rooms/member/messages 各有实际用例，HTTP 和 presence 正式接线；对应 resource、member、message 单元/集成检查 |
| R02 | ContextService.provide 组织副作用流程，旧整用例仓储/适配已删除；上下文 80 项定向集成及纯用例检查 |
| R03 | 资源初始化、成员约束/观测、路由、可见性/位置及投递结果归领域；条件更新仍在 SQL，纯业务 47 项与并发集成检查 |
| R04 | Pydantic 业务值复用且公开类定义不变；TopicPosition 移至应用视图，Delivery 保留业务/回执事实，删除未使用 RoomChange |
| R05 | 固定用户/默认话题由领域生成并显式传仓储，观测 cutoff 与投递有效状态由领域提供；资源与 SQL 边界检查 |
| R06 | RepositoryScope/SQLAlchemyScope 复用统一事务，RoomStore 组合能力，投递具体 Store 保留短作用域；只读 Query 和内部批量 loader 保留；空 Protocol 删除 |
| R07 | 领域表达提交结果、DeliveryService 组织动作、Codex adapter 承担协议和身份、runner 管锁/调度/并发；102 项投递定向回归 |
| R08 | 请求提交者、独立短事务、RPC/WS 前释放和资源所有权保持；正式 persistence_runtime 与完整回归覆盖 |

| 验收 | 组合证据 |
| --- | --- |
| A01/A10 | 上表覆盖 R01—R08，架构说明和各 task 记录实际责任、抽象与保留理由 |
| A02/A03 | 领域规则、应用用例及无反向依赖静态扫描；47 个纯业务测试 |
| A04/A05 | 上下文/投递 SQL 条件、分页前可见性及实际提供/位置/事件事务；对应竞态、回滚与查询批次集成测试 |
| A06/A07 | 投递定向 102 项、正式装配测试和完整回归；仅临时 SQLite 与模拟协议进程 |
| A08/A09 | 27 个公开模型 AST 一致，HTTP/WS、CLI/MCP、消息/资源等完整后端 488 项及类型/格式检查通过；不包含独立前端验证 |

实现阶段未操作真实数据库/服务/Codex，未进行 Git 写入或前端检查。用户随后明确授权整体验证，结论见[验证报告](../../verification/20261111-backend-responsibility-alignment.md)。
