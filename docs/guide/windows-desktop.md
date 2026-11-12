# Windows 桌面使用指南

## 启动与目录包

运行环境需要 Windows x64、Microsoft Edge WebView2 Runtime、.NET Framework 4.7.2+，以及已安装并认证的 Codex CLI。

源码启动使用 `make desktop`，会先构建前端。构建可分发制品使用 `make binary`，生成：

- `dist/AgentRelay/`：包含桌面入口 `agent-relay-gui.exe`、控制台入口 `agent-relay.exe` 和共享运行资源 `_internal/`。
- `dist/agent-relay-<version>-windows-x64.zip`：完整目录的压缩包，版本取自 `pyproject.toml`。

解压后双击 `agent-relay-gui.exe`。必须保留整个目录；目标机器无需 Python 或 Node.js。

## 配置与数据

桌面固定使用 `app` profile，配置优先级为内置 `config/app.yaml` → `~/.agent-relay/.env` → 系统环境变量。修改覆盖文件后重启应用：

```dotenv
AGENT_RELAY_SERVER__PORT=9080
AGENT_RELAY_DATABASE__PATH=./data/agent-relay.sqlite3
```

数据库相对路径从 `~/.agent-relay/` 解析；前端相对路径从程序资源目录解析。用户目录内容：

| 路径 | 用途 |
| --- | --- |
| `.env` | 用户配置覆盖 |
| `data/` | 默认数据库目录 |
| `logs/agent-relay.log` | 应用日志 |
| `webview/` | 排序等浏览器偏好 |

替换或移动程序目录会保留这些数据。桌面不读取开发环境的 `.env.dev`。

## CLI 与 MCP

桌面默认地址为 `http://127.0.0.1:9080`；端口被占用时显示启动错误。CLI/MCP 默认连接同一地址；修改服务端口后，将 `AGENT_RELAY_URL` 设为对应地址。

使用 `agent-relay.exe --help` 查看控制台命令，`agent-relay.exe mcp` 启动 stdio MCP。现有插件使用 `agent-relay mcp`，可将完整制品目录加入 `PATH`，或将 MCP 的 `command` 配置为控制台 EXE 的绝对路径。

## 关闭窗口

关闭窗口需要确认，取消后继续运行。确认后，会向本次运行发送过管理端消息的聊天室当前 Agent 发布“管理端已离线。”。通知失败会记录日志后退出，不等待 Agent 回复。
