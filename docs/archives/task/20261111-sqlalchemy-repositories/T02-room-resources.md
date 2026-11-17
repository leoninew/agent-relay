# Task / 子任务 T02：房间资源 Repository
最后修改时间: 2026-11-11 13:21:17

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[SQLAlchemy 与 Repository 重构](../../intent/20261111-sqlalchemy-repositories.md)。
- 权威总计划：[修订 2](../../plan/20261111-sqlalchemy-repositories.md)，协调根 `D:/SourceCodes/mywork/agent-relay`；任务 ID：T02。
- 依赖、版本条件、执行者和分配编号由总计划唯一维护；本文不独立授予执行权。

## Handoff basis / 交接依据

实施前按 SpecFlow references/task-coordination.md 核对计划接受、用户实施授权、有效分配和前置交付；当前分配以总计划为准。执行者只在本文接收/进展/交付章节写事实，通过 Agent Relay 定向回报主会话。

## Goal and acceptance / 目标与验收

交付房间资源 Repository 与资源读取，覆盖 A02、A05、A06、A07；T03 可直接使用本节点的资源事实，不再自行读取 sqlite3。

- 房间、默认话题、固定用户、成员/会话/订阅的读写及删除语义保持。
- 资源差异、订阅替换、观测检查点与对应事件同事务；业务冲突和跨房间关联约束保持。
- ORM 实体不泄漏，资源结果顺序和原有时间字段保持。

## Inputs and eligibility / 输入与可开始条件

前置以总计划定义表为准。消费已接受且可访问的模型、RoomRepository 契约、映射和事务实现；实际前置版本在派发时登记，不以方案 Accepted 代替实现可用。

## Scope and files / 范围与文件

- 新增 persistence/repositories/rooms.py、resource_queries.py 和包入口；局部 tests/integration/test_room_repository.py。
- 参考旧 store.py 的 save_resources/insert_room/save_observation 和 queries.py 的资源读取，不提前删除旧实现。
- 不修改公共 tests/room_fixtures.py、bootstrap/provider 或共享 T01 模型/契约；需要调整时回报主会话。

## Technical decisions / 局部技术设计

- 将 RoomState 与 original 的差异保存映射到 ORM/批量表达式，保持全量订阅替换的原有业务语义；不在业务值中加入 Session 或 ORM 状态。
- 复用固定的 SQLite 排序表达式，保持用户/Agent 和资源次序；删除房间遵循复合外键顺序，不假定新增了数据库级级联删除。
- 项目唯一、活动成员名/会话和活动话题名的检查与保存处于同一写作用域，数据库约束继续兜底。
- 观测只在值变化或到达检查点时更新；保留空值/名称更新和时间窗口语义，不使每次轮询都产生事件。
- 数据写入与显式事件共用借入 Session，返回前在必要位置 flush；Repository 不负责提交。

## Implementation outline / 实施安排

1. 在 T01 基础上实现资源读写与值映射，输出资源读取接口。
2. 迁移资源差异保存、订阅替换、观察检查点和显式事件写入。
3. 用局部 Session fixture 验证原子性、约束与顺序，记录交付供消息查询节点复用。

## Checks and delivery / 检查与交付

- `uv run --locked pytest -o addopts=-ra tests/integration/test_room_repository.py -q`：资源往返、固定用户、删除顺序、订阅替换、约束失败及事件共同回滚。
- 保留 tests/integration/test_room_store.py、test_member_sessions.py 中相关行为的等价覆盖；全局 fixture 尚未切换时，新增测试必须实际使用新 Repository，不能只报告旧实现测试通过。
- 并发项目创建、成员绑定，以及观察无变化/检查点更新纳入定向回归；失败后读取新作用域确认无残留数据或事件。
- 运行当前范围 mypy/Ruff，记录实际命令、结果、前置版本、未运行项和对 T03 的读取入口。

## Risks / 风险

ORM 关系级联可能改变删除或历史保留语义；Python 差异与批量更新混用可能产生旧 identity map；排序和观察时间比较不能随映射方式变化。

## Reception and progress / 接收与进展

- 2026-11-11 13:10:27，高级开发接收 `T02-20261111-01`，方案修订 2；授权消息 `room-a2493e542ba3-msg-0016`。Plan/task Accepted，总登记 assigned；实际 HEAD `be8accd90d4ae24a8aa9b8b225d8e77f8d709e96`。已核对前置 T01-workspace-v2 accepted，11 文件实际清单 SHA256 `a6bf39116c0aef6347fda0b7c76c2aa89f1ddfc97b21b90a310dc4390755a6ba` 一致。仅实施本 task 资源仓储/读取和局部测试；冻结 T01/公共夹具，保留独立 design 修改；不切正式装配、不操作真实库或服务、不执行 Git 写入。

- 2026-11-11 13:21:17：新资源仓储、读取与局部测试完成。32 个新 Repository 案例通过；连同 T01、既有房间/成员行为回归共 90 passed。T01 冻结清单哈希仍一致；期间工作区出现独立 web/src/domains/room/MessageDetails.vue、room.css 及对应 test 修改，未读取其差异或编辑。

