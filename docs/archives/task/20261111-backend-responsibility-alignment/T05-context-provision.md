# Task / 子任务 T05：成员上下文提供
最后修改时间: 2026-11-11 16:21:00

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[后端三层职责审视与业务组织调整](../../intent/20261111-backend-responsibility-alignment.md)。
- 权威总计划：[方案修订 1](../../plan/20261111-backend-responsibility-alignment.md)，任务 ID：T05。
- 权威协调根与代码工作区：`D:/SourceCodes/mywork/agent-relay`。依赖、分配、共享写入及审查以总计划为准。

## Handoff basis / 交接依据

- 用户已授权自主实施；执行者为主会话，分配编号 ALIGN-T05-20261111-01。接收、基线及前置见本文记录，最终组合见 T07。
- 协议入口为总计划 Coordination 的 SpecFlow skill 与协作契约；读取当前有效总登记和已接受输入。
- 执行者只写本文接收、进展、交付与最后修改时间；类型或共享契约超出设计时先向主会话回报。
- 在执行会话输出可复制摘要，由用户转交主会话，不自动发往聊天室。

## Goal and acceptance / 目标与验收

主要结果：上下文提供由应用用例组织，领域语义、数据库筛选和原子记账各有明确责任。覆盖 A02—A05、A07—A09 及 R02—R04、R06、R08 的上下文部分。

- `application/context` 包含实际提供流程，而非只有 DTO/Protocol；内部用 `provide` 表达有副作用的业务能力，公开 `/context` 接口、请求、结果与错误契约保持。
- 自己发布、实际 Delivery、当前有效订阅三种可见性语义独立且明确；指定 topic 需要当前有效订阅，human 接收人列表不扩大范围，跨房间同名 ID 不互相授权。
- 查询适配器在 SQL 中完成范围、关键词、游标和 limit+1 分页；不能依靠 Python 后过滤维护权限。lookahead 不记为提供，结果顺序及下一页游标保持。
- 应用决定本次提供流程及实际记账范围，领域计算位置更新，仓储原子保存 query/messages、条件推进位置并追加事件；相关读取/写入同一短事务，失败共同回滚。
- 空结果不产生提供记录；位置不后退、不因等值重复更新时间/事件；catalog 和 positions 是无副作用投影。移除旧整用例仓储和空 MemberContext 继承，保留必要存储原子方法。

## Inputs and eligibility / 输入与可开始条件

直接前置与版本要求只查总计划。需要已接受的上下文类型/作用域/可见性设计，以及已接受的消息值和数据库读取实现；核对方案、阶段授权、有效编号、共享文件及输入版本后记录接收。与投递节点无相互产物依赖，但共享工作区按主会话顺序执行。

## Scope and files / 范围与文件

- 新增 `application/context/{service,contracts,ports}.py`，迁移原 `application/members/context.py` 的有效定义并清理旧空抽象/消费者。
- `domain/rooms/positions.py` 及必要上下文规则、业务值/投影的有限调整；`repositories/context.py`、`member_context.py`、消息/资源读取的必要配套与统一 scope 适配。
- 成员上下文 HTTP route/provider、相关 fake/fixture、`test_context_repository.py`、`test_member_context.py`、`test_topic_positions.py` 及必要的纯上下文用例测试。
- 不重写管理端消息 scope，不改变领域可见性承诺；不修改投递 RPC、runner、schema 或 Database 生命周期。

## Technical decisions / 局部技术设计

- 沿 T01 已接受契约在一个统一短写作用域内组合：成员/订阅事实、可见消息读取、实际提供记录、位置更新、最终位置读取。作用域不透出 Session，不新建 ContextUnitOfWork。
- 领域规则明确权限语义及推进依据；SQL adapter 以相关 EXISTS 等表达式实现范围限制，过滤发生在排序/limit 之前。语义与 SQL 实现通过业务值测试和集成边界共同核对，不引入通用表达式 DSL。
- 应用只使用实际返回消息计算记账与推进输入；仓储可保留一次复合保存方法，内部保证提供记录与位置/事件原子性，但不承担整个 provide 的读取、策略和响应编排。
- 首次位置创建和大于旧值时的条件 UPDATE/RETURNING 留在仓储；并发保护不被 Python 的先读判断替代。时间、关联顺序和审计字段保持现有编码。
- Query/Reader 返回上下文专用值，不加载无用的 deliveries，保持批量关系读取；catalog/positions 可直接通过读取端口提供，不增加纯转发应用类。

## Implementation outline / 实施安排

1. 迁移上下文契约并实现实际 provide 用例，明确 catalog/positions 读取路径。
2. 将可见性与位置业务语义独立表达，调整 SQL 筛选和存储记账接口。
3. 接通统一短作用域、HTTP provider/route 和调用方，清理旧整用例路径。
4. 验证实际提供范围、分页、并发位置和各阶段失败，交付可组合的最终链路。

## Checks and delivery / 检查与交付

- 纯业务测试覆盖位置规则，以及新增/调整的上下文用例：空结果、lookahead 排除、实际提供范围、只读动作不记账、失败退出作用域；使用轻量端口，不为这些断言建库。
- 定向入口：`uv run --locked pytest -o addopts=-ra tests/integration/test_context_repository.py tests/integration/test_member_context.py tests/integration/test_member_publish.py tests/integration/test_persistence_runtime.py -q`。
- 保留现有可见性、历史删除/终态投递、literal 搜索、双向分页、同名跨房间、并发最大位置、约束/提交失败共同回滚与批量加载断言；移动后按真实责任更新调用，不删除有效业务覆盖。
- 受影响模块类型/格式检查与实际命令记录齐全；交付报告说明旧职责如何分配到新应用、领域和基础设施，不能只展示改名结果。

## Risks / 风险

- 提供成功与真实网络接收是不同事实；保持当前“本次提供”的定义，不新增客户端确认承诺。
- 将记录分成多个独立 store 调用会破坏事务；将权限改成分页后过滤会破坏范围和游标，均不接受。

## Reception and progress / 接收与进展

2026-11-11 主会话接收 ALIGN-T05-20261111-01/rev1，依据用户自主实施授权。HEAD 03b45fd 工作区含已接受 contracts-v1/messages-v1 与有效传递前置；实现统一 RepositoryScope、应用提供流程及数据库原子记录，不改投递链路或独立 web 修改。

## Delivery and review / 交付与审查

2026-11-11 16:18:10，主会话提交并审查接受 ALIGN-context-v1（ALIGN-T05-20261111-01/rev1）。应用 ContextService.provide 组织订阅、领域可见范围、SQL 读取、实际结果记账及位置返回；仓储只选择/原子记录，删除旧 members/context、persistence/member_context。TopicPosition 移至应用视图；统一 RepositoryScope/SQLAlchemyScope 与 RoomStore.read/write，所有消费者同步迁移。

定向 context_repository/member_context/member_publish/persistence_runtime 为 80 passed（9.95s）；新增纯上下文用例、位置与投递动作检查共 12 passed（0.13s），mypy src tests 140 文件通过。保留 8 次 SELECT、跨房间权限、分页实际提供、提交/各阶段回滚及借入 Session 共同回滚证据。无未完成或范围偏差。冻结签名去除 select_messages 冗余 member 参数，身份已由 VisibilityScope 携带；T07 统一记录实际契约修订与最终文件清单。
