# Task / 子任务 T06：集成切换、旧实现移除与开发回归
最后修改时间: 2026-11-11 15:00:42

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[SQLAlchemy 与 Repository 重构](../../intent/20261111-sqlalchemy-repositories.md)。
- 权威总计划：[修订 2](../../plan/20261111-sqlalchemy-repositories.md)，协调根 `D:/SourceCodes/mywork/agent-relay`；任务 ID：T06。
- 前置版本、分配、执行和审查由总计划维护；本节点开发回归不自动进入整体 Verification。

## Handoff basis / 交接依据

实施前按 SpecFlow references/task-coordination.md 核对前置交付、有效授权、执行者、编号与工作基线；当前分配以总计划为准。接收/进展/交付写本文相应章节，通过 Agent Relay 定向回报主会话。

## Goal and acceptance / 目标与验收

交付单一 SQLAlchemy 正式运行时和完整开发回归，集成覆盖 A01—A12。

- 应用、HTTP、后台和公共 fixture 使用新仓储/查询/事务工厂，src 不再直接依赖 sqlite3 API。
- 保持请求切面、外部 RPC 分段、WebSocket 短读、配置、数据库锁身份及原有公开接口。
- 删除已替代实现和失效导入，文档与真实行为一致，提供当前组合版本的完整检查及未完成项。

## Inputs and eligibility / 输入与可开始条件

直接前置和版本条件以总计划定义表为准。核对全部上游有效交付、实际接受证据及其组合是否仍兼容；缺少上游检查、发生共享契约变化或版本不可用时，不以任务自报完成放行。

## Scope and files / 范围与文件

- application/rooms/service.py、application/members/service.py 及对应内存替身，通过中立端口使用统一请求或用例事务，不新增模块专用 UoW。
- interfaces/http/persistence.py、rooms/members provider、bootstrap/http.py、persistence/dependencies.py、dispatch/dependencies.py、必要的中立事务适配。
- tests/room_fixtures.py、tests/fakes、受影响的全部集成测试和 subprocess 内部导入消费者；新局部 fixture 在可行时收敛复用，保留有意义的独立仓储检查。
- 删除或收敛旧 persistence/store.py、rooms.py、queries.py、context.py、positions.py、records.py 的已替代代码；不保留 SQLiteRoomStore 等旧内部路径转发代理。
- 更新 docs/design/backend-architecture.md 和本任务记录，按真实变化更新简洁使用说明；不修改独立 codex-integration-capabilities 文档、前端或历史迁移 SQL。

## Technical decisions / 局部技术设计

- bootstrap 从中立工厂取得 Database、查询和动作适配；Engine 退出时在 runner 全部停止后 dispose，借入资源的 provider/Repository 不重复关闭。
- RoomService/MemberSessions 通过中立端口使用统一事务，装配层将同一请求或用例的仓储绑定到同一 Session；RoomQueries 在写作用域内读取同一 Session，普通读取及 WebSocket 每次短取。
- 请求事务仍由原 ASGI 中间件拥有；clear_queue_with_codex 使用不绑定请求长事务的短写工厂，明确先提交再外部删除；成员 inspect 同样不被请求 Session 隐式包住。
- DeliveryRunner 仍持原数据库文件路径的 SubmitterLock，动作使用新 DeliveryStore；不改变线程数、轮询频率或 unknown 不重发。
- 更新测试对 sqlite3 连接/异常/裸 SQL 的依赖，用新仓储或 SQLAlchemy 测试接口表达行为。历史 DDL 专用 test_migration_sql.py 可作为直接 SQLite 验证例外，不恢复 src 依赖。
- 所有当前 head 历史值兼容证据使用临时库；不因架构变更删除或重建开发数据库，不把 ORM metadata 当迁移来源。

## Implementation outline / 实施安排

1. 核对上游版本，在当前工作区接通应用、HTTP 和后台工厂，更新共享 fixture 与 subprocess 导入。
2. 验证请求提交、错误回滚、RPC/WS 分段、文件锁和资源关闭；修复仅属于本次集成的遗漏。
3. 移除旧实现，进行依赖/SQL 例外审查，确认单一正式路径。
4. 执行当前组合版本完整开发检查，更新架构与交付记录，向主会话报告 A01—A12 结果及剩余风险。

## Checks and delivery / 检查与交付

