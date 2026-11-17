# Task / 子任务 T05：成员上下文 Repository 与原子查阅
最后修改时间: 2026-11-11 14:10:45

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[SQLAlchemy 与 Repository 重构](../../intent/20261111-sqlalchemy-repositories.md)。
- 权威总计划：[修订 2](../../plan/20261111-sqlalchemy-repositories.md)，协调根 `D:/SourceCodes/mywork/agent-relay`；任务 ID：T05。
- 实际依赖、阶段授权、分配编号和交付仲裁以总计划为准。

## Handoff basis / 交接依据

实施前按 SpecFlow references/task-coordination.md 核对方案、授权、有效分配及前置交付；当前分配以总计划为准。过程事实写入本文接收/进展/交付章节，通过 Agent Relay 定向回报主会话。

## Goal and acceptance / 目标与验收

交付 ContextRepository 和实现既有 MemberContext 契约的 SQLAlchemy 适配，覆盖 A04、A07、A09。

- catalog、positions、可见消息选择与双向分页保持现有结果。
- 查询实际结果、提供记录、位置和事件在同一短事务完成；并发与历史查询不会降低已有位置。
- 能力返回既有 ContextResult/MemberCatalog 等业务值，不引入额外只转发服务。

## Inputs and eligibility / 输入与可开始条件

直接前置和版本条件以总计划定义表为准。消费已接受的共享消息装配、资源读取、SQLite 表达式策略和 Session/事务工厂，派发时记录实际可访问版本。

## Scope and files / 范围与文件

- 新增 persistence/repositories/context.py、member_context.py；新增 tests/integration/test_context_repository.py。
- 复用 domain/rooms/positions.py 的订阅校验和位置规则；共享消息读取不得复制。
- 不改 HTTP 参数/返回、MCP 注解、公共 fixture 或 T04 投递文件；必要共同调整由主会话安排。

## Technical decisions / 局部技术设计

- 可见范围仍为自己发布、实际投递或当前有效订阅话题；它不同于房间查询的发送者/实际接收人筛选，不共用不等价的业务谓词。
- 单条消息可见性、topic 订阅校验、字面关键词、before/after 分页及返回时间线顺序保持。
- catalog/positions 使用短读，query 由于记录提供结果和位置使用短写；选择到响应 DTO 的过程都在同一作用域，外部无模型/RPC 工作。
- 记录确实返回给调用者的 message ID 与顺序；位置使用条件更新或等价原子 upsert，只允许更大 seq。
- 数据、提供记录、位置和显式事件共用 Session；无位置变化不追加多余 position 事件。历史实际路由和软删除事实不被全局 ORM 过滤误删。

## Implementation outline / 实施安排

1. 用 SQLAlchemy 表达上下文可见性、catalog 和位置读取。
2. 复用消息批量装配实现选择，迁移提供记录与条件位置更新。
3. 通过新适配的局部 fixture 验证范围、分页、原子回滚和并发单调性，交付 T06 构造入口。

## Checks and delivery / 检查与交付

- `uv run --locked pytest -o addopts=-ra tests/integration/test_context_repository.py -q`：实际返回记录、不可见消息、订阅变化、直接消息、特殊字符、双向分页、并发位置最大值和失败共同回滚。
- test_member_context.py、test_topic_positions.py 的既有行为在新实现上保持；默认纯规则 unit 不依赖数据库或 HTTP。
- 记录查询结果与提供记录/position 逐字段证据；T06 接线前不得仅用旧适配通过结果宣称新实现覆盖。
- 使用当前 mypy/Ruff，记录版本/前置、实际命令和未运行项；不对真实房间执行查阅或位置更新。

## Risks / 风险

通用消息筛选可能扩大上下文可见范围；先读后无条件写可能使并发位置倒退；选择和记录分离会使证据与实际提供内容不一致。

## Reception and progress / 接收与进展

