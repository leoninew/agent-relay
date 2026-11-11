# Task / 子任务 T03：消息 Repository 与组合查询
最后修改时间: 2026-11-11 13:41:22

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[SQLAlchemy 与 Repository 重构](../../intent/20261111-sqlalchemy-repositories.md)。
- 权威总计划：[修订 2](../../plan/20261111-sqlalchemy-repositories.md)，协调根 `D:/SourceCodes/mywork/agent-relay`；任务 ID：T03。
- 任务依赖、执行者、编号和审查结论以总计划为准。

## Handoff basis / 交接依据

实施前按 SpecFlow references/task-coordination.md 核对方案、授权、有效编号、实际版本及前置交付；当前分配以总计划为准。本文接收/进展/交付章节为执行者可写记录，通过 Agent Relay 定向回报主会话。

## Goal and acceptance / 目标与验收

交付 MessageRepository、共享消息读取/筛选及 RoomQueries 实现，覆盖 A02、A05、A06、A07、A08、A10；供投递和上下文节点复用相同消息事实。

- 发布查找、序号、路由关系及初始投递/事件原子保存保持。
- metadata/snapshot、消息页、有效队列、历史消息和事件补取的字段、顺序、范围和游标保持。
- 范围清空覆盖所有页，按消息去重计数；clear_codex 的目标仍由保存的回执与范围确定。

## Inputs and eligibility / 输入与可开始条件

前置版本条件见总计划定义表。需要可用的资源 Repository/查询以及其冻结的基础映射、作用域和 SQLite 策略。派发时记录实际使用版本和共享文件状态。

## Scope and files / 范围与文件

- 新增 persistence/repositories/messages.py、message_queries.py、room_queries.py；新增 tests/integration/test_message_repository.py 和 SQLAlchemy 查询局部 fixture。
- 现有 test_room_queries.py、test_room_store.py 的行为可作为检查依据，公共 fixture 与应用接线仍由 T06 维护。
- 不在本节点修改 Codex 协议、HTTP/CLI/MCP 契约、共享模型或投递后台逻辑。

## Technical decisions / 局部技术设计

- 幂等查找、MAX(seq)+1、消息及关联/投递插入全部在同一 BEGIN IMMEDIATE 写作用域；复用已有 build_message 规则，不在 Repository 重新决定路由。
- 消息范围使用类型化布尔表达式集中组合：话题与相关成员取交集，相关成员匹配发送者或保存的实际接收人；上下文可见范围由 T05 独立表达。
- 使用批量查询装配话题、mention、recipient 和 delivery，保持 position/原有投递顺序；提供可复用入口，避免 T04/T05 复制关系读取或触发 N+1。
- 字面关键词保留 `%`、`_`、大小写与空白处理；消息页原有返回顺序和有效队列降序不同，分别保留，不用统一排序替换。
- 清空保留原状态/时间/回执并设置删除标记，写事件、计数和后续回执目标选择使用同一事务；只返回目标，不执行 Codex RPC。
- RoomQueries 既可绑定当前写 Session 读取本次未提交结果，也可使用独立短读。事件读取继续检查断线游标和 resync_required，数据写入后显式记录事件。

## Implementation outline / 实施安排

1. 实现消息保存/幂等/序号及共享关系装配。
2. 迁移消息范围、分页、队列清空与保存回执目标读取。
3. 组合 T02 资源读取实现 RoomQueries、summary 和事件补取。
4. 定向验证并发、历史格式、原子回滚与查询边界，冻结供 T04/T05 使用的接口。

## Checks and delivery / 检查与交付

- `uv run --locked pytest -o addopts=-ra tests/integration/test_message_repository.py -q`：新仓储并发序号、同编号幂等/冲突、关联和投递失败整笔回滚。
- 为新查询实现复用或参数化现有消息/队列/事件行为检查，覆盖成员/话题交集、字面特殊字符、分页、总数、清空全部页、历史 deletedAt 和事件游标。
- 以 SQLAlchemy 语句执行计数或等价证据确认消息页关联按批量装配，不添加只断言内部调用名的测试。
- 当前 head 历史时间和回执读取保持；mypy/Ruff/限定 diff 检查完成后记录版本及可复用接口。

## Risks / 风险

普通 Session 事务不足以保护 MAX(seq)+1；全局软删除过滤会隐藏历史；join/exists 变化可能重复计数消息；不同页面顺序和游标不能机械统一。

## Reception and progress / 接收与进展

