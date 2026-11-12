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

## Windows 桌面应用

桌面与浏览器使用同一前端和 API。源码启动会先构建前端，再打开 WebView2 窗口：

```bash
make desktop
```

需要 Windows、Microsoft Edge WebView2 Runtime 和 .NET Framework 4.7.2+。Codex CLI 仍须预先安装并认证。桌面默认使用 `127.0.0.1:9080`；该端口被占用时显示启动错误，日志位于 `~/.agent-relay/logs/agent-relay.log`。

桌面固定使用 `app` profile，配置依次读取内置 `config/app.yaml`、`~/.agent-relay/.env`、系统环境变量。用户覆盖示例：

```dotenv
AGENT_RELAY_SERVER__PORT=9080
AGENT_RELAY_DATABASE__PATH=./data/agent-relay.sqlite3
```

数据库相对路径从 `~/.agent-relay/` 解析；前端相对路径从程序资源目录解析。数据库默认在 `~/.agent-relay/data/`，日志在 `logs/`，桌面排序等浏览器偏好在 `webview/`。更换程序目录保留这些数据；桌面不读取开发 `.env.dev`。修改服务端口后，CLI/MCP 的 `AGENT_RELAY_URL` 也需指向相同端口。

关闭窗口先确认。取消继续运行；确认后向本次运行发送过管理端消息的聊天室当前 Agent 发布“管理端已离线。”。通知复用正常投递，失败记录日志后退出，不等待 Agent 回复；正在提交的 RPC 完成后才释放数据库和后台锁。

## Windows 目录包

在 Windows 的 GNU Make/Bash 环境中构建，入口会同步锁定的桌面依赖并构建前端：

```bash
make binary
```

产物为 `dist/AgentRelay/`。必须保留整个目录，包括 `agent-relay-gui.exe`（桌面窗口）、`agent-relay.exe`（控制台 CLI/MCP）及 `_internal/`（Python、WebView 依赖、默认配置、前端和迁移资源）。目标机器无需 Python 或 Node.js；仍需前述 WebView2/.NET 和 Codex 运行前提。

`make binary` 同时将整个目录压缩为 `dist/agent-relay-<version>-windows-x64.zip`，版本取自 `pyproject.toml`。代码实现阶段保留单元与静态检查；实际窗口、数据库迁移和 CLI/MCP 使用真实制品验证，不增加集成测试入口。

直接使用 `agent-relay.exe mcp` 启动 stdio MCP。现有插件使用 `agent-relay mcp`，可将完整目录加入 `PATH`，或将 MCP 的 `command` 配置为该控制台 EXE 的绝对路径。双击 GUI 前确认 CLI/MCP 指向同一服务地址。

GitHub Actions 的 `Build Windows desktop` 支持手动 `workflow_dispatch` 和 `v*` tag push。Windows x64 runner 按版本文件准备工具，通过 `make deps`、`make check`、`make test` 和 `make binary` 生成完整 ZIP，在对应 run 的 Artifacts 下载。tag 必须等于项目版本前加 `v`（例如 `v0.1.0`）；此 workflow 只上传 Actions artifact。

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
| `tests/unit/` | 后端单元测试 |
| `migrations/` | SQLite SQL 与 Alembic revision |
| `scripts/install.py` | 本地插件/skill 的预检、安装同步和状态查询，供 `make install` 使用 |
| `scripts/binary.py` | 读取项目版本、核对 tag、压缩完整桌面目录并输出 CI artifact 路径，供 `make binary` 使用 |

`scripts/` 只保留实际安装和制品操作，独立验证探针已删除。

- [后端架构](docs/design/backend-architecture.md)
- [协作设计](docs/design/codex-session-chat-collaboration.md)
- [统一术语](docs/design/terminology.md)
- [Agent Relay 协作 skill](plugins/agent-relay/skills/agent-relay/SKILL.md)
- [变更记录](RELEASE.md)
