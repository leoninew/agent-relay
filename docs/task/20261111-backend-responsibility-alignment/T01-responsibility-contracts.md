# Task / 子任务 T01：三层职责审视与共享契约基线
最后修改时间: 2026-11-11 16:34:20

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[后端三层职责审视与业务组织调整](../../intent/20261111-backend-responsibility-alignment.md)。
- 权威总计划：[方案修订 1](../../plan/20261111-backend-responsibility-alignment.md)，任务 ID：T01。
- 权威协调根与代码工作区：`D:/SourceCodes/mywork/agent-relay`。依赖、执行者、有效分配及仲裁以总计划为准；方案 Accepted 不表示交付已接受。

## Handoff basis / 交接依据

- 用户已授权自主实施；执行者为主会话，分配编号 ALIGN-T01-20261111-01。接收、基线及前置见本文记录，最终组合见 T07。
- 协议入口：总计划 Coordination 所列 SpecFlow `SKILL.md` 和 `references/task-coordination.md`。
- 调查参考基线为 `03b45fd632f25d0a051dc0de76a4035b1035988a`；派发时在总登记核实实际 HEAD、无关修改、授权和有效编号。
- 以后执行者可写本 task 的设计交付补充、接收、进展、交付章节及最后修改时间；不自行改总计划、方案状态或下游定义。设计结论由主会话审查后同步到方案。
- 默认在执行会话输出可复制摘要，由用户转交当前主会话；不自动向聊天室发送。

## Goal and acceptance / 目标与验收

主要结果：一份能够作为后续实现依据的三层职责与共享契约基线，不修改产品代码。覆盖 A01、A02、A04、A07、A10 的设计基础及全部 R01—R08。

- 为每个 R 项记录当前事实、具体调用者、业务决策/事实读取/技术保护的区别、目标责任、保留/迁移/合并/删除决定及实施节点；不只给出目录树或建议列表。
- 给出资源、成员、消息、上下文、投递的最小类型与端口签名，包括返回值、失败语义和读写/事务性质；后续节点不需要重新猜测上下文如何原子记账或状态由谁决定。
- 对 `RoomModel` 的编码、`TopicPosition` 的投影字段、`Delivery` 的状态/外部事实、`RoomChange`、重复 Protocol 逐项给出决定和实际消费者，不机械建立三套 DTO。
- 用文字或伪代码走查创建房间、加入成员、发布/幂等、清队列、提供上下文、投递/确认与关闭的目标链路，指出唯一提交者、外部等待边界及 SQL 竞争条件。
- 输出共享文件与类型的修改归属、删除清单、每节点必要检查、契约演进顺序和所有未解决项；影响下游的决定不得悬空后声称可实施。

## Inputs and eligibility / 输入与可开始条件

直接依赖查总计划任务定义表。本节点无前置交付，但仍需方案接受、覆盖调查执行的阶段授权、有效分配和接收记录。读取当前意图/计划、架构说明和前轮 SQLAlchemy 验证限制，核对实际源码及相关测试，不沿用旧问题清单代替调查。

## Scope and files / 范围与文件

- 只读 `domain/rooms/`、`application/`、`infrastructure/{persistence,codex,dispatch}/`、相应 interfaces/bootstrap 和测试消费者。
- 交付设计写在本文新增的设计交付补充及交付章节，不另建独立 Spec 阶段文档；如需修订总方案，提交具体修改建议，由主会话统一更新。
- 不修改产品代码、测试、配置、公共夹具、历史任务或独立 web/design 工作；不调用真实库、HTTP 服务或 Codex。

## Technical decisions / 局部技术设计

- 调查矩阵至少包含：现位置、调用者、规则内容、所需事实、并发/事务约束、目标位置、接口输入输出、处理理由、验收归属。
- 规则归属以业务语义和变化原因判断；DB 最终唯一性、身份条件、原子领取、单调更新与 SQL 可见性筛选不因规则抽取而删除。
- 作用域契约复用统一 Database/事务基础，区分请求借用和独立短作用域。上下文的读取、记录、位置更新需可在同一作用域组合，不能继续把整用例仅命名为 Repository.query，也不新增模块 UoW。
- 状态责任表区分合法业务状态、转换触发者与 SQL 的旧状态/删除标记/身份条件；观测刷新窗口区分策略取值与存储条件实现。
- 只读 Query 可直接返回投影；多阶段上下文提供属于应用用例。协议原始字段与错误留在适配器，应用所需事实使用明确中立值。
- 当前目录决策按总计划，若调查证据要求变化，记录理由、受影响节点与完整签名，由主会话仲裁；不自行宣布接受或开始实施。

## Implementation outline / 实施安排

1. 核对实际基线与代表调用链，逐项补齐 R01—R08 事实和消费者。
2. 绘出业务决策、应用编排和技术动作的对应关系，列出目标类型、端口和提交所有者。
3. 走查关键成功、失败、空结果和竞争场景，检查契约能保持原行为。
4. 明确下游文件归属、删除/合并与接线顺序，提交设计交付供主会话接受。

## Checks and delivery / 检查与交付

