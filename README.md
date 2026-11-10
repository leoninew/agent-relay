# Agent Relay

面向智能体协作的消息中继服务，使用 FastAPI、Vue 和 SQLite，通过 Web、CLI 和 MCP 管理聊天室与消息投递。

## 环境

- Python 3.12+、uv。
- Node.js（版本见 `.node-version`）、Corepack；pnpm 版本由 `web/package.json` 固定。
- GNU Make 和 Bash；Windows 可使用 Git Bash。
- 本机已安装并认证的 Codex CLI；Relay 与成员会话使用同一共享 daemon。

## 本地开发

在仓库根目录安装依赖：

```bash
make deps
```

在两个终端分别启动后端和前端：

```bash
make webapi profile=dev
```

```bash
make web profile=dev
```

前端为 `http://localhost:9081`，`/api` 代理到后端 `http://127.0.0.1:9080`。`dev` 配置已启用代码重载和启动迁移；新数据库为空，需在页面创建聊天室并添加已有 Codex 会话。

默认配置位于 `config/config.yaml`，开发配置位于 `.env.dev`。环境变量使用 `AGENT_RELAY_` 前缀和 `__` 分隔层级，优先级为默认配置 → `.env.<profile>` → 系统环境变量。Make 默认使用 `dev`，直接运行 Python 入口时通过 `AGENT_RELAY_PROFILE` 选择环境，未设置则为 `prod`。

数据库默认位于 `data/agent-relay.sqlite3`。手动迁移、修改结构及旧库处理见[迁移指南](migrations/README.md)。

## 开发检查

```bash
make check
make test
```

依次检查前后端类型、lint 和格式，运行后端与前端单元测试。使用 `make check fix=1` 自动修复 lint 和格式问题。

修改依赖后更新并提交对应的 `uv.lock` 或 `web/pnpm-lock.yaml`。

## CLI 与 Codex 插件

```bash
make install
agent-relay --help
```

安装 CLI 及 Codex 的 MCP/协作 skill 后，重新开启 Codex 会话。Relay HTTP 服务需要单独启动；CLI/MCP 默认连接 `http://127.0.0.1:9080`，可通过 `AGENT_RELAY_URL` 修改地址。

无需安装 CLI 时，可在仓库中运行 `uv run --locked agent-relay --help`。

## 代码与文档

| 路径 | 内容 |
| --- | --- |
| `src/agent_relay/` | 后端业务、适配器、CLI 与 MCP |
| `web/` | Vue 前端 |
| `tests/unit/`、`tests/integration/` | 后端单元测试与集成测试 |
| `migrations/` | SQLite SQL 与 Alembic revision |

- [后端架构](docs/design/backend-architecture.md)
- [协作设计](docs/design/codex-session-chat-collaboration.md)
- [统一术语](docs/design/terminology.md)
- [Agent Relay 协作 skill](plugins/agent-relay/skills/agent-relay/SKILL.md)
