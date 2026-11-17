# Task / 子任务 T04：投递 Repository 与短事务动作
最后修改时间: 2026-11-11 13:54:06

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[SQLAlchemy 与 Repository 重构](../../intent/20261111-sqlalchemy-repositories.md)。
- 权威总计划：[修订 2](../../plan/20261111-sqlalchemy-repositories.md)，协调根 `D:/SourceCodes/mywork/agent-relay`；任务 ID：T04。
- 依赖、有效分配和审查状态由总计划唯一维护。

## Handoff basis / 交接依据

实施前按 SpecFlow references/task-coordination.md 核对实施授权、有效分配与前置接受；当前分配以总计划为准。执行者在本文接收/进展/交付章节记录，通过 Agent Relay 定向回报主会话。

## Goal and acceptance / 目标与验收

交付 SQLAlchemy DeliveryRepository 和实现原 DeliveryStore 契约的短动作适配，覆盖 A04、A07、A08、A11。

- pending 领取、异常中断、回执保存、启动尝试、备注与输入确认均保留条件写入。
- 每个动作独立短事务，数据与事件原子提交；RPC 期间不占用 Session/数据库事务。
- 清空、迟到结果、unknown 不重发和单次首项启动行为保持。

## Inputs and eligibility / 输入与可开始条件

以总计划定义表的前置与版本要求为准。需要已接受的共享消息装配/筛选、资源读取、回执映射和事务基础，不能复制或自行改写这些契约。

## Scope and files / 范围与文件

- 新增 persistence/repositories/deliveries.py、delivery_store.py；新增 tests/integration/test_delivery_repository.py。
- 保留 application/delivery/service.py、dispatch runner 和 QueueDriver 的业务行为；最终工厂切换、锁路径及公共 fixture 由 T06 完成。
- 共享定义需要改动时由主会话协调；不同时改 T05 的夹具、上下文代码或总计划登记。

## Technical decisions / 局部技术设计

- Repository 借用 Session；DeliveryStore 适配器为一次原子方法创建短作用域并提交后返回业务值。应用 DeliveryService 的 RPC 调用发生在这些方法之外。
- 领取维持每会话无其他 submitting 的条件和既有 FIFO；finish 保留 status/deleted_at/client_message_id；activation 保留回执身份和未尝试条件。
- 用带条件的 update 和实际受影响结果判定，不将 ORM 对象的旧属性无条件写回；事件只为成功变更的记录追加。
- confirm_input 保留原会话和原 client_message_id 的核验、received item/turn 记录及 unknown 到 received 的路径；清空历史不参与后台候选。
- 启动、中断、备注和接收事实继续通过中立值表达，不保存完整 prompt，不新增重试/补偿策略。

## Implementation outline / 实施安排

1. 实现条件领取和 ClaimedDelivery 装配，复用 T03 消息读取。
2. 迁移回执、启动尝试、中断、备注和接收确认，并共享事务写事件。
3. 接入局部 DeliveryStore fixture 验证并发与 RPC 分段，交付 T06 的构造入口。

## Checks and delivery / 检查与交付

- `uv run --locked pytest -o addopts=-ra tests/integration/test_delivery_repository.py -q`：同会话竞争领取、清空与回执竞争、启动只尝试一次、身份不匹配不更新、失败连同事件回滚。
- 保留 test_delivery_service.py、test_member_publish.py、test_delivery_actions.py 的原会话关联、定位头部、回执及 unknown 不重发覆盖；局部检查需实际绑定新适配。
- fake QueueDriver 在 enqueue/delete/activate 时验证前一数据库事务已经结束；并行动作各用独立 Session。
- 使用当前类型/lint/格式入口，准确记录版本、命令、结果、未运行项和未完成项，不操作真实 daemon。

## Risks / 风险

ORM 无条件回写可能复活软删除记录；事务未提交便 RPC 会延长写锁并造成不可回滚的外部动作；Session 不得跨线程池并发任务复用。

## Reception and progress / 接收与进展

