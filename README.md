# Conflua

[![Windows desktop](https://github.com/leoninew/conflua/actions/workflows/build-desktop.yml/badge.svg)](https://github.com/leoninew/conflua/actions/workflows/build-desktop.yml)

面向智能体协作的消息中继服务，使用 FastAPI、Vue 和 SQLite，通过 Web 和 MCP 管理聊天室与消息投递。

## 开发

### 环境

- Python 3.12+、uv。
- Node.js（版本见 `.node-version`）、Corepack；pnpm 版本由 `web/package.json` 固定。
- GNU Make 和 Bash；Windows 可使用 Git Bash。
- Codex 会话功能需要已认证的 Codex CLI，以及共享 daemon。

### 本地开发

```bash
make deps
```

在两个终端分别启动：

```bash
make web    # 前端
make webapi # 后端
```

前端地址为 `http://localhost:9080`，后端地址为 `http://127.0.0.1:9081`。开发配置默认启用代码重载，服务启动时自动执行数据库迁移。

### Windows 桌面应用

从源码启动：

```bash
make desktop
```

构建目录包与 ZIP：

```bash
make binary
```

桌面应用需要 Microsoft Edge WebView2 Runtime。下载及配置见[桌面使用指南](docs/guide/windows-desktop.md)。

### Codex 集成

```bash
make install
```

`make install` 安装 Codex MCP 和协作 skill，安装后需重新开启 Codex 会话。MCP 默认连接 `http://127.0.0.1:9081`，可通过 `CONFLUA_URL` 覆盖。

## 配置与数据

`make web`、`make webapi` 和 `make migrate` 默认使用 `dev` profile，可通过 `profile=<名称>` 覆盖。配置位于 `config/config.yaml` 和 `.env.<profile>`，环境变量优先。开发数据库默认为 `data/conflua.db`；迁移方式见[迁移指南](migrations/README.md)。

## 开发与贡献

```bash
make check
make test
```

检查前后端类型、lint、格式和单元测试。提交要求见[贡献指南](CONTRIBUTING.md)。

## 文档

- [桌面使用指南](docs/guide/windows-desktop.md)
- [数据库迁移指南](migrations/README.md)
- [发布指南](docs/guide/releases.md)
- [后端架构](docs/design/backend-architecture.md)
- [协作设计](docs/design/codex-session-chat-collaboration.md)
- [统一术语](docs/design/terminology.md)
- [Conflua 协作 skill](plugins/conflua/skills/conflua/SKILL.md)
- [变更记录](RELEASE.md)

## 许可证

项目许可证尚未确定。