## Delivery and review / 交付与审查

- 交付：`T02-20261111-01 / T02-workspace-v1`，方案修订 2；工作区 `D:/SourceCodes/mywork/agent-relay`，HEAD `be8accd90d4ae24a8aa9b8b225d8e77f8d709e96`。有效前置为已接受 `T01-workspace-v2`，实际 SHA256 `a6bf39116c0aef6347fda0b7c76c2aa89f1ddfc97b21b90a310dc4390755a6ba` 已再次核对保持冻结。
- 本节点新增 4 个源码/测试文件：persistence/repositories/__init__.py、repositories/rooms.py、resource_queries.py；tests/integration/test_room_repository.py。按完整仓库相对路径排序，以 `path:sha256` 行、LF 连接且无末尾 LF 计算的清单 SHA256 为 `3322a512d4987439d7e09842bea9400d6d6aae3c2bb74ff057d14fde164789e1`。仅另写本 task 的接收、进展、交付和修改时间；未修改 T01、公共夹具、原适配或正式装配。
- A02：`SQLAlchemyRoomRepository(session)` 结构满足 application RoomRepository Protocol，资源写入使用 ORM/表达式，不依赖 sqlite3、不拼接 SQL。`ResourceQueries(session)` 返回 Pydantic 业务值与 RoomState，不返回 ORM；各仓储/查询借用传入的同一 Session，不提交/回滚，也不自建 Session。
- A05：房间插入及固定用户、资源差异/订阅替换及显式事件在同一 Session flush；约束失败、观察第二段失败、请求撤销和房间删除失败均由拥有者回滚。借入请求作用域退出后外部连接仍看不到写入，finish(False) 后资源和事件均无残留。
- A06：保留固定用户的身份/空会话与 user activity_source；四默认话题仍由现有 RoomService 创建，本节点验证其原样持久化。Topic/Session 按 rowid，Member 按 session_id IS NULL 再 rowid，订阅按 position；修改/rejoin 保留插入序，软删除仍可作为历史读出并释放活动名/会话绑定。只替换发生变化的成员订阅，未从 State 显式出现的资源不额外物理删除。
- A07：项目唯一路径、活动话题名/成员名/成员会话、固定用户 CHECK、跨房间复合外键在真实迁移临时库验证；并发标准化项目创建、同会话成员加入各 8 次竞争均仅 1 成功，其余业务冲突。按现有依赖顺序删除完整 14 表资源，含自回复消息、投递、上下文、位置；其他房间数据不受影响，删除失败可完整回滚。
- 观察语义：值变化、空时间或达到含等号的 30 秒检查点才更新及记录事件；用冻结的 time_at_or_before 统一 julianday <=。验证时间倒退/0/29 秒不写、30/31 秒写、跨时区等效时间，presence/activity/source/name/NULL 各自仅更新对应资源。保留成员别名/订阅与 None 会话名；已移除成员不复活。bulk 更新/删除使用 synchronize_session='fetch'，测试持有的 ORM 实体在同一 Session 中亦读取到正确新值。
- T03 可用读取入口：`ResourceQueries(session).room/rooms/project_exists/resources/publisher/member_for_session/joined_members/bindings/metadata/positions`；RoomRepository 暴露对应资源能力并组合这些查询。resources 固定 5 次 SELECT 读取房间、话题、全量订阅、成员、会话，1/20 Agent 的查询次数一致；metadata 额外批量聚合消息/话题/活动投递、事件游标和订阅位置。positions 保留活动订阅过滤、默认 seq=0、实际时间与按话题后续消息数；历史软删除话题的消息计数仍保留。T03 可在自己的借入 Session 内直接组合，不调用旧 sqlite3 读取。
- 实际检查：`uv run --locked pytest -o addopts=-ra tests/integration/test_room_repository.py -q`：32 passed，全部实际使用新 Repository/ResourceQueries。`uv run --locked pytest -o addopts=-ra tests/integration/test_room_repository.py tests/integration/test_sqlalchemy_foundation.py tests/integration/test_request_transaction.py tests/integration/test_room_store.py tests/integration/test_member_sessions.py tests/unit/test_persistence_records.py -q`：90 passed；其中旧适配回归只证明过渡兼容，不替代新实现检查。
- 静态检查：`uv run --locked mypy src tests`：116 source files 成功；`uv run --locked ruff check .`、`uv run --locked ruff format --check .`：通过（180 files）；`git diff --check`：通过。只对本节点新文件执行 Ruff 修整。
- 风险/未完成：当前无已知阻塞。T03 尚需实现消息及完整 RoomQueries 组合，T04/T05 尚需后台投递/上下文写适配；T06 才接线、移除旧 SQLiteTransaction/sqlite3 路径并验证最终调用链。两种事务类仅为过渡，最终保留统一 SQLAlchemy 实现。未运行总体 Verification、未操作真实库/服务、未执行 Git 写入；独立 design/web 修改均保留。请主会话按清单和证据审查，接受后放行 T03。
