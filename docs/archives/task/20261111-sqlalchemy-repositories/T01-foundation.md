# Task / 子任务 T01：SQLAlchemy 映射与事务基础
最后修改时间: 2026-11-11 13:08:32

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[SQLAlchemy 与 Repository 重构](../../intent/20261111-sqlalchemy-repositories.md)。
- 权威总计划：[修订 2](../../plan/20261111-sqlalchemy-repositories.md)，实际根为 `D:/SourceCodes/mywork/agent-relay`；任务 ID：T01。
- 依赖、授权、执行者和当前分配编号只以总计划为准；本文记录局部方案和接收/交付事实。

## Handoff basis / 交接依据

分配、授权和实际基线以总计划执行登记及分配历史为准；协议入口为本次 SpecFlow skill 的 references/task-coordination.md。

执行者的过程记录写入本文“接收与进展”“交付与审查”，通过 Agent Relay 定向回报主会话；主会话读取实际记录后同步总登记。不能通过更新本文自行取得执行权。

## Goal and acceptance / 目标与验收

交付可复用的类型化映射、数据库资源与事务基础，覆盖 A01、A02、A03、A04、A05、A10、A11 的基础部分；下游能在不直接接触 sqlite3 的情况下实现仓储。

- 映射现有 14 张表及当前约束、时间和回执格式；当前 head 的历史格式数据可往返，未新增迁移。
- 补齐 RoomRepository、MessageRepository、DeliveryRepository、ContextRepository 能力契约，沿用 RoomQueries/RoomData 等中立端口；不定义按模块划分的 UoW，不暴露 SQLAlchemy。统一请求或用例事务在装配时把各仓储绑定至同一 Session。
- HTTP 惰性事务和独立读写作用域可被实际测试验证；只有事务拥有者提交/回滚，临时测试仓储共享同一 Session。

## Inputs and eligibility / 输入与可开始条件

直接前置和版本条件见总计划定义表。规划基线 `be8accd90d4ae24a8aa9b8b225d8e77f8d709e96`；输入包括当前 baseline SQL、既有 transaction/store/middleware、时间/回执映射和测试。派发时重新核对 HEAD、独立修改、Plan/task 接受状态及实施授权。

## Scope and files / 范围与文件

- 共享契约：application/rooms/ports.py、application/delivery/ports.py、application/members/context.py。
- 新增 persistence/database.py、models.py、types.py、mappers.py、sqlite.py，演进 persistence/transaction.py；新建 tests/integration/test_sqlalchemy_foundation.py 和必要的纯映射测试。
- 本节点集中冻结共享模型、映射和事务契约。现有正式装配/公共 fixture 保持由 T06 切换，新基础通过局部 fixture 检查；不修改真实库或迁移链。

## Technical decisions / 局部技术设计

- Engine/sessionmaker 属于进程，Session 属于一个串行事务作用域；不使用全局 Session 或依赖线程局部变量判断请求归属。
- SQLite 连接事件控制外键、超时和显式 BEGIN；读写模式在首次 SQL 前确定，写作用域使用 BEGIN IMMEDIATE。所有 BEGIN/PRAGMA、rowid 和必要函数表达式集中在 sqlite.py。
- 请求首次写前 read 独立结束；写后 read 借用同一请求 Session。作用域退出不提交借入的 Session；中间件 finish 在响应开始前完成提交，重复收尾幂等。
- Session 使用显式 flush 策略，Repository 负责在需要约束或数据库结果前 flush；基础不隐藏提交，也不注册业务事件自动落库 hook。
- 时间映射保持现有带时区 ISO 文本；回执额外 metadata 保持 JSON 文本可读和标识一致性校验。映射只产生现有业务值，不向外返回 ORM 实体。
- 新基础可与尚未切换的旧适配并存至 T06，但不得在正式路径增加双写、自动回退或虚假空仓储。

## Implementation outline / 实施安排

1. 核对表、约束和现有序列化事实，建立映射及 SQLite 方言边界。
2. 定义能力仓储契约，实现统一资源工厂、短会话和惰性请求事务；跨模块仓储共用请求或用例事务。
3. 使用局部测试仓储验证共享事务、响应收尾、读写模式和历史格式往返。
4. 记录下游可使用的构造接口、实际版本、例外清单和检查，提交主会话审查。

## Checks and delivery / 检查与交付