以总计划验证命令为准，至少执行纯业务测试、显式覆盖默认 marker 过滤的全部后端测试、mypy src/tests/migrations、Ruff 和 diff 空白检查。

- 集成检查覆盖 current-head 兼容、复合外键、并发序号/绑定、事件、请求事务/提交失败、投递/清空竞争、上下文及 HTTP/CLI/MCP 契约。
- AST/导入核对 src 无直接 sqlite3、application/domain 无 SQLAlchemy/Session；列出 sqlite.py 的必要原生语句和固定表达式，不以字符串 grep 结果代替调用链审查。
- 逐项核对原有文件锁、数据库路径、启动迁移开关、单次 RPC 资源和 lifespan 关闭；新 Engine 不能因工厂替换引入跨测试/请求缓存。
- 不运行用户服务器、浏览器、真实 Codex 或真实数据库操作。若未执行某项检查，写明准确原因和影响，不宣称全量通过。
- 集成涉及的应用、HTTP 和测试文件已有独立修改；先读取实际内容并融合，保留已有暂存区和无关变更，不回退或覆盖。存在无法安全合并的冲突时回报主会话。
- 交付版本为可访问工作区 diff/快照，不要求 Git 提交。独立未暂存修改不纳入本节点完成依据。

## Risks / 风险

公共 fixture 切换可能掩盖局部测试仍绑定旧实现；需检查正式调用链和测试实际依赖。上游通过不能代替当前组合版本检查，集成失败需如实回报并修复既定范围问题。

## Reception and progress / 接收与进展

- 2026-11-11 14:17:47，高级开发接收 `T06-20261111-01`，方案修订 2；授权来自用户开始实现指示、总计划分配历史及架构师消息 `room-a2493e542ba3-msg-0041`。Plan/task Accepted，总登记 assigned；实际 HEAD `be8accd90d4ae24a8aa9b8b225d8e77f8d709e96`。直接前置 T04-workspace-v1（`5a3c031a54bc2a3add8882aec01d0510bc0afb4c20a48955a9984e48149999e5`）与 T05-workspace-v1（`40b9e09f30cdc50787a2bacbf7f49b490d3f523c5f63344da35112c44eabb25a`）已接受并复算一致，同时核对 T01-workspace-v2（`a6bf39116c0aef6347fda0b7c76c2aa89f1ddfc97b21b90a310dc4390755a6ba`）、T02-workspace-v1（`3322a512d4987439d7e09842bea9400d6d6aae3c2bb74ff057d14fde164789e1`）及 T03-workspace-v1（`9afcc7396062619de5ece2cec190cc8b65252e4d639f73b4e42ec5acf69de7ae`）清单均一致。已读取实际应用 service 内容，保留既有房间改名及其他独立行为；后续按当前 HTTP/测试内容融合，不覆盖暂存区、独立 design/web 或无关修改。本节点按授权统一接线、移除旧实现并更新架构及公共夹具，必要的旧事务清理纳入集成版本；不执行 Git 写入、不操作真实库/服务、不自动进入整体 Verification。当前无阻塞，无法安全合并或需额外共享契约变更时先报协调。

- 2026-11-11 14:37:28，完成统一装配：新增 SQLAlchemyRoomStore 组合房间/消息仓储；HTTP 请求绑定统一 SQLAlchemyTransaction，成员 RPC、clear_codex、后台动作和 WebSocket 使用独立短作用域。bootstrap 关闭 runner 后 dispose 自建 Engine，借入 Database 保持调用方所有权；装配与启动失败纳入清理检查。已删除六个旧 persistence 模块及 SQLiteTransaction，迁移公共夹具和受影响 HTTP/CLI/MCP/子进程消费者，既有改名路由和应用行为未回退。定向集成 57 passed，新增生产装配边界 8 passed，纯业务 33 passed；mypy src/tests（123 文件）、migrations（2 文件）、Ruff check、format（187 文件）及暂存/未暂存 diff 空白检查通过。完整后端开发回归正在运行；当前无阻塞，不将本节点开发检查记为整体 Verification。

## Delivery and review / 交付与审查

### T06-workspace-v1 / 待主会话审查

