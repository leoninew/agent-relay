# Agent Relay

[![Windows desktop](https://github.com/leoninew/agent-relay/actions/workflows/build-desktop.yml/badge.svg)](https://github.com/leoninew/agent-relay/actions/workflows/build-desktop.yml)

面向智能体协作的消息中继服务，使用 FastAPI、Vue 和 SQLite，通过 Web、CLI 和 MCP 管理聊天室与消息投递。

## 功能

- 在聊天室中组织成员和话题，向 Codex 会话投递消息。
- 通过频道隔离成员、话题、消息、草稿和队列；新频道可选用独立的 Git worktree。
- 使用 Web 界面、Windows 桌面应用、CLI 或 MCP 管理和参与协作。
- 界面支持简体中文、英文和跟随系统语言，以及主题模式。

## 快速开始

### 环境

- Python 3.12+、uv。
- Node.js（版本见 `.node-version`）、Corepack；pnpm 版本由 `web/package.json` 固定。
- GNU Make 和 Bash；Windows 可使用 Git Bash。
- 使用 Codex 会话相关功能时，需要安装并认证 Codex CLI；Relay 与成员会话使用同一共享 daemon。

### 本地开发

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

打开 `http://localhost:9080`。前端将 `/api` 代理到后端 `http://127.0.0.1:9081`；`dev` 配置启用代码重载和启动迁移。新数据库为空，可在页面创建聊天室并添加已有 Codex 会话。

### Windows 桌面应用

从 [GitHub Releases](https://github.com/leoninew/agent-relay/releases) 下载 Windows x64 ZIP，完整解压后运行 `agent-relay-gui.exe`。需要 Microsoft Edge WebView2 Runtime，无需安装 Python 或 Node.js。

源码启动：

```bash
make desktop
```

也可使用 `make binary` 构建完整目录包与 ZIP。目录包含桌面入口 `agent-relay-gui.exe`、CLI/MCP 入口 `agent-relay.exe` 和运行资源，使用时须保留整个目录。安装和配置详见[桌面使用指南](docs/guide/windows-desktop.md)，制品发布见[发布指南](docs/guide/releases.md)。

### CLI 与 Codex 插件

```bash
make install
agent-relay --help
```

安装 CLI 及 Codex 的 MCP/协作 skill 后，重新开启 Codex 会话。Relay HTTP 服务需要单独启动；CLI/MCP 默认连接 `http://127.0.0.1:9081`，可通过 `AGENT_RELAY_URL` 修改地址。

无需安装 CLI 时，可在仓库中运行 `uv run --locked agent-relay --help`。频道管理命令见 `agent-relay channel --help`。资源操作必须使用全局 `--channel-id CHANNEL` 或 `AGENT_RELAY_CHANNEL_ID`；MCP 必须提供 `channel_id`，默认频道同样显式指定。例如：

```bash
agent-relay --channel-id CHANNEL member catalog ROOM
```

## 配置与数据

`make web`、`make webapi` 和 `make migrate` 默认使用 `dev` profile，可追加 `profile=<名称>` 覆盖。配置见 `config/config.yaml` 和 `.env.<profile>`，系统环境变量优先。开发环境的数据库默认位于 `data/agent-relay.sqlite3`；迁移及旧库处理见[迁移指南](migrations/README.md)。

桌面应用默认服务地址为 `http://127.0.0.1:9081`，用户配置、数据库和日志位于 `~/.agent-relay/`。具体配置优先级和目录结构见[桌面使用指南](docs/guide/windows-desktop.md#配置与数据)。

界面默认跟随系统语言，中文系统使用简体中文，其他系统使用英文。可在右上角齿轮菜单切换语言，选择保存在用户目录的 `preferences.json` 中，优先于 `config/config.yaml` 的 `preferences.language` 默认值。聊天内容和用户定义的名称保留原文。

## 频道与数据删除

左侧栏顶部可切换或新建频道。默认频道使用房间目录；新建频道可选择从当前 commit 创建 Git worktree，默认不创建。Codex 会话需使用对应频道的工作目录。

非默认频道可在详情中删除。确认后频道被软删除并切回默认频道；记录保留在数据库中，停止新的消息投递，不影响工作目录、Git worktree 和 Codex 会话。

搜索框旁的“清空”操作会要求确认，然后软删除当前频道的消息及投递记录，并移除当前无法连接的成员。话题、可连接成员和固定用户保留；界面不提供恢复入口。成员连接状态核验失败时操作报错，保留原数据。

## 开发与贡献

```bash
make check
make test
```

上述命令检查前后端类型、lint 和格式，并运行前后端单元测试。集成测试、依赖更新和提交要求见[贡献指南](CONTRIBUTING.md)。

## CI/CD

发布流水线复用本地的 `make deps`、`make check`、`make test` 和 `make binary`，完成依赖安装、静态检查、单元测试和 Windows 桌面打包。

| 平台 | 触发方式 | 制品 |
| --- | --- | --- |
| [GitHub Actions](.github/workflows/build-desktop.yml) | 推送 `v*` 标签，或手动指定已有版本标签 | ZIP 上传至 GitHub Release Assets，同时保留 Actions Artifact |
| [GitLab CI](.gitlab-ci.yml) | 推送 `vMAJOR.MINOR.PATCH` 标签 | ZIP 上传至 Generic Package Registry，并在 GitLab Release 中提供下载链接 |

版本标签必须为 `vMAJOR.MINOR.PATCH`，并与 `pyproject.toml` 中的版本一致。当前流水线用于版本发布；普通分支推送和 Pull Request 不触发上述工作流。GitHub Actions 需将标签推送到 GitHub，推送到 Gitee 不会触发；GitLab 同样需要收到对应标签。

版本更新、手动发布和 GitLab Runner 配置见[发布指南](docs/guide/releases.md)。

## 文档

- [桌面使用指南](docs/guide/windows-desktop.md)
- [数据库迁移指南](migrations/README.md)
- [发布指南](docs/guide/releases.md)
- [后端架构](docs/design/backend-architecture.md)
- [协作设计](docs/design/codex-session-chat-collaboration.md)
- [统一术语](docs/design/terminology.md)
- [Agent Relay 协作 skill](plugins/agent-relay/skills/agent-relay/SKILL.md)
- [变更记录](RELEASE.md)

## 许可证

项目许可证尚未确定。