- `uv run --locked pytest -o addopts=-ra tests/integration/test_sqlalchemy_foundation.py -q`：临时库；覆盖失败回滚、响应前提交/提交失败、惰性读、取消释放、顺序跨 worker 收尾和连接配置。
- 保留/扩展 tests/unit/test_persistence_records.py 的纯映射检查；SQLAlchemy 的真实往返归入 integration，不使默认 unit 建库。
- `uv run --locked mypy src tests`、Ruff check/format check 和限定 diff 空白检查；准确记录受旧装配影响而尚未切换的项目。
- 使用 Alembic 创建临时库验证映射，不使用 create_all 自证；读取旧 SQL 格式 fixture，核对时区、空值、回执及约束。
- 交付记录必须给出仓储绑定/Session 所有权说明及通过的实际命令；A01 的最终 src 清理由 T06 完成，本节点不能宣称已整体消除 sqlite3。

## Risks / 风险

默认事务控制可能弱化立即写锁；日期类型可能改变历史表现；同一请求的多个 worker 不能并行使用 Session。任一共享契约调整由主会话更新方案及下游范围。

## Reception and progress / 接收与进展

- 2026-11-11 12:51:30，高级开发接收 T01；有效分配 `T01-20261111-01`，方案修订 1。授权来自用户开始实现指示与架构师消息 `room-a2493e542ba3-msg-0007`。Plan/task 均 Accepted，总登记已 assigned，无前置任务。实际 HEAD `be8accd90d4ae24a8aa9b8b225d8e77f8d709e96`。保留独立修改 docs/design/codex-integration-capabilities.md，不读取差异或修改；不切正式装配、不操作真实库/服务、不执行 Git 写入。

- 2026-11-11 13:02：用户指出模块 UoW 会使跨模块事务边界不清，架构师消息 `room-a2493e542ba3-msg-0012` 接受方案修订 2，原分配编号继续有效。已删除尚未使用的 RoomUnitOfWork/Factory；仅增加能力仓储契约，统一事务基础不按模块划分。
- 14 表映射、ISO 文本时间与回执映射、SQLite 方言边界、Database 读写作用域及 SQLAlchemyTransaction 已完成。通过真实临时库检查跨仓储共享 Session、请求前短读、写锁先于检查、同事务事件、错误回滚、响应前提交与跨 worker 顺序收尾；未切正式装配。

- 2026-11-11 13:07:10：接收架构师审查退回消息 `room-a2493e542ba3-msg-0014`，原编号 `T01-20261111-01`、方案修订 2 继续有效，总登记 running；T01-workspace-v1 暂不放行。已核对旧观察检查点使用 julianday <=，本次仅修正集中时间函数并补等值/早晚/跨时区回归，随后更新哈希重交。

## Delivery and review / 交付与审查