- 执行者：高级开发；编号 `T06-20261111-01`，方案修订 2。HEAD 仍为 `be8accd90d4ae24a8aa9b8b225d8e77f8d709e96`，交付为权威共享工作区实际文件及删除清单，不执行 Git 写入。
- 接收基于已接受 T01—T05；接收时全部前置哈希一致。T06 按任务范围演进 T01 的 transaction.py（删除旧 SQLiteTransaction）和 mapper 单元测试（删除旧 records 依赖），以及 T03 的局部夹具（复用正式组合适配）。最终组合还包含独立 `Topic.messageCount` 移除后的 mapper、资源查询、房间仓储及相关测试适配；这些内容属于已验证的组合快照，不应表述为 T01/T02 除前述文件外完全未变化。
- 独立 application 房间改名实现、contracts 与 HTTP PATCH 路由保留；实际 test_room_api.py 中改名回归保留，仅更新数据库注入参数。独立 codex-integration-capabilities 文档及 web 文件未读取差异或修改；其他无关修改保留。
- 完成范围为 T06 Implementation 和开发检查；主会话仍需审查交付，整体 Verification 未自动进入。

### Actual changes / 实际变更

- 新增 `SQLAlchemyRoomStore` 与组合 `SQLAlchemyRoomData`，通过已有 RoomStore/RoomData 端口将房间与消息仓储绑定同一 Session；请求查询也借用该 Session。应用层无需导入 SQLAlchemy、取得 Session 或 commit，无模块专用 UoW。
- persistence 工厂返回 Database；HTTP persistence provider、房间/成员 provider、delivery/presence 工厂和 bootstrap 统一使用 SQLAlchemy。成员 inspect/list、clear_codex 和后台投递分别使用无请求绑定的短事务适配；WebSocket 每次补取后释放 Session。
- bootstrap 自建 Engine 在 presence、delivery 停止且文件锁释放后 dispose；装配/启动失败也释放自建资源。内部测试注入从 `store=` 改为 `database=`；借入 Database 由调用方关闭，Repository/provider 不重复关闭。正常服务器、CLI/MCP 入口和公开协议不变。
- 删除旧 `store.py`、`rooms.py`、`queries.py`、`context.py`、`positions.py`、`records.py` 及 SQLiteTransaction，无旧内部路径转发代理。原生 SQLite 行为集中保留在 sqlite.py；迁移、schema、配置和调度参数不变。
- 公共 demo fixture 用真实仓储写入原有数据；test-only RoomTestStore 组合房间和投递短动作，产品装配分别使用两种适配。T03 消息夹具复用正式 store，保留独立仓储/查询测试。
- 迁移受影响测试、子进程导入与 SQLAlchemy 异常；测试状态设置使用类型化 update/select。历史 DDL 专用 test_migration_sql.py 保留直接 sqlite3 验证例外。更新 backend-architecture.md，新增生产装配故障和资源边界回归。

### Development evidence / 开发检查

| 命令 / 检查 | 实际结果 |
| --- | --- |
| `uv run --locked pytest tests/unit -q` | 33 passed，0.38s |
| `uv run --locked pytest -o addopts=-ra tests/integration/test_request_transaction.py tests/integration/test_room_store.py tests/integration/test_room_queries.py tests/integration/test_member_sessions.py tests/integration/test_member_context.py tests/integration/test_delivery_service.py -q` | 57 passed，11.07s |
| `uv run --locked pytest -o addopts=-ra tests/integration/test_persistence_runtime.py -q` | 8 passed，1.71s |
| `uv run --locked pytest -o addopts=-ra tests -q` | 最终组合 474 passed，77.22s；覆盖全部 integration 标记、HTTP/WS/CLI/MCP、临时库和模拟协议子进程 |
| `uv run --locked mypy src tests` | 123 source files，无问题 |
| `uv run --locked mypy migrations` | 2 source files，无问题 |
| `uv run --locked ruff check .` | All checks passed |
| `uv run --locked ruff format --check .` | 187 files already formatted |
| `git diff --check`、`git diff --cached --check` | 均通过；未执行暂存或提交 |
| Python AST/导入及调用点审查 | 82 个 src Python 文件，0 违例：无 sqlite3 导入、应用/领域无 SQLAlchemy 或 infrastructure 导入、无旧模块导入、无 create_all/text()、仓储不 commit/rollback |

