# Task / 子任务 T03：成员生命周期与状态观测
最后修改时间: 2026-11-11 16:21:00

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[后端三层职责审视与业务组织调整](../../intent/20261111-backend-responsibility-alignment.md)。
- 权威总计划：[方案修订 1](../../plan/20261111-backend-responsibility-alignment.md)，任务 ID：T03。
- 权威协调根与代码工作区：`D:/SourceCodes/mywork/agent-relay`。依赖、执行编号与仲裁以总计划为准。

## Handoff basis / 交接依据

- 用户已授权自主实施；执行者为主会话，分配编号 ALIGN-T03-20261111-01。接收、基线及前置见本文记录，最终组合见 T07。
- 协议入口为总计划 Coordination 所列 SpecFlow skill 及协作契约；读取总计划对应登记和已接受的前置交付。
- 执行者仅更新本文接收、进展、交付及最后修改时间，不自行调整任务定义或总登记；共享文件按主会话安排顺序写入。
- 在执行会话输出可复制接收/阻塞/交付摘要，由用户转交主会话，不自动发往聊天室。

## Goal and acceptance / 目标与验收

主要结果：成员加入、编辑、退出和状态观测归属于连贯的成员应用能力，领域规则、会话协议与数据库条件分工明确。覆盖 A02—A04、A06—A09 及 R01、R03、R05—R08 的成员部分。

- 成员编辑和删除不再由 RoomService 承担，加入、编辑、退出、候选会话和观测的业务入口有明确归属；固定用户保护、同名/会话冲突和有效订阅规则统一。
- 观测刷新窗口由明确策略提供，仓储只执行改变或超过阈值时的原子条件；保持现有 30 秒、含等号、跨时区比较、NULL 和无变化不重复事件的语义。
- SessionDriver 只提供中立会话事实，Codex 适配器负责原始状态、身份、分页和错误转换，成员用例判断项目归属和可加入性。
- 加入保持短读 → 释放 → inspect → 短写重查；候选/后台观测不改变用户设定的成员名或订阅。HTTP 与 presence runner 使用新能力，旧成员路径移除。

## Inputs and eligibility / 输入与可开始条件

直接前置及版本要求见总计划。消费已接受的成员/会话/观测设计，以及资源初始化和持久化实现；派发时核对实际版本、有效授权/编号和共享文件安排，写入接收事实后实施。

## Scope and files / 范围与文件

- `application/members/{service,sessions}.py` 及按 T01 设计增加的 `contracts.py`、`ports.py`，从 `application/rooms/{service,contracts}.py` 移出的成员部分。
- 领域成员约束、`repositories/rooms.py` 的 save_observation、资源读取和所需 scope；不修改房间初始化和消息发布策略。
- `infrastructure/codex/driver.py` 的 `_session/list_sessions/inspect` 及实际共用协议 helper 的必要部分；不改 enqueue/start/input-history 业务链路。
- presence runner/工厂、HTTP 成员相关 route/provider，及成员 fake、fixture、测试；不处理上下文提供。

## Technical decisions / 局部技术设计

- 成员能力对外组织生命周期，是否保留内部会话协作者由 T01 根据实际职责决定；不建立一组仅互相转发的类来替代一个大类。
- 成员唯一性、固定 human 限制、订阅有效性使用领域规则；原会话/项目身份和并发重查由应用编排；存储约束继续保护最终写入。
- 应用计算观测策略所需阈值或传入明确策略值，仓储保留状态差异、身份、有效成员、时间窗口和更新返回值等数据库判断，并与事件共同保存。
- adapter 将 `notLoaded/idle/active/systemError` 等原始协议状态转换为现有中立事实；对外不可用原因、presence 与活动说明按 T01 决定的责任位置生成，保持当前行为。
- 候选枚举与后台观测共享同一规则来源；runner 的周期、取消与停止机制保留。协议 driver 与投递节点共享，交付时明确哪些 helper 已演进供后续消费。

## Implementation outline / 实施安排

1. 明确并提取成员约束与观测策略，统一成员契约及应用入口。
2. 调整 SQL 观测输入，保留原子条件、UTC/偏移时间语义和事件行为。
3. 核对会话 adapter 分工，接通 HTTP、presence 工厂与消费者，删除旧成员实现。
4. 完成轻量用例、协议转换和存储/RPC 边界检查，交付发布身份与资源访问能力。

## Checks and delivery / 检查与交付

- 纯业务检查覆盖 `tests/unit/test_member_binding.py`、相关成员规则及必要的编辑/退出/观测用例：特别验证 RPC 时无存储作用域、写前重查、固定用户限制和成员元数据不被观测覆盖。
- 定向入口：`uv run --locked pytest -o addopts=-ra tests/integration/test_member_sessions.py tests/integration/test_user_members.py tests/integration/test_codex_driver.py tests/integration/test_room_repository.py tests/integration/test_persistence_runtime.py -q`。
- 观测时间边界继续复用 `test_sqlalchemy_foundation.py` 的等值/时区/NULL 覆盖，改变调用契约时相应运行；保证无变化与阈值判断不被简单时间字符串比较替代。
- 更新对应类型/fake/夹具，完成受影响模块必要静态检查；记录实际前置版本、文件清单、结果及未运行原因，附供 T04/T06 消费的会话与成员接口。

## Risks / 风险

- 同一会话可服务跨房间业务，不能因为整合成员类新增错误的全局业务限制。
- 仅把 30 秒常量移动到 domain 不足以说明责任，必须明确策略与执行条件；不能为集中规则增加额外长事务。
- driver、RoomState 与 HTTP route 为共享文件，超出会话部分的必要修改先向主会话说明。

## Reception and progress / 接收与进展

2026-11-11 主会话接收 ALIGN-T03-20261111-01/rev1；用户自主实施授权，HEAD 03b45fd 工作区包含已接受 contracts-v1 和 resources-v1，前置及局部检查可访问。成员/观测规则、会话边界和对应接线按范围实施，保留其他链路与独立 web 修改。

## Delivery and review / 交付与审查

2026-11-11 ALIGN-T03-20261111-01/rev1 交付 ALIGN-members-v1。MemberService 统一加入、编辑、退出和观测；成员 DTO 迁至 members/contracts；领域成员规则及 observation_cutoff 提供策略，仓储接受显式阈值保留 inclusive julianday 和 UPDATE 条件；HTTP/presence 正式接通。Codex 会话解码/分页/身份转换属于协议适配，审视后保留。测试端以 RoomWorkflow 组合多个真实业务服务供跨链路场景使用，生产不保留旧转发方法。5 unit、83 integration（24.54s）、mypy src tests 127 文件通过；无阻塞或业务范围偏差，最终格式检查待集成。主会话审查后接受，前置 contracts-v1/resources-v1 有效。
