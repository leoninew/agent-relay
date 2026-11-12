# Agent Relay 后端结构与边界
最后修改时间: 2026-11-12 11:12:59

依据 [Python + FastAPI 架构指南修订 2](../../../best-practices/docs/guides/python-backend-service-architecture.md)。本轮职责调整见[总计划](../plan/20261111-backend-responsibility-alignment.md)及[契约调查](../task/20261111-backend-responsibility-alignment/T01-responsibility-contracts.md)；这是本项目实际结构说明，不复制通用标准。

## 目录与业务归属

```text
src/agent_relay/
  domain/rooms/
    models/                      # 领域实体、值对象、状态与类型；按房间、消息、投递等分文件
    resources.py / members.py    # 初始化、资源及成员生命周期规则
    rules.py / positions.py      # 路由、发布重放与位置推进规则
    delivery.py                  # 提交结果与失败转换
    errors.py                    # 领域错误
  application/
    dto/                         # 按业务模块组织请求、结果、投影及端口传递的数据
    rooms/                       # 房间/话题生命周期、资源和查询端口
    members/                     # 加入、编辑、退出、候选会话与状态观测
    messages/                    # 发布、幂等/引用校验、发布查找与队列管理
    context/                     # 上下文提供用例与纯读取端口
    capabilities/                # 技能、MCP 目录查询与可用性核验
    delivery/                    # 恢复、单次提交、启动和接收核验
    transactions.py              # RepositoryScope[T]：read/write 统一作用域
  infrastructure/
    persistence/                 # SQLAlchemy 仓储、查询、事务、SQLite 方言与迁移
    codex/                       # models.py 存放协议数据；catalog/driver 处理转换与 RPC
    dispatch/                    # 锁、轮询、线程池、停止及本能力装配
  interfaces/
    http/                        # 路由、provider、中间件、错误和流式响应
    cli.py                       # Click 输入输出适配
    mcp.py                       # MCP 工具和调用身份适配
    client.py                    # CLI/MCP 共用的 Relay HTTP 客户端
    dto.py                       # 客户端结果、HTTP 响应等接口数据
  bootstrap/
    settings.py                  # 配置模型与字段校验
    config.py                    # 配置加载与缓存
    logging.py / reload.py       # 日志与开发重载
    http.py                      # HTTP 组合根
  server.py / cli.py / migrate.py # 公开模块启动入口
```

聊天室、成员、话题和消息仍属于紧密协作的单一业务范围；能力目录不意味着独立部署或按表拆模块。`domain` 不导入 application、协议或存储；`application` 不导入具体基础设施、FastAPI 或启动配置。Pydantic 业务值保持现有 camelCase 编码，不为各层复制同义 DTO。`Delivery` 保留业务身份与已核验的回执事实，原始 RPC input/response 不进入业务值。

## 数据结构与流程分离

- `domain/rooms/models/` 管理领域实体、值对象及其不变量校验；`RoomState`、`VisibilityScope`、`SubmissionFailure` 与关联领域类型一起存放。包内按房间、消息、能力引用、投递、可见范围分文件，外部通过模型包导入；状态转换、路由和生命周期流程留在规则模块。
- `application/dto/` 按业务模块集中管理请求、结果、读投影以及端口参数/回执。`TopicPosition` 位于 `positions.py`，投递请求/回执位于 `delivery.py`，会话快照位于 `members.py`。Service 组织用例，ports/sessions 定义协议与错误，不再声明这些数据类。
- Codex wire schema 和能力绑定快照集中在 `infrastructure/codex/models.py`；`SkillDiscovery.public_catalog()` 保留从已解析绑定到应用目录的简单投影。原始协议解码、身份生成与可用性转换由 `catalog.py` 负责，RPC 留在 `driver.py`。现有 `infrastructure/persistence/models.py` 已独立管理 ORM 映射，继续保留。
- 接口数据集中在 `interfaces/dto.py`，客户端及路由只负责协议操作；配置模型集中在 `bootstrap/settings.py`，加载入口仍是 `bootstrap/config.py` 的 `load_settings`。
- 仅在相关数据类型达到需要分组的规模时建立包；少量类型使用独立模块。新增数据类放入所属层的数据模块，避免与 Service、规则函数、驱动或配置加载流程混放。

## 责任与抽象

| 对象 | 本项目责任与保留理由 |
| --- | --- |
| 领域规则 | `resources` 决定固定用户、默认话题及话题约束；`members` 决定成员限制、退出、重命名及观测窗口；`rules` 决定路由/发布重放；`models/context` 表达可见范围，`positions` 决定推进规则；`delivery` 决定提交结果与失败语义 |
| Service | 组织完整业务动作、读取所需事实、调用规则并安排一致性边界；不访问 Session，不提交事务 |
| Repository | 读写持久事实，保留条件更新、原身份/删除标记保护、原子领取、位置单调推进及事件保存；不隐藏完整上下文提供流程 |
| Query/Reader | 形成无副作用的快照、分页、统计、catalog/positions，可由接口直接调用；无需增加转发 Service |
| 内部 loader | `ResourceQueries/MessageQueries` 在 Session 内批量装配关系，供仓储与公开查询适配复用，只对持久化层可见 |
| Scope/Store | `SQLAlchemyScope` 实现统一仓储作用域；RoomStore 同时提供组合资源/消息能力与 queries；具体 DeliveryStore 为每个后台存储动作提供独立短事务 |
| driver/runner | driver 处理 RPC、技能 input 绑定、原始身份校验和协议转换；runner 管锁、调度、线程池与退出，调用应用动作 |