全部测试使用临时数据库和 fake/自有协议进程；未运行真实库、服务、Codex 或浏览器，未强加前端检查。初次完整回归为 474 passed（77.14s）；14:43 最终哈希核对发现独立并行修改 `Topic.message_count` 及 test_room_api.py 的对应字段断言，已保留并重新完整运行，最终为 474 passed（77.22s），mypy/Ruff/格式/空白检查再次通过。此前误将现有删除房间测试识别为新增，核对实际差异后澄清：删除测试原已存在，本轮并行变化为 Topic 字段移除；service/route 哈希未继续变化。本节点未修改 domain 模型或该独立断言，最新组合证据包含它们。初次 mypy 发现测试 pool 的静态类型过宽，已通过 QueuePool 类型收窄修复；初次格式检查发现本次长行/导入，已局部格式化，最终检查通过。无未完成的节点开发检查。

### Acceptance mapping / A01—A12 开发对照

| 标准 | 当前组合证据 |
| --- | --- |
| A01 | 正式 Database/Engine/sessionmaker 与 14 张表 ORM 已装配；AST 核对 src 无直接 sqlite3；删除旧运行时路径 |
| A02 | 四类能力 Repository 经中立端口使用；正式 room_store 组合房间/消息仓储共享 Session，返回业务值；应用/领域依赖审查通过 |
| A03 | test_request_transaction 验证两次用例写入和查询同请求可见、外部连接提交前不可见、响应开始时均已提交；test_persistence_runtime 验证处理/未处理异常共同回滚资源和事件，真实提交失败只返回 500 且不持久化；foundation 保留惰性读、取消和跨 worker 清理检查 |
| A04 | HTTP 成员 list/inspect 和 WebSocket 等待断言 checkedout=0；clear_codex fake 删除前断言 checkedout=0 且独立连接读到已提交 deleted_at；delivery_repository 的外部调用检查及完整后台装配回归通过 |
| A05 | foundation 当前 head/历史值往返、14 表映射及旧 revision 拒绝，room_store/room_repository 的复合外键与原子回滚回归通过；未修改迁移链或真实数据 |
| A06 | 项目规范化并发唯一性、并发成员绑定、消息序号与发布幂等回归通过；BEGIN IMMEDIATE 在首条事实查询前执行的基础检查仍通过 |
| A07 | 资源/消息/上下文失败和生产请求提交失败均验证事件共同回滚；事件分页、游标、重启补取及无变化观察不重复发事件的回归通过 |
| A08 | queue 分页/计数/范围、历史状态与回执保留、领取/清空竞争、迟到回执/备注/输入不复活、unknown 不自动重发及可选 Codex 清理回归通过 |
| A09 | 独立 context_repository 与已有 HTTP 上下文回归覆盖当前订阅/实际路由/本人发布可见性、跨房间隔离、字面搜索、双向分页、实际提供记录/位置/事件原子性和并发最大位置 |
| A10 | 调用链审查运行时 CRUD 均为 SQLAlchemy 表达式；仅 sqlite.py 的 PRAGMA、BEGIN 和固定 rowid 表达式使用原生语句，instr/julianday 函数也集中于该模块；历史 migration_sql 不变 |
| A11 | runtime 验证自建/借入 Engine 所有权、装配与启动失败清理、runner 停止/锁释放先于 dispose，以及规范化数据库路径的原锁文件身份；foundation 验证跨线程顺序收尾；HTTP/CLI/MCP 使用方式回归通过 |
| A12 | 公共/局部夹具、架构说明和全部受影响消费者已更新；最终完整后端 474 passed，类型/lint/格式及空白检查通过；本记录提供实际版本和限制 |

sqlite.py 的原生例外具体为：连接事件执行 `PRAGMA foreign_keys = ON`、`PRAGMA busy_timeout = 5000`；begin 事件按受限模式执行 `BEGIN` 或 `BEGIN IMMEDIATE`；白名单 rooms/topics/sessions/members/messages/deliveries 的固定 `{table}.rowid` 列排序。其余函数用表达式构造 `instr` 字面子串及含等号的 `julianday` 时间比较。底层仍通过 SQLAlchemy 使用 SQLite DBAPI，首版不承诺更换数据库。

### Interfaces and remaining risks / 接口与剩余风险

