# Agent Relay 后端结构与边界
最后修改时间: 2026-11-09 22:37:40

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
    persistence/                 # SQLite、查询、原子上下文、事务与迁移
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

- 发布：HTTP rooms route → `RoomService.post_message` → `RoomStore.write_rooms` → `RoomData` 事实读取 → `build_message` 路由 → 原子插入消息及投递。SQLiteRoomData 拥有连接，应用只见业务值。
- 成员绑定：`MemberSessions.add` → 短读事实 → 无数据库作用域的 `SessionDriver.inspect` → 短写重查、绑定并生成 metadata。会话底层状态在 Codex adapter 转为中立快照；实际用户仍绑定原会话。
- 查阅：HTTP member route → `MemberContext` 能力契约 → `SQLiteMemberContext` 的单存储复合事务。SQL 保持有界可见性查询，领域函数校验订阅、计算推进位置；无需额外转发服务。
- 投递：DeliveryRunner 持有单库锁并领取 pending → `DeliveryService.submit` → `QueueDriver` → 保存中立回执。首项启动及原输入核验沿现有策略执行，不因超时重新入队。
- CLI/MCP：各自入口 → `RelayClient` → HTTP 服务。身份来自已有会话上下文，错误与结果由各自协议适配，仍使用同一份持久事实。

## 装配与资源作用域

| 作用域 | 所有者与资源 |
| --- | --- |
| 进程 | bootstrap 创建设置、数据库资源工厂、会话/队列适配器及 runner；runner 拥有线程和锁，lifespan 按顺序关闭 |
| HTTP 请求 | 事务中间件创建惰性事务；persistence provider 绑定请求 store，room/member provider 只连接本用例；响应开始前提交，失败回滚 |
| 后台动作 | 每次存储操作取得独立短事务，外部 RPC 在事务之外；不同并发动作不共享连接 |
| WebSocket | event provider 取得进程查询能力，每次补取单独短读；等待客户端和下一轮时不保留数据库事务 |
| 单次 Codex 请求 | adapter 关闭本次 proxy、桥接线程和连接，不关闭共享 daemon |

持久化、Codex 和 dispatch 各自的 `dependencies.py` 为本能力提供普通工厂；HTTP provider 留在 interfaces。`app.state` 桥接数据库、驱动与 runner，不再通过业务服务反向取得数据库资源。应用不读取 `app.state`。

聊天室变化由 domain 的 `RoomChange` 值表达；SQLite 写入方法在数据写入成功后显式追加事件，并与数据变更同事务。迁移不使用事件触发器，WebSocket 仍按持久游标补取。

## 测试与运行入口

- `uv run --locked pytest` 或 `make test-unit`：默认纯业务测试，不建 SQLite、不启动 FastAPI 或协议子进程。
- `make test-integration`：SQLite、HTTP/WebSocket、CLI/MCP、Codex fixture 协议子进程及后台生命周期。测试只使用临时数据库和自有模拟协议进程。
- `make test`：全部后端和前端测试；`make check`：既有类型、lint 和格式入口。
- `python -m agent_relay.server`、`python -m agent_relay.cli`、`python -m agent_relay.migrate` 及 `agent-relay` script 保持原调用方式。旧内部 Python 模块路径随职责迁移，仓库内消费者已更新。

协议端口增加类型化回执属于 Python 内部契约，HTTP、CLI 和 MCP 仍返回原有字段。暂无生成协议代码，不创建空 `gen` 层。
