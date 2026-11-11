# Agent Relay 后端结构与边界
最后修改时间: 2026-11-11 14:34:00

依据 [Python + FastAPI 架构指南修订 2](../../../best-practices/docs/guides/python-backend-service-architecture.md)。治理范围与交付见[总计划](../plan/20261109-backend-architecture-governance.md)；这是本项目实际结构说明，不复制通用标准。

## 目录与业务归属

```text
src/agent_relay/
  domain/rooms/                  # 实体、路由、成员约束与位置规则
  application/
    rooms/                       # 输入输出、资源/发布用例与存储查询端口
    members/                     # 绑定、状态观测、会话及上下文能力契约
    delivery/                    # 单次提交、启动和接收核验
  infrastructure/
    persistence/                 # SQLAlchemy 仓储、查询、事务、SQLite 方言与迁移
    codex/                       # RPC、进程桥接及协议转换
    dispatch/                    # 锁、轮询、线程池、停止及本能力装配
  interfaces/
    http/                        # 路由、provider、中间件、错误和流式响应
    cli.py                       # Click 输入输出适配
    mcp.py                       # MCP 工具和调用身份适配
    client.py                    # CLI/MCP 共用的 Relay HTTP 客户端
  bootstrap/                     # 配置、日志、开发重载和 HTTP 组合根
  server.py / cli.py / migrate.py # 公开模块启动入口
```

聊天室、成员、话题和消息仍属于紧密协作的单一业务范围；能力目录不意味着独立部署或按表拆模块。`domain` 不导入 application、协议或存储；`application` 不导入具体基础设施、FastAPI 或启动配置。Pydantic 业务值保持现有编码，应用请求和组合视图放在 `application/rooms/contracts.py`，不为各层复制同义 DTO。

## 代表调用链

- 发布：HTTP rooms route → `RoomService.post_message` → `RoomStore.write_rooms` → 房间资源与消息仓储 → `build_message` 路由 → 原子插入消息及投递。`SQLAlchemyRoomData` 组合两个仓储，借用同一 Session；应用只见业务值。
- 成员绑定：`MemberSessions.add` → 短读事实 → 无数据库作用域的 `SessionDriver.inspect` → 短写重查、绑定并生成 metadata。会话底层状态在 Codex adapter 转为中立快照；实际用户仍绑定原会话。
- 查阅：HTTP member route → `MemberContext` 能力契约 → `SQLAlchemyMemberContext` → 上下文仓储的独立短写事务。实际结果、提供记录、位置和事件一起提交；领域函数校验订阅、计算推进位置。
- 投递：DeliveryRunner 持有单库锁 → `SQLAlchemyDeliveryStore` 短事务领取 pending 并提交 → `DeliveryService.submit` → `QueueDriver` → 另一个短事务保存中立回执。首项启动及原输入核验沿现有策略执行，不因超时重新入队。
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

持久化层按房间资源、消息、投递、上下文划分 Repository；`RoomStore`、`DeliveryStore`、`MemberContext` 保留中立的业务能力边界。同一请求或用例共享事务，不新增模块专用 UoW，应用不接触 Session 或 commit。Session 串行使用，允许同步 worker 间顺序收尾，不使用线程局部 scoped_session 或跨请求可变会话。

聊天室变化由 domain 的 `RoomChange` 值表达；仓储在数据写入成功后显式追加事件，并与数据变更同事务。仓储只 flush，事务所有者 commit/rollback。投影在会话内转换为现有 DTO，消息关系按批次装配，不依赖响应时懒加载；历史投递与当前队列分别筛选，不设全局软删除过滤。

## SQLAlchemy 与 SQLite 边界

正式运行时仅保留 SQLAlchemy 实现。`Database` 规范化现有 `database.path`，创建 Engine 和禁用 autobegin/autoflush 的 sessionmaker；读事务显式 BEGIN，写事务在序号、幂等或唯一性检查前 BEGIN IMMEDIATE。后台锁仍使用同一规范化数据库路径加 `.dispatch.lock`，调度频率与并发设置保持原值。

ORM 映射当前 `queue_deleted_20261110` 的 14 张表；SQL-first Alembic 仍是 schema 来源，不调用 create_all，不隐式修复/升级不匹配的库。`migrate_on_startup` 显式开关和独立 migrate 入口保持原方式。ISO 文本类型保留时区与精度，回执类型仅保存额外 metadata，标识由独立列重建并校验。首版默认数据库仍为 SQLite。

运行时 CRUD 和动态筛选使用 SQLAlchemy 表达式。`persistence/sqlite.py` 集中保留：连接时的 `PRAGMA foreign_keys = ON`、`PRAGMA busy_timeout = 5000`，事务开始时的 `BEGIN`/`BEGIN IMMEDIATE`，白名单表的固定 rowid 排序列，以及 `instr` 字面子串、`julianday(value) <= julianday(cutoff)` 时间窗口函数。其他仓储不拼接 SQL，也不使用 text() 包装旧查询。产品源码不直接依赖 sqlite3 API；SQLAlchemy 底层仍使用 SQLite DBAPI，历史迁移 SQL 保留。

## 测试与运行入口

- `uv run --locked pytest`：默认纯业务测试，不建 SQLite、不启动 FastAPI 或协议子进程。
- `uv run --locked pytest -o addopts=-ra tests/integration`：覆盖默认 marker 过滤，运行数据库、HTTP/WebSocket、CLI/MCP、Codex fixture 协议子进程及后台生命周期测试，只使用临时数据库和自有模拟协议进程。
- `uv run --locked pytest -o addopts=-ra tests -q`：完整后端开发回归；类型检查包括 `mypy src tests` 与 `mypy migrations`。历史 DDL 专用 `test_migration_sql.py` 是直接 sqlite3 验证例外。
- `make test`：后端与前端单元测试；`make check`：既有类型、lint 和格式入口，可用 `fix=1` 自动修复。
- `python -m agent_relay.server`、`python -m agent_relay.cli`、`python -m agent_relay.migrate` 及 `agent-relay` script 保持原调用方式。旧内部 Python 模块路径随职责迁移，仓库内消费者已更新。

协议端口增加类型化回执属于 Python 内部契约，HTTP、CLI 和 MCP 仍返回原有字段。暂无生成协议代码，不创建空 `gen` 层。