- 集成入口：`create_database(path, migrate_on_startup=...) -> Database`；`SQLAlchemyRoomStore(database, transaction=None)`；`SQLAlchemyRoomQueries(database, transaction=None)`；`SQLAlchemyDeliveryStore(database)`；`SQLAlchemyMemberContext(database)`。请求 owner 为既有中间件，Engine owner 为 bootstrap 或显式注入方。
- `SQLAlchemyRoomStore.write_rooms/read_rooms` 只借用统一事务；跨仓储写入与读取共用一个 Session。RPC 用例采用独立短事务适配，不能将外部失败理解为可以回滚已提交本地修改；此行为保持既有契约。
- 现有 `database.path`、`migrate_on_startup`、同步模型、SQL-first 迁移和 SubmitterLock 不变。内部 `create_app/build_app` 测试注入参数改为 Database；仓库内调用方已全部迁移，不保留旧 SQLiteRoomStore 内部 API。
- 无已知阻塞或未完成实现。风险仍是 SQLite 方言与当前 head 的边界，以及 ORM/SQL-first 迁移双重描述需要后续维护；未验证真实运行库或在线升级。本节点只交付开发证据，不自宣整体 Verification。

### Workspace version / 可核对版本

T06 清单为下表 30 项（24 个现存文件、6 个删除标记）。按路径升序，以 UTF-8 编码 `path:lowercase_sha256`，删除项用 `path:deleted`，LF 连接且末尾无 LF 后计算 SHA256；task 自身因含哈希不纳入。`T06-workspace-v1` 清单 SHA256：`83d18308ac286111379e4ae8aa653acfdb0664fb0ddc685258f380b49755c6aa`。

| 文件 | SHA256 / 删除 |
| --- | --- |
| `docs/design/backend-architecture.md` | `2dcc62538c8f00ffead7b060445ffdbc0b743fedfa71b7ea8da67f4316f3e52b` |
| `src/agent_relay/bootstrap/http.py` | `7d98bf872b4c03f94af33c75de107c1b06107905447d241bd6fcca4bb9c32b30` |
| `src/agent_relay/infrastructure/dispatch/dependencies.py` | `8e198b5ac5caaeb3c37664c6c4faf832ebe3c74ace7b5fd1cb15a1efa073648a` |
| `src/agent_relay/infrastructure/persistence/context.py` | `deleted` |
| `src/agent_relay/infrastructure/persistence/dependencies.py` | `41976e033e63d434103c054a0ca65753ee995d055249de48d09155c005a3407c` |
| `src/agent_relay/infrastructure/persistence/positions.py` | `deleted` |
| `src/agent_relay/infrastructure/persistence/queries.py` | `deleted` |
| `src/agent_relay/infrastructure/persistence/records.py` | `deleted` |
| `src/agent_relay/infrastructure/persistence/room_store.py` | `a63561f1ec80dad1f34f10e1cf133b4f0e9eaa39eadac872921b7732e26f4519` |
| `src/agent_relay/infrastructure/persistence/rooms.py` | `deleted` |
| `src/agent_relay/infrastructure/persistence/store.py` | `deleted` |
| `src/agent_relay/infrastructure/persistence/transaction.py` | `ddad4bbb6f1590f64a4fe6267340ce31e0c3b50617626cde24c0da7adf59a00e` |
| `src/agent_relay/interfaces/http/members/dependencies.py` | `3970f12bdee00689b26f031865a548e14ec7bcda1e7fd60ee7b842443767b57a` |
| `src/agent_relay/interfaces/http/persistence.py` | `9834597eaa079b1f963fa5802fded067e745c5b25d3fc82f4255c4f5edab6553` |
| `src/agent_relay/interfaces/http/rooms/dependencies.py` | `a794d57377404e5dea90def1194853beaa01e37f5ae54605a9ee48c0284e4aad` |
| `tests/integration/test_cli.py` | `678d3bf4aedb26ba525fe9d17408e672673f58aa2cf0883f7669133e069e70b4` |
| `tests/integration/test_delivery_service.py` | `63756010fd031d93489ad23dc6956e9d91a622da7b61db4b39dde184b53dbf23` |
| `tests/integration/test_mcp_server.py` | `f3e96f9200e35356e237d935d8b3d6a3cbcfc496ca774a7ce0a0eb67cc5fb36d` |
| `tests/integration/test_member_context.py` | `2a7f809c86ba299acb558ef274e566297bf24837e13c2de316f03a0572c19e1d` |
| `tests/integration/test_member_publish.py` | `344c0bc69d2b863abfa03ca4d86cfc839bc6f09c1011bd8d9d38fe4a1c6da424` |
| `tests/integration/test_member_sessions.py` | `47185bf4296a8926ab6e6dcab075849aa5156472e625b8e508c4bfc66b78107a` |
| `tests/integration/test_persistence_runtime.py` | `ec5c8c2e55c52324fc192c5a29f792f9299a676eb584872f471a78753d1c9d25` |
| `tests/integration/test_request_transaction.py` | `12d781975499da700211e4003b5ff195da23aefc1498e10fbc542874531300f2` |
| `tests/integration/test_room_api.py` | `b7da009217cf5fc96b977ce42d83e4f6a1ed4a57ea71a2512c951473c9508756` |
| `tests/integration/test_room_queries.py` | `63be5bc4a2c0535f82c7de69669ef36abb4a8e70e5b3b53b739489c2d4dec990` |
| `tests/integration/test_room_store.py` | `5e38ac16bd9ccb7c9d57157c13f6d51e141b647fa2468073b0e52027b496779d` |
| `tests/integration/test_user_members.py` | `68e081737c314fbd9c7cd0e528cfd9017f6e0d3d722d7b3c01c52578739a36c4` |
| `tests/room_fixtures.py` | `2f8ca5b47aa6769df5944c998f8275350e0c3d7b67665911e18f77b74560bb75` |
| `tests/sqlalchemy_message_fixtures.py` | `1b1ce10ea7e9e085c7454e7c6704291fac7c326484df6878a0486419399ef180` |
| `tests/unit/test_persistence_records.py` | `37c77395546b0fbd539abf6a60cbce6ac1fe1e24b71091f797255727887e1151` |