删除无消费者的 `RoomChange` 对象，保留实际事件类型 `RoomChangeKind`；删除仅重复父能力的 `MemberContext/DeliveryStore` Protocol 和旧整用例上下文适配器。具体 `SQLAlchemyDeliveryStore` 仍有短事务所有者的独立责任。

## 代表调用链

- 创建房间：`RoomService.create_room` → 领域 `new_room_state` 生成固定用户/话题 → `RoomStore.write` 中显式 `insert_room(room, user)`、保存资源及事件；RoomService 只负责房间与话题生命周期。
- 成员绑定：`MemberService.add` → 短读与领域约束 → 退出作用域后 `SessionDriver.inspect` → 短写重查、绑定并生成 metadata。编辑/退出也在 MemberService；观测窗口由领域提供 cutoff，仓储以包含等号的时间条件写入。会话底层状态在 Codex adapter 转为中立快照。
- 发布：HTTP room/member route → `MessageService.post_message` → `RoomStore.write` → 发布身份/幂等/引用校验 → 领域 `build_message` 路由 → 原子插入消息、投递及事件。`SQLAlchemyRoomData` 组合两个仓储，借用同一 Session；应用只见业务值。
- 清队列：`MessageService.clear_queue_with_codex` → 独立短写保存删除标记并取得远端目标 → 提交并释放 → `QueueDriver.delete`。远端结果只影响返回统计，不回退本地删除或复活队列。
- 提供上下文：HTTP member route → `ContextService.provide` → 一个 `RepositoryScope.write`：读取有效订阅 → 领域订阅检查/VisibilityScope → SQL 可见筛选和 limit+1 → 对实际返回消息计算位置 → 保存 query/messages/位置/事件 → 读取最终位置并返回。时间、query ID、空结果处理和游标归应用；仓储保留 SQL 与原子记账，不再提供 `query` 整用例。
- 投递：DeliveryRunner 持有单库锁 → `DeliveryService.recover` 标记中断提交 → `SQLAlchemyDeliveryStore` 短事务原子领取并提交 → `DeliveryService.submit` 调用 QueueDriver → 领域提交结果 → 短事务条件保存 → 受保护首项启动。`observe` 核验原输入，不因未知结果或启动失败重新入队。
- 简单读取：HTTP → RoomQueries 或 ContextQueries → SQLAlchemy 查询适配 → 批量投影；不构造完整用例类。WebSocket 使用独立 event 查询，每次补取后释放再等待。
- CLI/MCP：各自入口 → `RelayClient` → HTTP 服务。身份来自已有会话上下文，错误与结果由各自协议适配，仍使用同一份持久事实。

## 装配与资源作用域

| 作用域 | 所有者与资源 |
| --- | --- |
| 进程 | bootstrap 创建 Database、Engine/sessionmaker、驱动及 runner；先停止 presence，再停止 delivery 并释放锁，最后 dispose 自建 Engine；装配/启动失败也清理自建资源 |
| HTTP 请求 | 中间件创建惰性 SQLAlchemyTransaction，首次写入后各仓储及 RoomQueries 共享同一 Session；响应开始前统一提交，错误、异常或取消回滚，提交失败不发送成功响应 |
| RPC 用例 | 成员 inspect/list 和 clear_codex 使用不绑定请求写会话的 store；短读/短写退出并释放 Session 后再调用外部协议，清队列先提交本地删除标记 |
| 后台动作 | 每次存储操作取得独立短事务，外部 RPC 在事务之外；不同并发动作不共享 Session |
| WebSocket | event provider 取得无请求绑定的 SQLAlchemyRoomQueries，每次补取单独短读；send/receive/等待期间不保留 Session |
| 单次 Codex 请求 | adapter 关闭本次 proxy、桥接线程和连接，不关闭共享 daemon |

持久化、Codex 和 dispatch 各自的 `dependencies.py` 为本能力提供普通工厂；HTTP provider 留在 interfaces。`app.state` 桥接 Database、驱动与 runner，应用不读取 `app.state`。测试装配可用 `create_app(database=...)` 借入 Database，由调用方关闭；派生 store、查询和 Repository 不关闭借入的 Engine，不自行结束请求事务。

持久化层按房间资源、消息、投递、上下文划分 Repository。`RepositoryScope[T]` 只定义 read/write；`SQLAlchemyScope` 用工厂绑定 Session，借入 Session 时不提交/关闭，以 Database 创建独立作用域时由 Database 收尾，绑定请求事务时由中间件统一收尾。同一请求或用例可组合多个仓储，不新增模块专用 UoW，应用不接触 Session 或 commit。Session 串行使用，允许同步 worker 间顺序收尾，不使用线程局部 scoped_session 或跨请求可变会话。

