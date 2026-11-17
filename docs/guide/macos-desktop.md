# macOS 桌面使用指南

## 架构与构建

macOS 制品按 CPU 架构分别交付，使用系统 Cocoa/WKWebView，无需 WebView2。Conflua 自带 Python 运行时与前端资源；目标机器无需为 Conflua 安装 Python 或 Node.js。Codex CLI、其自身运行依赖、认证及共享 daemon 仍需单独准备。

| 制品后缀 | 目标机器 | 构建 Python 架构 |
| --- | --- | --- |
| `macos-amd64` | Intel Mac | `x86_64` |
| `macos-arm64` | Apple Silicon Mac | `arm64` |

在对应架构的 Mac 上准备 Python 3.12、uv、Node.js、Corepack 和 GNU Make，执行：

```bash
make deps
uv run --locked --no-sync python -c 'import platform; print(platform.machine())'
make binary
```

产物为：

- `dist/Conflua.app`：包含 GUI、CLI 和运行资源的完整应用。
- `dist/conflua-<version>-macos-amd64.zip` 或 `dist/conflua-<version>-macos-arm64.zip`。

架构取自构建用 Python 进程，不是文件名参数；PyInstaller 按该架构收集原生依赖，打包脚本再用 `lipo` 核对两个入口。不能在 arm64 环境直接改名得到 amd64 制品，也不从 Windows/Linux 交叉编译 macOS。GitHub Actions 分别使用 Intel 和 Apple Silicon runner 生产两套 ZIP；当前 CI 基线为 macOS 15，较早系统尚未验证。

ZIP 使用 macOS `ditto` 创建，保留 `.app` 中的符号链接与执行权限。不要只复制 `Contents/MacOS` 下的可执行文件，也不要用不保留符号链接的方式重新压缩应用。

## 启动与配置

解压后可将整个 `Conflua.app` 拖入“应用程序”，再双击启动。源码启动使用 `make desktop`。

桌面固定使用 `app` profile，配置优先级为内置 `config/conflua.yaml` → `~/.conflua/.env` → 进程环境变量。用户数据库、日志、WebView 存储及偏好分别放在 `~/.conflua/data/`、`logs/`、`webview/` 和 `preferences.json`，不写入 `.app`。更换制品不会删除这些数据。

默认 API 地址为 `http://127.0.0.1:9081`。开发服务与桌面不能同时占用该端口；可在 `~/.conflua/.env` 中覆盖：

```dotenv
CONFLUA_SERVER__PORT=9081
CONFLUA_DATABASE__PATH=./data/conflua.db
```

Finder 不读取交互式 shell 的启动配置，因此终端能找到 `codex` 不代表 Finder 启动的应用也能找到。必要时在 `~/.conflua/.env` 指定实际的 Codex 原生可执行文件：

```dotenv
CONFLUA_CODEX__COMMAND='["/absolute/path/to/codex", "app-server", "proxy"]'
```

该路径必须替换为本机真实路径。如果使用 npm 的 JavaScript 入口，可以将命令配置为绝对路径的 Node 和 `codex.js`，再接 `app-server`、`proxy`，避免依赖 Finder 的 `PATH`。应用不会安装 Codex，也不会关闭用户共享 daemon。

启动失败时查看 `~/.conflua/logs/conflua.log`；无控制台时会尝试显示原生错误对话框。界面语言也可在应用设置中手动选择。

## CLI 与 MCP

CLI 随 `.app` 一起交付：

```bash
/Applications/Conflua.app/Contents/MacOS/conflua --help
/Applications/Conflua.app/Contents/MacOS/conflua mcp
```

MCP 的 `command` 可设为 `/Applications/Conflua.app/Contents/MacOS/conflua`，参数为 `["mcp"]`。CLI/MCP 连接已经启动的桌面 HTTP 服务，不另起后台。更改桌面端口后，需要同步设置客户端 `CONFLUA_URL`。

## 签名与验证边界

当前使用 PyInstaller 默认的 ad-hoc 签名，未配置 Developer ID 签名或 Apple 公证。从网络下载的应用可能被 Gatekeeper 拦截；这不等同于已签名、公证的公开分发包。仅对可信来源按 macOS 的安全提示处理，不要全局关闭系统安全检查。

`make binary` 校验资源、版本、入口架构和 bundle 元数据，并执行冻结 CLI 的 `--help`。GUI、Finder 下的 Codex 连接、首次数据库迁移及退出行为仍需在目标系统验收，CLI 检查不能替代桌面验证。