- 初次交付（审查已退回，当前版本见下方 v2）：`T01-20261111-01 / T01-workspace-v1`，方案修订 2；父基线 HEAD `be8accd90d4ae24a8aa9b8b225d8e77f8d709e96`，位于共享权威工作区 `D:/SourceCodes/mywork/agent-relay`。11 个交付源码/测试文件的排序 `path:sha256` 清单（以 LF 连接、无末尾 LF）的 SHA256 为 `d4766fcf69cc063c7f6bf9beca7efd2dc0995b01b14aef95225720f414265520`，供主会话对照当前文件审查。未执行 Git 写入。
- 实际文件：application/rooms/ports.py、application/delivery/ports.py、application/members/context.py；persistence/database.py、models.py、types.py、mappers.py、sqlite.py、transaction.py；tests/integration/test_sqlalchemy_foundation.py、tests/unit/test_persistence_records.py。
- 映射：Base.metadata 覆盖现有 14 表；临时库由 Alembic head 创建，逐表比对列名/类型、主键、复合外键、唯一约束、CHECK、索引及部分索引条件。没有 create_all、DDL 变更、迁移或历史链改写。
- 兼容：历史 SQL 字符串 fixture 包含 +08:00、-07:00、UTC/Z、微秒及 NULL；读取保留时区/精度，实际修改后的写回使用相同 ISO TEXT 格式。回执只存额外 JSON 字段，标识由列重建并校验；新旧纯映射均通过。
- 下游接口：`Database(path)` 核验当前迁移 head，持有进程级 engine/sessionmaker；`request_transaction()` 返回惰性 `SQLAlchemyTransaction`。基础适配器把同一个 transaction 传给 `Database.read(transaction)` / `write(transaction)`，首次写前独立短读，写后所有仓储借用同一 Session。后台用例可共用同一个 `Database.write()` 作用域向多个仓储注入 Session。Repository 只 flush，不提交/回滚；应用只使用中立端口，ASGI 现有 finish 切面或独立写作用域负责最终提交。无模块 UoW。
- 生命周期：autobegin=False、autoflush=False、expire_on_commit=False；读取显式 BEGIN，写入在返回 Session 前 BEGIN IMMEDIATE。pool 连接配置外键、5 秒忙等待、允许请求在 worker 间顺序交接；Session 始终串行使用。异常/取消/首次 BEGIN 失败/提交失败均关闭会话，finish 幂等，禁止结束后重用；Database.close() 由最终装配在 workers 停止后调用。
- 下游映射工具：`room_from_model/topic_from_model/session_from_model/member_from_model/message_from_model/delivery_from_model/delivery_to_model/delivery_values`；SQLite `insertion_order/literal_contains/time_at_or_before`（v2 将原 time_before 改为含等号语义并改名） 集中 rowid、字面子串和时间函数。没有 ORM 关系的隐式业务 hook；插入父子行需明确 flush 顺序，bulk 更新需同步/过期 identity map，软删除筛选由各查询显式表达。
- 事务证据：基础测试中 RoomRecord 与 RoomEventRecord 两组写入先后借用同一 Session，外部连接提交前不可见；201 响应开始前数据和事件均已提交，400/500、异常、取消及提交失败均回滚。另覆盖独立短作用域失败、并发独立 Session 序号递增、外键、跨 worker 收尾、WebSocket 不建事务与失败 BEGIN 资源释放。
- 实际检查：`uv run --locked pytest -o addopts=-ra tests/integration/test_sqlalchemy_foundation.py tests/integration/test_request_transaction.py -q`：21 passed；`uv run --locked pytest tests/unit/test_persistence_records.py -q`：5 passed。`uv run --locked mypy src tests`：112 source files，成功；`uv run --locked ruff check .`、`uv run --locked ruff format --check .`：通过（176 files）；`git diff --check`：通过。
- 范围与未完成项：A01/A02/A03/A04/A05/A10/A11 的基础部分已交付，系统整体迁移尚未完成。旧 SQLiteTransaction 与正式适配继续保留，T02—T05 实现实际仓储，T06 切换装配/共享 fixture 后移除旧 sqlite3 运行时路径并执行整体回归。未访问真实库/服务，未运行总体 Verification；独立 design 文档未读差异或修改。
- 当前无已知阻塞；等待主会话核验交付版本、接口和证据后更新总登记。后续调整共享基础请经主会话协调。

### Rework delivery / 返工交付 v2

- 2026-11-11 13:08:32：按消息 `room-a2493e542ba3-msg-0014` 完成原编号返工，交付 `T01-20261111-01 / T01-workspace-v2`，方案修订 2，基线 HEAD 仍为 `be8accd90d4ae24a8aa9b8b225d8e77f8d709e96`。交付仍为前述 11 个源码/测试文件，按相同算法计算的当前 SHA256 为 `a6bf39116c0aef6347fda0b7c76c2aa89f1ddfc97b21b90a310dc4390755a6ba`；v1 哈希保留作退回历史。
- 本轮实际改动仅为 persistence/sqlite.py 和 tests/integration/test_sqlalchemy_foundation.py，以及本 task 的过程/交付记录。集中函数改为 `time_at_or_before(value, cutoff)`，使用 `julianday(value) <= julianday(cutoff.isoformat())`，与旧 store.py 两处观察检查点一致；类型接受 SQLColumnExpression，仓储可直接传 ORM 列或表达式。没有调用方残留旧 time_before 名称。
- 增加 8 个真实临时库回归案例：同一时区早于/等于/晚于检查点，UTC 与 -07:00 对 +08:00 的等效瞬间，跨时区早/晚，以及 NULL 延续 SQL 三值语义。调用方的 observed_at IS NULL 分支仍由仓储显式组合。
- 回归有效性：先在修复前运行新增案例，得到 3 failed、5 passed（同区等值、UTC 等值、-07:00 等值全部复现失败）；修复后同命令为 8 passed。`uv run --locked pytest -o addopts=-ra tests/integration/test_sqlalchemy_foundation.py -k observation_checkpoint -q`。
- 新版本完整定向检查：`uv run --locked pytest -o addopts=-ra tests/integration/test_sqlalchemy_foundation.py tests/integration/test_request_transaction.py tests/unit/test_persistence_records.py -q`：34 passed；`uv run --locked mypy src tests`：112 source files，成功；`uv run --locked ruff check .`、`uv run --locked ruff format --check .`：通过（176 files）；`git diff --check`：通过。
- 下游接口变化仅为使用明确命名的 `time_at_or_before`；原事务/映射接口及交付范围保持有效。无新增阻塞，不切正式装配、不操作真实库/服务、不执行 Git 写入。重新提交主会话核验，T02 放行仍由主会话决定。
