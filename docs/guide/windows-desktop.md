# Windows 桌面使用指南

## 启动与目录包

运行环境需要 Windows x64、Microsoft Edge WebView2 Runtime，以及已安装并认证的 Codex CLI。

源码启动使用 `make desktop`，会先构建前端。构建可分发制品使用 `make binary`，生成：

- `dist/conflua/`：包含桌面入口 `conflua-gui.exe`、控制台入口 `conflua.exe` 和共享运行资源 `_internal/`。
- `dist/conflua-<version>-windows-x64.zip`：完整目录的压缩包，版本取自 `pyproject.toml`。

解压后双击 `conflua-gui.exe`。必须保留整个目录；目标机器无需 Python 或 Node.js。

右上角“关于”显示当前桌面程序的版本。版本与程序代码一同打包，不受本机另外安装的 CLI、uv tool 或开发环境版本影响。

## 配置与数据

桌面固定使用 `app` profile，配置优先级为内置 `config/conflua.yaml` → `~/.conflua/.env` → 系统环境变量。修改覆盖文件后重启应用：

```dotenv
CONFLUA_SERVER__PORT=9081
CONFLUA_DATABASE__PATH=./data/conflua.db
```

数据库相对路径从 `~/.conflua/` 解析；前端相对路径从程序资源目录解析。用户目录内容：

| 路径                   | 用途                                       |
| ---------------------- | ------------------------------------------ |
| `.env`                 | 用户配置覆盖                               |
| `data/`                | 默认数据库目录                             |
| `logs/conflua.log` | 应用日志                                   |
| `webview/`             | 排序等浏览器偏好                           |
| `preferences.json`     | 界面语言等用户偏好；不存在时使用配置默认值 |

替换或移动程序目录会保留这些数据。桌面不读取开发环境的 `.env.dev`。

界面语言默认跟随系统 UI 语言：中文显示简体中文，其他显示英文。右上角齿轮菜单可切换“跟随系统 / 简体中文 / English”，保存后页面、退出确认和新离线通知立即使用同一选择；偏好文件缺失或损坏时回退配置，不自动覆盖原文件。

## CLI 与 MCP

桌面默认地址为 `http://127.0.0.1:9081`；端口被占用时显示启动错误。CLI/MCP 默认连接同一地址；修改服务端口后，将 `CONFLUA_URL` 设为对应地址。

使用 `conflua.exe --help` 查看控制台命令，`conflua.exe mcp` 启动 stdio MCP。现有插件使用 `conflua mcp`，可将完整制品目录加入 `PATH`，或将 MCP 的 `command` 配置为控制台 EXE 的绝对路径。

## 关闭窗口

关闭窗口需要确认，取消后继续运行。确认后，会向本次运行发送过管理端消息的聊天室当前 Agent 发布当前语言的新离线通知（中文为“管理端已离线。”）。通知失败会记录日志后退出，不等待 Agent 回复。系统原生按钮语言由 Windows 决定。