- 2026-11-11 13:25:00，高级开发接收 `T03-20261111-01`，方案修订 2；授权消息 `room-a2493e542ba3-msg-0025`。Plan/task Accepted，总登记 assigned；实际 HEAD `be8accd90d4ae24a8aa9b8b225d8e77f8d709e96`。已核对前置 T01-workspace-v2 accepted（实际清单 SHA256 `a6bf39116c0aef6347fda0b7c76c2aa89f1ddfc97b21b90a310dc4390755a6ba`）及 T02-workspace-v1 accepted（实际清单 SHA256 `3322a512d4987439d7e09842bea9400d6d6aae3c2bb74ff057d14fde164789e1`）一致。冻结前置文件及公共夹具，只新增本节点消息仓储/查询和局部测试；保留独立 design/web 修改，不切正式装配、不操作真实库或服务、不执行 Git 写入。
- 2026-11-11 13:41:22，完成消息仓储、批量消息读取和组合 RoomQueries；本节点 54 项检查及相关回归合计 168 项通过，类型、lint 和格式检查通过。消息页读取 1 条和 25 条均为 6 次 SELECT。交付前重新核对 T01/T02 清单与接受版本一致，未改冻结文件、公共夹具或正式装配；无阻塞及范围偏差，交付待主会话审查。

## Delivery and review / 交付与审查

### 交付版本与实际变更

- 分配编号 `T03-20261111-01`，方案修订 2；交付 `T03-workspace-v1`，位于权威共享工作区 `D:/SourceCodes/mywork/agent-relay`，实际 HEAD 仍为 `be8accd90d4ae24a8aa9b8b225d8e77f8d709e96`。
- 前置为已接受的 T01-workspace-v2（`a6bf39116c0aef6347fda0b7c76c2aa89f1ddfc97b21b90a310dc4390755a6ba`）和 T02-workspace-v1（`3322a512d4987439d7e09842bea9400d6d6aae3c2bb74ff057d14fde164789e1`）；交付时重新计算均一致。
- 新增 `message_queries.py`：消息范围、幂等和序号读取、关系批量装配、字面关键词、历史消息页及有效队列查询。
- 新增 `repositories/messages.py`：消息、路由关系、初始投递及事件保存；全范围队列清空及保存回执目标读取。仅 flush，不提交或回滚借入的 Session。
- 新增 `room_queries.py`：复用 T02 资源读取实现现有 RoomQueries 的 metadata/snapshot、分页、消息、队列及事件补取；支持 Database 短读或借入当前事务 Session。
- 新增 `tests/sqlalchemy_message_fixtures.py` 和 `tests/integration/test_message_repository.py`：使用真实 RoomService 及新资源/消息仓储组合的局部夹具，独立预期值验证行为，不依赖旧运行时适配器或改动公共夹具。
- 范围偏差、未完成项、待仲裁事项：无。独立 design/web 修改保留，未读取其差异；未执行 Git 写入、正式接线、真实数据库或服务操作。

以下为产品代码及局部测试的完整清单；每行采用仓库相对路径、冒号及小写 SHA256，路径排序后用 LF 连接且末尾无 LF，再取 UTF-8 SHA256。清单总 SHA256：`9afcc7396062619de5ece2cec190cc8b65252e4d639f73b4e42ec5acf69de7ae`。此版本指工作区文件内容，审查时读取实际文件，不以暂存区替代。

```text
src/agent_relay/infrastructure/persistence/message_queries.py:b2cd9ac07589034365129d0c42832adbd8afa89afec561b44ee11f7bf245c112
src/agent_relay/infrastructure/persistence/repositories/messages.py:2ba8bb031677467d36e1e020fae63f622b0a46c2018c7c1fbffa850934237068
src/agent_relay/infrastructure/persistence/room_queries.py:db9a42e2e646dce174893434b23adf4cbd1514b97d1c07de2954c3d8e2efeb68
tests/integration/test_message_repository.py:b33641b4af30eb6b4b285c4f926efbb7ab6c9a14dcd4f27ed0db138acf648a3a
tests/sqlalchemy_message_fixtures.py:542623955bc88966d51917e935eaa46cbadb429061c86387e3e346e62fea0b91
```

### 局部验收结果