仓储在数据写入成功后显式追加事件，并与数据变更同事务。仓储只 flush，事务所有者 commit/rollback。投影在会话内转换为业务值/视图，消息关系按批次装配，不依赖响应时懒加载；历史投递与当前队列分别筛选，不设全局软删除过滤。

上下文可见性独立于管理端消息 scope：自己发布、实际 Delivery、当前有效订阅三种事实取并集；human 接收人列表不扩大权限。SQL 在分页前过滤，lookahead 不记账；空结果不记录。首次位置插入与 seq 条件 UPDATE RETURNING 在同一 BEGIN IMMEDIATE 内完成，等值/更早位置不更新时间或重复事件，任何记录/结果/提交失败一起回滚。

投递合法主链为 pending → submitting → queued/rejected/unknown，中断 submitting → unknown，实际匹配输入使 queued/unknown → received。领域表达结果，仓储继续核对旧状态、原身份、deleted_at 和单次启动标记，迟到结果不覆盖已保存回执或清空事实。`history_cursors` 由进程级 DeliveryService 拥有；runner 的 observations 防止同 session 并发观测，不改变历史遍历策略或持久化游标。关闭等待所有活动任务结束后才释放锁/Engine。

## SQLAlchemy 与 SQLite 边界

正式运行时仅保留 SQLAlchemy 实现。`Database` 规范化现有 `database.path`，创建 Engine 和禁用 autobegin/autoflush 的 sessionmaker；读事务显式 BEGIN，写事务在序号、幂等或唯一性检查前 BEGIN IMMEDIATE。后台锁仍使用同一规范化数据库路径加 `.dispatch.lock`，调度频率与并发设置保持原值。

ORM 映射当前 `capabilities_json_20261111` 的 14 张表，消息能力引用直接保存在 `messages.capabilities` JSON 列；SQL-first Alembic 仍是 schema 来源，不调用 create_all，不隐式修复/升级不匹配的库。`migrate_on_startup` 显式开关和独立 migrate 入口保持原方式。ISO 文本类型保留时区与精度，回执类型仅保存额外 metadata，标识由独立列重建并校验。首版默认数据库仍为 SQLite。

运行时 CRUD 和动态筛选使用 SQLAlchemy 表达式。`persistence/sqlite.py` 集中保留：连接时的 `PRAGMA foreign_keys = ON`、`PRAGMA busy_timeout = 5000`，事务开始时的 `BEGIN`/`BEGIN IMMEDIATE`，白名单表的固定 rowid 排序列，以及 `instr` 字面子串、`julianday(value) <= julianday(cutoff)` 时间窗口函数。其他仓储不拼接 SQL，也不使用 text() 包装旧查询。产品源码不直接依赖 sqlite3 API；SQLAlchemy 底层仍使用 SQLite DBAPI，历史迁移 SQL 保留。

## 测试与运行入口

- `uv run --locked pytest`：默认单元测试，按领域、应用、基础设施、配置与接口分类，不建 SQLite、不启动 FastAPI 或协议子进程。
- `uv run --locked mypy src tests`、`uv run --locked mypy migrations`：检查源码、单测和迁移脚本类型。
- 迁移链及 SQL 使用 `alembic history`、`alembic heads`、`alembic upgrade queue_deleted_20261110:head --sql` 离线核对，不执行真实 SQLite 测试。
- `make test`：后端与前端单元测试；`make check`：既有类型、lint 和格式入口，可用 `fix=1` 自动修复。
- `python -m agent_relay.server`、`python -m agent_relay.cli`、`python -m agent_relay.migrate` 及 `agent-relay` script 保持原调用方式。旧内部 Python 模块路径随职责迁移，仓库内消费者已更新。

单测 fixture 按需放在对应目录的 `conftest.py`，仓储和驱动使用端口 Mock 或局部内存替身。已移除依赖旧 `tests/support` 的集成测试及协议子进程脚手架，不恢复共享模拟仓储。

测试按责任选择最小范围：

- 领域测试直接验证路由、去重、固定用户、订阅和位置等规则；应用测试使用轻量仓储、驱动 fake 验证编排、保存的事实及 RPC 前退出作用域。
- 基础设施测试验证 DTO/ORM 转换、序列化、事务提交/回滚编排和 RPC 输入输出，数据库会话及 RPC 均使用替身。
- 接口测试验证参数、请求编码、错误契约、MCP 工具目录及事务中间件，不启动真实 HTTP 服务或连接数据库。

重复断言和没有实际风险依据的冷门异常组合直接删除，不要求逐项迁为单元测试。按当前用户约束，不增加跨层、真实 SQLite、集成或端到端测试。

协议端口增加类型化回执属于 Python 内部契约，HTTP、CLI 和 MCP 仍返回原有字段。暂无生成协议代码，不创建空 `gen` 层。