- 2026-11-11 13:58:15，高级开发接收 `T05-20261111-01`，方案修订 2；授权来自用户开始实现指示、总计划分配历史及架构师消息 `room-a2493e542ba3-msg-0038`。Plan/task Accepted，总登记 assigned；实际 HEAD `be8accd90d4ae24a8aa9b8b225d8e77f8d709e96`。直接前置 T03-workspace-v1（`9afcc7396062619de5ece2cec190cc8b65252e4d639f73b4e42ec5acf69de7ae`）已接受且实际清单一致；同时核对 T01-workspace-v2（`a6bf39116c0aef6347fda0b7c76c2aa89f1ddfc97b21b90a310dc4390755a6ba`）、T02-workspace-v1（`3322a512d4987439d7e09842bea9400d6d6aae3c2bb74ff057d14fde164789e1`）及 T04-workspace-v1（`5a3c031a54bc2a3add8882aec01d0510bc0afb4c20a48955a9984e48149999e5`）实际清单均与接受版本一致。仅新增上下文仓储、短事务适配和局部测试；冻结前置文件及公共夹具，保留暂存区及独立修改，不读取独立差异、不执行 Git 写入、不接正式装配、不操作真实库或服务。当前无阻塞，共享变更需求先协调。
- 2026-11-11 14:10:45，完成上下文仓储及短事务适配；最终局部 56 项、相关回归合计 307 项通过，mypy、全仓 Ruff lint/format 和暂存/未暂存差异空白检查通过。核对上下文独立可见性、同名资源/消息的跨房间隔离、双向分页的实际提供范围，以及八路并发位置最大值；1 条与 25 条上下文消息读取均保持 8 次 SELECT。交付前复算 T01—T04 清单均一致，未调整共享文件；无阻塞和范围偏差，交付待主会话审查。

## Delivery and review / 交付与审查

### 交付版本、文件与边界

- 分配编号 `T05-20261111-01`，方案修订 2；交付 `T05-workspace-v1` 位于权威共享工作区 `D:/SourceCodes/mywork/agent-relay`，实际 HEAD `be8accd90d4ae24a8aa9b8b225d8e77f8d709e96`。
- 直接前置为已接受 T03-workspace-v1（`9afcc7396062619de5ece2cec190cc8b65252e4d639f73b4e42ec5acf69de7ae`）。工作区同时使用已接受的 T01-workspace-v2（`a6bf39116c0aef6347fda0b7c76c2aa89f1ddfc97b21b90a310dc4390755a6ba`）、T02-workspace-v1（`3322a512d4987439d7e09842bea9400d6d6aae3c2bb74ff057d14fde164789e1`）及 T04-workspace-v1（`5a3c031a54bc2a3add8882aec01d0510bc0afb4c20a48955a9984e48149999e5`）；交付时四份实际清单均复算一致。
- 新增 `persistence/repositories/context.py`：实现既有 ContextRepository 的 catalog、positions、query；复用 T03 批量消息读取及 T02 位置读取，以独立上下文谓词选择消息，保存实际提供记录，并按领域规则条件推进位置、显式记录事件。借用 Session，只 flush，不提交、回滚或关闭。
- 新增 `persistence/member_context.py`：实现 MemberContext 中立端口；catalog/positions 为短读，query 在独立短写内完成选择、提供记录、位置、事件和 DTO 生成，提交并关闭会话后返回业务值。只持有 Database，不保存可变 Session 或外部客户端。
- 新增 `tests/integration/test_context_repository.py`：使用迁移到当前 head 的临时库及冻结的 T03 局部夹具；新适配的实际结果、记录、事件、并发与故障检查，不依赖旧运行时路径或 HTTP 装配。仅另写本 task 的接收、进展、交付及修改时间。
- 范围偏差、未完成项、待仲裁事项：无。前置文件和公共夹具未改，原暂存区及独立修改保留，未读取独立差异；无 Git 写入、正式接线、真实数据库或服务操作。

以下三文件按仓库相对路径排序，以 `path:sha256` 行、LF 连接且末尾无 LF，取 UTF-8 SHA256；清单总 SHA256 为 `40b9e09f30cdc50787a2bacbf7f49b490d3f523c5f63344da35112c44eabb25a`。审查对象为工作区实际文件内容，不以暂存区替代。

```text
src/agent_relay/infrastructure/persistence/member_context.py:2c614acd38c138eacdb76bb63e1a510536b5456f75b4ed1fd9489a0d869b6107
src/agent_relay/infrastructure/persistence/repositories/context.py:0a3c9b6b0db78b388620a10ea8691d8259adbb2eb8dbc02cdd938bacf78e6542
tests/integration/test_context_repository.py:654308235d019adcf1bbf32e2e3a2f63a7f11e53aa03de4d3b59fe2cd7f7654d
```

### 局部验收结果与关键语义

| 验收项 | 本节点证据与结果 |
| --- | --- |
| A04 | catalog/positions 不产生提供记录、位置或事件，短读结束即归还连接。query 的全部数据库步骤在一个 BEGIN IMMEDIATE 作用域内，无 RPC；返回 ContextResult 后池连接已归还。失败、约束失败及提交失败均释放连接，进程 Engine 仍由 Database 所有者管理。 |
| A07 | query parent、实际返回消息及其顺序、位置和 position 事件共用 Session。分别在 parent、关联、位置、事件、结果构造阶段注入失败，以及真实复合外键失败，均无半条提供记录或位置/事件残留；提交失败不返回成功。与资源仓储组合的所有者回滚同时撤销资源、提供记录、位置及事件，已加载位置实体与条件更新同步。 |
| A09 | 可见性按自己发布 OR 实际 Delivery OR 当前有效订阅话题表达；不使用管理视图发送者/保存接收人范围。验证无订阅时自己的发布/直接消息可见、订阅新增可读旧消息、取消订阅/话题删除移除仅靠订阅的可见性、历史投递删除/终态仍可见。相同消息 ID、成员/话题 ID 在不同房间不能授权或串写位置。双向 keyset 分页按时间线返回，字面特殊字符/大小写/首尾空白保持，lookahead 不写提供记录或推进位置。单条/话题/全部查询、空结果、历史反查、重复查询与八路并发均保持领域位置规则。 |