| 验收项 | 本节点证据与结果 |
| --- | --- |
| A02 | SQLAlchemyMessageRepository 满足既有 MessageRepository；SQLAlchemyRoomQueries 满足既有 RoomQueries。返回独立业务值，应用不接触 ORM/Session；真实 RoomService 直接使用局部适配器运行。 |
| A05 | 在当前 Alembic head 创建的临时库验证复合外键、唯一约束、position/投递顺序、历史软删除、NULL、带时区及 Z 格式时间和回执；读取历史格式 fixture，无 schema 或迁移变更。 |
| A06 | 并发发布取得唯一连续序号；相同发布编号并发重放仅生成一条消息，不同内容得到既有冲突；发布编号按房间及发布者隔离。序号读取与插入共用 BEGIN IMMEDIATE 写作用域，重放不重新路由历史消息。 |
| A07 | 无效话题、mention、接收人、投递会话/回执及重复客户端编号均使资源、消息、关联、投递和事件共同回滚；请求内资源与消息共用事务，只有所有者 finish 后可见。事件补取、分页和无效/跨房间/未来游标的 resync 行为保持。 |
| A08 | 有效队列按消息去重且降序，历史页保持时间正序；成员与话题取交集，成员匹配发送者或保存的实际接收人。清空超过 50 条覆盖全部页、按消息计数且重复清空不再计数，保留状态/时间/回执历史；Codex 目标仅按已保存的删除标记、状态及回执列选择，不执行 RPC。 |
| A10 | 新运行时 CRUD/筛选均采用 SQLAlchemy 表达式；关键词复用集中方言函数，覆盖字面 `%`、`_`、大小写、首尾空白和类似 SQL 的文本。消息及关系批量读取，1 条与 25 条消息页均为 6 次 SELECT，无逐消息装配查询。 |

### 检查命令与结果

```powershell
uv run --locked pytest -o addopts=-ra tests/integration/test_message_repository.py -q
# 54 passed
uv run --locked pytest -o addopts=-ra tests/integration/test_message_repository.py tests/integration/test_room_repository.py tests/integration/test_sqlalchemy_foundation.py tests/integration/test_request_transaction.py tests/integration/test_room_queries.py tests/integration/test_room_store.py tests/integration/test_member_sessions.py tests/integration/test_member_publish.py tests/unit/test_persistence_records.py -q
# 168 passed in 27.82s
uv run --locked mypy src tests
# Success: no issues found in 121 source files
uv run --locked ruff check .
# All checks passed!
uv run --locked ruff format --check .
# 185 files already formatted
git diff --check
# passed
```

检查使用临时数据库与局部夹具。本节点未运行全量测试、migrations mypy、前端或协议进程检查：未修改这些范围，完整装配及开发回归归 T06；没有执行整体 Verification。新运行时文件已检查，无 sqlite3、旧运行时适配器依赖或 raw SQL；局部测试仅为历史格式 fixture 使用原始插入语句。

### 下游接口、所有权与风险

- T04 可复用 `MessageQueries(session).message(room_id, message_id)`、`statement()`、`read(room_id, statement, include_deliveries=...)` 和 `load(room_id, rows, include_deliveries=...)`，统一读取当前发送者名称及有序话题/mention/recipient/delivery；消息读取保留历史删除资源及投递。返回业务值在 Session 关闭后可独立使用。
- T05 可从 `statement()` 构造自己的可见性条件后使用 `read(..., include_deliveries=False)`，已用局部测试确认不读取投递。`scope(room_id, topic_id=..., member_id=...)` 仅表示管理视图的发送者/历史实际接收人范围，不能代替上下文可见性规则；上下文订阅范围及位置归 T05。
- `SQLAlchemyMessageRepository(session)` 借用事务所有者提供的 Session；调用者须在写作用域内完成幂等、序号和插入。`clear_queue` 及 `codex_queue_targets` 应在相同写作用域使用，提交后再执行外部 Codex 清理；后续 RPC 分段及迟到投递竞争归 T04/T06。
- `SQLAlchemyRoomQueries(database, transaction=None)` 提供短读/请求内读；`SQLAlchemyRoomQueries(session)` 借用已有作用域。两者不允许并发共享 Session，不能同时传绑定 Session 与 transaction。
- T01/T02 基础与公共夹具保持冻结；新局部夹具供开发检查使用，正式 RoomStore、provider、bootstrap、后台及公共 fixture 的统一切换和旧实现删除归 T06。SQLiteTransaction 与 SQLAlchemyTransaction 目前为分阶段迁移共存，最终不保留双套正式运行时。
- 已知剩余风险为正式装配、后台条件竞争及上下文规则尚待各节点集成验证；本节点未扩大支持范围。请主会话核对当前工作区清单及检查证据后审查，再按总计划放行 T04/T05。
