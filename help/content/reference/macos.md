# macOS 桌面使用指南

## 下载与启动

从 [GitHub Releases](https://github.com/leoninew/conflua/releases/latest) 的 Assets 下载匹配的 ZIP：

| 制品后缀 | 目标机器 |
| --- | --- |
| `macos-amd64` | Intel Mac |
| `macos-arm64` | Apple Silicon Mac |

解压后双击完整的 `Conflua.app`，也可以先将它拖入「应用程序」。不要只复制 `Contents/MacOS` 下的可执行文件。Conflua 使用系统 WKWebView，无需另装 Python、Node.js 或 WebView2；Codex 自身的依赖、认证与 daemon 另行准备，见[运行与排障](./troubleshooting.md)。发布构建运行在 macOS 15，较早系统未验证。

## 配置与数据

桌面固定使用 `app` profile，配置优先级从低到高为内置 `config/conflua.yaml`、`~/.conflua/.env`、进程环境变量。数据库、日志、WebView 存储与偏好分别在 `~/.conflua/data/`、`~/.conflua/logs/`、`~/.conflua/webview/` 与 `~/.conflua/preferences.json`，不写入 `.app`。默认地址为 `http://127.0.0.1:9081`；遇到端口冲突时，在 `~/.conflua/.env` 设置 `CONFLUA_SERVER__PORT` 为可用端口并重启。

终端能找到 `codex` 不代表从 Finder 启动的应用也能找到。必要时将下例替换成本机 Codex 原生可执行文件的实际绝对路径：

```dotenv
CONFLUA_CODEX__COMMAND='["/absolute/path/to/codex", "app-server", "proxy"]'
```

若使用 npm 的 JavaScript 入口，可在数组内依次填 Node 的绝对路径、`codex.js` 的绝对路径、`app-server`、`proxy`。Conflua 不安装 Codex，也不关闭用户的共享 daemon。

## CLI 与 MCP

若应用已放在「应用程序」：

```sh
/Applications/Conflua.app/Contents/MacOS/conflua --help
```

MCP 的 `command` 可设为 `/Applications/Conflua.app/Contents/MacOS/conflua`，参数为 `["mcp"]`。CLI/MCP 连接已启动的桌面服务；改端口后同步设置 `CONFLUA_URL`。

## 签名与 Gatekeeper

制品使用 ad-hoc 签名，没有 Developer ID 签名和 Apple 公证，从网络下载后可能遇到 Gatekeeper 提示。仅对可信来源按 macOS 的安全提示操作，不全局关闭系统安全检查。