沿各原任务清单复算的集成后上游版本：T01 为 `da36ac0bae8c5c33fc49f79d1d303ce4a4f1529fe5898d62122e982a836f4240`（包括 transaction、单测及 Topic mapper 演进）；T02 为 `58fd2acc2a6b151ccd989d5ed69af7c164d1fc097ba31767b87b9ebebeb7b56f`（包含 Topic 字段独立变更的资源查询、仓储及测试适配）；T03 为 `877479dfccf85c4144a04a0dd8274d8e0e18681a3001495bfaf5dd86b1d02fba`（夹具复用调整）；T04 仍为 `5a3c031a54bc2a3add8882aec01d0510bc0afb4c20a48955a9984e48149999e5`；T05 仍为 `40b9e09f30cdc50787a2bacbf7f49b490d3f523c5f63344da35112c44eabb25a`。2026-11-11 15:00 验证时更正先前误记的 T01/T02 集成后哈希；T06 与上游清单路径去重后的 53 项组合哈希仍为 `18f64536138a34f360a4554bc5a96db26623f813641c07a7df4c6d83d0c12edb`，同一排序及 deleted 约定。

保留且未由 T06 修改的背景文件另记录：`application/rooms/contracts.py` 为 `cd98d8a91c47136eefa66dd3e5cf5699c95b962050f1c0ac167004a3eab9c4d2`，`application/rooms/service.py` 为 `15f86938ef29ff20cf96bc9f77ac2997256798ea83b6e224db73ac1544425b6a`，`interfaces/http/rooms/routes.py` 为 `263c4ab2c9ead668f02cd2c05d6baeea5cb0a559bf7244f8224330566b93d850`，`domain/rooms/models.py` 为 `8be7f7aa68405bc87426b98c2d9f48be6ce16cdc51bb91c18df56221f1e3f713`，均相对 `src/agent_relay/`。Topic 字段变化属于独立修改，本节点融合而不回退，不据此声称扩大重构范围。其他独立 design/web 改动不纳入本节点清单或完成依据。

可复制交付摘要：`T06-20261111-01 / rev2 / T06-workspace-v1 / HEAD be8accd90d4ae24a8aa9b8b225d8e77f8d709e96 / manifest 83d18308ac286111379e4ae8aa653acfdb0664fb0ddc685258f380b49755c6aa / full backend 474 passed / mypy src/tests/migrations + Ruff + diff checks passed / 已移除旧 sqlite3 运行时 / 待主会话审查，未进入整体 Verification`。