- 使用静态源码、调用引用和现有测试断言核对；不执行产品测试或真实协议探测。只读设计交付的产品类型/lint/测试检查注明不适用，不能填“通过”。
- 接受依据为八项 R 全覆盖、签名和类型可实现、事务/分页/竞争条件无缺口、下游可按范围实施、无遗漏验收归属。
- 交付版本为本文设计补充，记录调查的实际基线、涉及范围与背景修改。与产品实现版本明确区分。

## Risks / 风险

- 调查节点必须产出可执行设计，避免只重复意图或把所有选择延后；必要时建议修订下游边界，由主会话决定。
- 保留适当技术复杂性，不能把所有领域类型分离或移动所有 SQL 条件当作目标；任何保留决定需有消费者或约束依据。

## Design delivery supplement / 设计交付补充

设计版本 ALIGN-contracts-v1；基于 HEAD 03b45fd 及当前源码、测试调用者完成调查，无产品改动。

| 项 | 决定与实现归属 |
| --- | --- |
| R01 | RoomService 仅房间/话题，MemberService 统一成员生命周期，MessageService 负责发布/幂等/队列；迁移正式消费者，删除旧转发方法 |
| R02 | ContextService.provide 通过统一 RepositoryScope 编排 subscriptions、select_messages、position_updates、record_provision、positions；仓储删除完整 query 用例 |
| R03 | domain/rooms/resources.py 管初始化/话题，members.py 管成员约束/变更/观测窗口，rules.py 保留路由/发布规则，delivery.py 管状态集合及提交结果 |
| R04 | 保留 Pydantic/camelCase 共享业务值；TopicPosition 是 later_count 读取投影，迁至 application/rooms/views.py；Delivery 的标识/回执保留事实与编码；删除未使用 RoomChange，保留 Kind |
| R05 | insert_room 显式接收 fixed user 值，默认用户/话题由领域工厂生成；save_observation 接收按领域策略计算的 refresh cutoff；状态集合来自领域 |
| R06 | application/transactions.py 提供 RepositoryScope[T].read/write，SQLAlchemyScope[T] 复用统一 Session 机制；RoomStore 保留有效的 queries 与组合 RoomData，read_rooms/write_rooms 改为 read/write；删除 DeliveryStore 空 Protocol，保留有独立短动作价值的具体适配 |
| R07 | DeliveryService 管恢复/提交/启动/核验，领域转换结果；runner 保留锁/调度/并发、恢复调用应用。现有 Codex RPC、技能绑定、身份校验、状态转换经审视属协议责任，保留。历史游标由进程级应用服务拥有，同 session 观测由 runner 防重复调度 |
| R08 | 请求中间件唯一提交；上下文用独立短写 RepositoryScope；成员/清理 RPC 先退出本地作用域。Database、锁、runner 所有权与关闭顺序保持 |

冻结签名：RepositoryScope[T].read()/write() → AbstractContextManager[T]；ContextRepository.subscriptions(room, member) → set[str]；select_messages(room, member, request, scope) → (messages, more)；record_provision(room, member, request, messages, updates, query_id, now) → None；catalog/positions 为纯读取。ContextService.provide 决定空结果、实际提供范围、时间/ID 和游标，仓储保留 SQL 分页、记录约束、首次位置插入与 seq 条件 UPDATE RETURNING。

可见性由领域 VisibilityScope 明确自己发布/实际投递/有效订阅三种授权事实，SQL 在 limit 前落实；human 接收人列表不等同投递。领域计算推进值，所有记录同一短事务。

创建房间：领域 new_room_state → 应用写作用域 insert_room(room, user) / save_resources → 同事务事件。成员：短读退出 → inspect → 短写重查与领域变更。发布：身份/幂等/引用 → 领域路由 → 同事务序号、消息、投递、事件。远程清理：本地删除及目标短写提交 → RPC。投递：原子领取 → RPC → 领域结果 → 条件保存 → 受保护启动，未知不重发。关闭：停止 runners、释放锁、dispose 自建 Engine。

成员/消息 DTO 移至对应 contracts；消息页仍供 rooms 快照复用；上下文契约移至 context/contracts。共享模型/端口按节点顺序修改，删除旧 members/context、persistence/member_context 整用例适配与重复抽象，保留 SQL 方言、批量 loader、映射和锁。无阻塞性未知项，契约未改变七节点边界或依赖。

## Reception and progress / 接收与进展

2026-11-11 主会话接收 ALIGN-T01-20261111-01，方案修订 1，授权为用户“自行推进实施，避免沟通成本”。实际 HEAD 03b45fd632f25d0a051dc0de76a4035b1035988a，输入源码/测试可访问，无前置；独立 web 修改保留。已完成只读调查，没有产品或真实环境操作。

## Delivery and review / 交付与审查

2026-11-11 15:46:05，主会话以 ALIGN-T01-20261111-01/rev1 提交 ALIGN-contracts-v1。输入 HEAD 03b45fd；实际仅记录设计，R01—R08 与目标签名/调用链已核对，产品测试、mypy/Ruff 不适用。无未完成项、风险偏差或阻塞，主会话审查并接受。

2026-11-11 16:21:00，主会话接受实施契约补正 ALIGN-contracts-v1.1：`select_messages(room_id, request, scope)` 不再另传与 scope 重复的 member_id；scope 显式携带发布者、投递目标与订阅事实，避免两个身份参数不一致。其他事务、权限和节点边界不变；T05、T07 已按该签名复核，完整组合验证见 T07。
