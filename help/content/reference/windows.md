# Windows 桌面使用指南

## 下载与启动

运行环境需要 Windows x64、Microsoft Edge WebView2 Runtime，以及可用的 Codex。认证和 daemon 检查见[运行与排障](./troubleshooting.md)。

在 [GitHub Releases](https://github.com/leoninew/conflua/releases/latest) 的 Assets 中选择 `conflua-<version>-windows-x64.zip`。双击解压目录中的 `conflua-gui.exe`；保留同一目录下的 `conflua.exe` 和 `_internal/`。运行 Conflua 不需要另装 Python 或 Node.js。

右上角「关于」显示实际桌面版本，不受另外安装的 CLI 或开发环境版本影响。

## 配置与数据

桌面固定使用 `app` profile，配置优先级从低到高为内置 `config/conflua.yaml`、`~/.conflua/.env`、进程环境变量。例如，默认端口被占用时可改为可用端口，然后重启：

```dotenv
CONFLUA_SERVER__PORT=9082
```

数据目录、日志、WebView 存储与偏好分别在 `~/.conflua/data/`、`~/.conflua/logs/`、`~/.conflua/webview/` 与 `~/.conflua/preferences.json`。移动或替换程序目录不会删除这些数据。桌面不读取开发环境的 `.env.dev`。

默认跟随系统语言；右上角齿轮菜单可手动切换「跟随系统 / 简体中文 / English」。

## CLI 与 MCP

默认地址为 `http://127.0.0.1:9081`。使用包内 `conflua.exe --help` 验证 CLI，`conflua.exe mcp` 是 stdio MCP 入口。可把包目录加入 `PATH`，或在 MCP 配置中把 `command` 设为 `conflua.exe` 的绝对路径，参数为 `["mcp"]`。改端口后同步设置 `CONFLUA_URL`。

## 关闭窗口

关闭需确认。确认后，应用向本次运行发送过管理端消息的聊天室当前 Agent 发布离线通知；不等待 Agent 回复。只要取消关闭，应用会继续运行。