- catalog 保留现有房间字段、话题及成员 rowid 顺序，过滤已删除资源；成员 topic_ids 仍按保存的 position 返回，订阅有效性另外排除已删除话题。positions 复用 T02 的活动订阅、默认零值、时间和 later_count 规则，读取不写库。
- 上下文与管理视图有意不同：仅保存为 human recipient、没有实际 Delivery 的他人消息不会扩大该成员上下文；六种投递状态及删除标记不会隐藏历史实际投递。发送者软删除后仍可返回历史消息的当前保存名称。
- 复用 `require_subscribed_topic` 和 `position_updates`；无话题过滤时推进返回消息涉及的每个有效订阅，指定话题只推进该话题。原子短写内缺失位置才插入，已有位置使用 `seq < 新值` 条件 UPDATE RETURNING，只有确实推进才追加事件；不增加新的 SQLite 方言写法。相同或更早历史查询保留 seq/updated_at，空结果不新建 query_id 或提供记录。
- 实际提供关联逐条核对响应 message ID 和时间线顺序，保存过滤条件、方向、limit 及带时区 provided_at；返回 ContextMessage 保持既有字段，不泄露 Delivery/ORM/Session。1 条与 25 条消息读取均为 8 次 SELECT，不额外物化投递实体，无逐消息关系查询。

### 检查命令、结果与未运行项

```powershell
uv run --locked pytest -o addopts=-ra tests/integration/test_context_repository.py -q
# 56 passed in 4.94s
uv run --locked pytest -o addopts=-ra tests/integration/test_context_repository.py tests/integration/test_delivery_repository.py tests/integration/test_message_repository.py tests/integration/test_room_repository.py tests/integration/test_sqlalchemy_foundation.py tests/integration/test_request_transaction.py tests/integration/test_room_queries.py tests/integration/test_room_store.py tests/integration/test_member_sessions.py tests/integration/test_member_publish.py tests/integration/test_delivery_service.py tests/integration/test_member_context.py tests/unit/test_delivery_actions.py tests/unit/test_topic_positions.py tests/unit/test_persistence_records.py -q
# 307 passed in 28.46s
uv run --locked mypy src tests
# Success: no issues found in 127 source files
uv run --locked ruff check .
# All checks passed!
uv run --locked ruff format --check .
# 191 files already formatted
git diff --check
git diff --cached --check
# 均 passed
```

新运行时文件经定向搜索，无 sqlite3、raw SQL 或 commit/rollback/close 调用。检查使用临时数据库，不操作真实房间。全量测试、migrations mypy、前端、协议进程和整体 Verification 未运行：本节点未修改相关装配，完整开发回归归 T06。既有 SQLiteMemberContext/HTTP 检查作为过渡回归，新实现的证据来自上述 56 个实际绑定新仓储/适配的案例。

### T06 接线入口、所有权与剩余风险

- 正式构造入口为 `agent_relay.infrastructure.persistence.member_context.SQLAlchemyMemberContext(database)`，现有 HTTP/MCP 消费 MemberContext 端口即可，公开参数/返回不变。进程复用 Database/Engine；本适配器每次调用使用独立短作用域，不绑定请求 Session，不持有跨请求可变会话。
- 组合用例可在一个 `Database.write()` 内构造 `agent_relay.infrastructure.persistence.repositories.context.SQLAlchemyContextRepository(session)`，同一 Session 可供其他仓储共享。query 要求写作用域以保护首次位置插入、消息选择及实际提供事实；不能在短读内调用 query，也不能并发使用同一 Session。catalog/positions 可借用读作用域。
- T06 继续统一工厂/provider/bootstrap/公共夹具并删除旧 context.py/positions.py 的 sqlite3 运行时实现；不能把管理视图 `MessageQueries.scope` 当成上下文权限谓词。完整系统回归及整体 Verification 尚未完成。
- 本节点无已知产品阻塞或共享文件调整需求。最终装配、迁移后所有调用链及进程关闭顺序仍需 T06 验证；请主会话按工作区哈希、实际变更和上述证据审查后放行集成。
