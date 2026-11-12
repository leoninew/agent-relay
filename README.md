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
make webapi
```

```bash
make web
```

前端为 `http://localhost:9081`，`/api` 代理到后端 `http://127.0.0.1:9080`。`dev` 配置已启用代码重载和启动迁移；新数据库为空，需在页面创建聊天室并添加已有 Codex 会话。

`make web`、`make webapi` 和 `make migrate` 默认使用 `dev`，可追加 `profile=<名称>` 覆盖。配置见 `config/config.yaml` 和 `.env.<profile>`，系统环境变量优先。

数据库默认位于 `data/agent-relay.sqlite3`。手动迁移、修改结构及旧库处理见[迁移指南](migrations/README.md)。

聊天室搜索框右侧的“清空”按钮会先要求确认，再软删除当前聊天室全部消息及投递记录，并移除当前无法连接的成员。话题、可连接成员与固定用户保留；界面不提供恢复入口。成员连接状态核验失败时操作报错，保留原数据。

## Windows 桌面应用

需要 Windows 和 Microsoft Edge WebView2 Runtime。源码启动：

```bash
make desktop
```

桌面默认服务地址为 `http://127.0.0.1:9080`，用户配置和数据位于 `~/.agent-relay/`。构建完整目录包与 ZIP：

```bash
make binary
```

产物位于 `dist/AgentRelay/`，提供 `agent-relay-gui.exe`（桌面）和 `agent-relay.exe`（CLI/MCP），运行时须保留整个目录。详见[桌面使用指南](docs/guide/windows-desktop.md)；CI 下载与 GitLab Release 配置见[发布指南](docs/guide/releases.md)。

## 开发检查

```bash
make check
make test
```

依次检查前后端类型、lint 和格式，运行后端与前端单元测试。单测按层隔离依赖，前端只验证规则、状态和请求契约，不包含 UI 或性能测试。使用 `make check fix=1` 自动修复 lint 和格式问题。

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
| `tests/unit/` | 后端单元测试 |
| `migrations/` | SQLite SQL 与 Alembic revision |
| `scripts/` | 本地安装与制品打包 |

- [后端架构](docs/design/backend-architecture.md)
- [协作设计](docs/design/codex-session-chat-collaboration.md)
- [统一术语](docs/design/terminology.md)
- [Agent Relay 协作 skill](plugins/agent-relay/skills/agent-relay/SKILL.md)
- [变更记录](RELEASE.md)
