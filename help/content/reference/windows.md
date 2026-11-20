# Windows 桌面使用指南

## 下载与启动

Windows 包里有两个入口：`conflua-gui.exe` 打开聊天室，`conflua.exe` 供终端和 MCP 调用。两者在 Windows x64 上运行；桌面窗口需要 Microsoft Edge WebView2 Runtime。要让成员接到消息，还需要可用的 Codex，见[运行与排障](./troubleshooting.md)。

在 [GitHub Releases](https://github.com/leoninew/conflua/releases/latest) 的 Assets 中选择 `conflua-<version>-windows-x64.zip`。双击解压目录中的 `conflua-gui.exe`；保留同一目录下的 `conflua.exe` 和 `_internal/`。运行 Conflua 不需要另装 Python 或 Node.js。

右上角「关于」显示实际桌面版本，不受另外安装的 CLI 或开发环境版本影响。

## 配置与数据

端口被占用时，在 `~/.conflua/.env` 里给桌面服务换一个空闲端口，然后重启。例如：

```dotenv
CONFLUA_SERVER__PORT=9082
```

修改没有生效？桌面用的是 `app` profile，不读开发用的 `.env.dev`。用户的 `.env` 覆盖内置 `config/conflua.yaml`，而进程环境变量又会覆盖 `.env`。换程序目录不用搬聊天记录：数据在 `~/.conflua/data/`，日志在 `~/.conflua/logs/`，WebView 和偏好分别保存在 `~/.conflua/webview/` 和 `~/.conflua/preferences.json`。

默认跟随系统语言；右上角齿轮菜单可手动切换「跟随系统 / 简体中文 / English」。

## CLI 与 MCP

默认地址为 `http://127.0.0.1:9081`。使用包内 `conflua.exe --help` 验证 CLI，`conflua.exe mcp` 是 stdio MCP 入口。可把包目录加入 `PATH`，或在 MCP 配置中把 `command` 设为 `conflua.exe` 的绝对路径，参数为 `["mcp"]`。改端口后同步设置 `CONFLUA_URL`。

## 关闭窗口

关闭需确认。确认后，应用向本次运行发送过管理端消息的聊天室当前 Agent 发布离线通知；不等待 Agent 回复。只要取消关闭，应用会继续运行。