- 2026-11-11 13:45:43，高级开发接收 `T04-20261111-01`，方案修订 2；授权来自用户开始实现指示、总计划分配历史及架构师消息 `room-a2493e542ba3-msg-0035`。Plan/task Accepted，总登记 assigned；实际 HEAD `be8accd90d4ae24a8aa9b8b225d8e77f8d709e96`。已复算并核对接受的前置 T01-workspace-v2（`a6bf39116c0aef6347fda0b7c76c2aa89f1ddfc97b21b90a310dc4390755a6ba`）、T02-workspace-v1（`3322a512d4987439d7e09842bea9400d6d6aae3c2bb74ff057d14fde164789e1`）及 T03-workspace-v1（`9afcc7396062619de5ece2cec190cc8b65252e4d639f73b4e42ec5acf69de7ae`）清单均一致。仅新增投递仓储、短事务适配和局部集成测试；冻结前置及公共夹具，保留暂存区和独立 design/web 修改，不读取独立差异、不执行 Git 写入、不切正式装配、不操作真实库或服务。共享变更需求先报协调；当前无阻塞。
- 2026-11-11 13:54:06，完成投递条件仓储与独立短事务适配；局部 62 项及相关回归合计 239 项通过。首轮发现跨房间测试误按列表位置取得不同成员/会话，已改为按身份选择测试数据；最终跨房间互斥检查通过。mypy、全仓 lint、本节点格式和差异空白检查通过；全仓格式检查发现同时出现的范围外 `tests/integration/test_room_api.py` 需要格式化，未改该文件。前置 T01/T02/T03 交付清单复算一致，无共享文件调整需求；交付待主会话审查。

## Delivery and review / 交付与审查

### 交付版本、文件与边界

- 分配编号 `T04-20261111-01`，方案修订 2；交付 `T04-workspace-v1` 位于权威共享工作区 `D:/SourceCodes/mywork/agent-relay`，实际 HEAD `be8accd90d4ae24a8aa9b8b225d8e77f8d709e96`。
- 使用已接受的 T01-workspace-v2（`a6bf39116c0aef6347fda0b7c76c2aa89f1ddfc97b21b90a310dc4390755a6ba`）、T02-workspace-v1（`3322a512d4987439d7e09842bea9400d6d6aae3c2bb74ff057d14fde164789e1`）及 T03-workspace-v1（`9afcc7396062619de5ece2cec190cc8b65252e4d639f73b4e42ec5acf69de7ae`）；交付前重新计算均一致。
- 新增 `persistence/repositories/deliveries.py`：实现 DeliveryRepository 的七个能力方法，借用 Session；通过条件 UPDATE RETURNING 取得实际变更标识，再写对应事件并 flush，不自行提交、回滚或关闭 Session。领取复用 T02 资源及 T03 消息装配，FIFO 仍使用集中 rowid 表达式。
- 新增 `persistence/delivery_store.py`：实现既有 DeliveryStore 契约，每个修改动作独立 `Database.write()`，候选输入读取使用 `Database.read()`；提交并释放 Session 后才返回结果，不保存共享 Session、不持有 QueueDriver。
- 新增 `tests/integration/test_delivery_repository.py`：局部临时迁移库、并发与失败注入检查，实际绑定新适配运行原有 DeliveryService/RoomService；复用已冻结的 T03 局部夹具及现有 fake，不修改公共夹具或旧适配器。
- 仅另写本 task 的接收、进展、交付和修改时间。无产品范围偏差、未完成项或待仲裁的共享变更；保留原暂存区、独立 design/web 及同时出现的范围外 application/HTTP/test_room_api 修改，未读取独立差异。没有 Git 写入、正式接线、真实数据库或服务操作。

以下三文件按仓库相对路径排序，以 `path:sha256` 行、LF 连接且末尾无 LF，取 UTF-8 SHA256；清单总 SHA256 为 `5a3c031a54bc2a3add8882aec01d0510bc0afb4c20a48955a9984e48149999e5`。审查对象为工作区实际内容，不以暂存区替代。

```text
src/agent_relay/infrastructure/persistence/delivery_store.py:141f032ad1764db2beeb3dba2e30f2af2c8d215a3f5751115157ca7fb9fccd63
src/agent_relay/infrastructure/persistence/repositories/deliveries.py:9374a653aa34c6e5608361f318198da364a561513ab2e0b90d00b535d2009cb1
tests/integration/test_delivery_repository.py:2fd8aafd67c6d92a2ab755ed8944442f8d61c6ab8822dfa29e6a94b618c2dd7e
```

### 局部验收结果

| 验收项 | 本节点证据与结果 |
| --- | --- |
| A04 | 原 DeliveryService 的 enqueue、activation_candidate、activate、read_input_page，以及 RoomService.clear_queue_with_codex 的 delete 均由 fake 断言没有借出的连接，并当场取得独立写作用域确认未持写锁。enqueue 前可读已提交 submitting，activate 前可读已提交启动尝试，delete 前可读已提交删除标记。阻塞中的 enqueue 与清空可并行，迟到回执不触发启动。 |
| A07 | 领取、完成、启动、备注、接收和中断均根据 UPDATE 实际返回行写事件；六种动作的事件失败注入均回滚数据并释放连接。提交失败不返回成功。借入仓储与资源仓储共用一个 Session，外部读取看不到未提交值，所有者异常时资源、投递与事件共同回滚；已加载 ORM 实体同步为最新状态。 |
| A08 | 保留全局 FIFO、每原会话 submitting 排他及跨房间排他；八路竞争不会重复领取或重复启动。finish 仅修改同房间/投递/client ID 的未删除 submitting，保留保存的目标身份；启动要求原 session/queue/client 身份且只尝试一次。confirm 只接收原 session/client 的未删除 queued/unknown，并保留回执/排队时间；重复或迟到结果不覆盖历史。领取/清空和完成/清空真实竞争、所有清空后后台动作均验证不复活；unknown 不自动重发，旧输入跨页可确认，回执额外字段及持久重开保持。 |
| A11 | 各后台方法取得独立短作用域，Repository 仅借用当前 Session。并发领取及启动使用独立作用域，池 checkout/checkin 检查证实成功、异常及提交失败后连接已归还，返回 ClaimedDelivery 为可独立使用的业务值。Engine 由外部持有的 Database 管理，适配器不承担进程关闭。 |

历史成员仍按保存的会话绑定匹配，不新增全局 deleted_at 过滤；不匹配的绑定、human、已删除或终态投递不参与领取。备注和接收保持既有字段更新范围，不保存完整 prompt，也未增加补偿或重试策略。

### 检查命令、结果与未运行项

```powershell
uv run --locked pytest -o addopts=-ra tests/integration/test_delivery_repository.py -q
# 62 passed in 7.38s
uv run --locked pytest -o addopts=-ra tests/integration/test_delivery_repository.py tests/integration/test_message_repository.py tests/integration/test_room_repository.py tests/integration/test_sqlalchemy_foundation.py tests/integration/test_request_transaction.py tests/integration/test_room_queries.py tests/integration/test_room_store.py tests/integration/test_member_sessions.py tests/integration/test_member_publish.py tests/integration/test_delivery_service.py tests/unit/test_delivery_actions.py tests/unit/test_persistence_records.py -q
# 239 passed in 30.63s
uv run --locked mypy src tests
# Success: no issues found in 124 source files
uv run --locked ruff check .
# All checks passed!
uv run --locked ruff format --check .
# 1 file would be reformatted, 187 files already formatted
# 范围外 tests/integration/test_room_api.py，未修改
uv run --locked ruff format --check src/agent_relay/infrastructure/persistence/repositories/deliveries.py src/agent_relay/infrastructure/persistence/delivery_store.py tests/integration/test_delivery_repository.py
# 3 files already formatted
git diff --check
git diff --cached --check
# 均 passed
```

新运行时文件另经定向搜索，无 sqlite3、raw SQL、commit/rollback/close 调用。完整测试、migrations mypy、前端、协议进程及整体 Verification 未运行：不属于本节点改动，最终装配与完整开发回归由 T06 负责。旧适配器的既有回归仅为过渡兼容证据；本节点 62 项检查全部实际绑定新仓储/适配器。

### T06 接线入口与剩余风险

- 构造入口：`agent_relay.infrastructure.persistence.delivery_store.SQLAlchemyDeliveryStore(database)`，同一进程可复用同一个 Database/Engine；各动作自行创建独立 Session，不能绑定请求事务或复用请求 Session。现有 DeliveryService 及 DeliveryRunner 可按原 DeliveryStore 端口接收此实例。
- 复合短事务可用 `agent_relay.infrastructure.persistence.repositories.deliveries.SQLAlchemyDeliveryRepository(session)`，由调用方以同一个 `Database.write()` 向其他仓储传 Session；仓储不独立提交。后台常规路径使用上面的 Store，返回后再进行外部 RPC。
- 最终装配继续用 `Database.path` 的规范化路径构造 SubmitterLock；保留 runner 获取排他锁后才调用 interrupt_submissions 的业务约束。先停止 runner/等待 workers，再由进程所有者关闭 Database；本节点未改锁身份或 runner 生命周期。
- T01/T02/T03、公共夹具和正式工厂保持冻结；由 T06 统一装配、删除旧 sqlite3/SQLiteTransaction 路径并执行完整回归。T05 上下文和 T06 集成仍未完成，本次不是系统整体迁移或整体 Verification 结论。
- 本节点无已知产品阻塞。共享工作区存在范围外 API 测试格式问题，已隔离记录，请主会话协调原修改者；不能把全仓格式检查记为通过。请主会话核对上述工作区清单、实际代码和局部检查后审查。
