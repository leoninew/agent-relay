# WebView 双模式接入评估
最后修改时间: 2026-11-12 14:25:53

评估日期：2026-11-12。项目基线：`0e12906`。本文为已接受方案，用户随后授权五项 Implementation；实际实施与开发检查见 [SpecFlow 总计划](../plan/20261112-webview-desktop.md)。本评估本身不表示桌面运行验证通过。

参考模板：`D:\SourceCodes\mywork\best-practices\templates\python-fastapi-webview`，其中锁定的 PyWebView 版本为 6.2.1。

## 结论与范围

适合接入 PyWebView。浏览器和桌面窗口可以共用现有 Vue 页面、FastAPI API、WebSocket 事件流和应用用例，工作主要集中在启动装配、服务生命周期、资源路径与制品交付。无需调整刚完成的领域模型和应用 DTO 分层。

建议首版面向 Windows，使用 WebView2，采用模板的 GUI 主线程与 Uvicorn 后台线程结构。开发阶段继续使用 `make webapi` 和 `make web`；桌面制品使用 PyInstaller `onedir`、GUI 入口 `windowed`。分发完整目录，包含运行资源和 Python 运行时。

关闭桌面窗口时先确认；确认后，如本次运行在聊天室发送过管理端消息，向这些聊天室的成员投递“管理端已离线。”，随后退出由桌面启动的 Relay 服务。浏览器标签关闭不影响服务。退出流程复用现有发布、投递和资源关闭能力。

## 两种界面与共同后台

| 场景 | 启动方式 | 页面地址 | 服务归属 |
| --- | --- | --- | --- |
| 日常浏览器开发 | `make webapi` + `make web` | `http://localhost:9081` | 用户分别管理后端与 Vite |
| 桌面源码验收 | 建议新增 `make desktop`，先构建前端 | `http://127.0.0.1:9080/static/` | 桌面进程启动本地 API |
| 桌面制品 | `agent-relay-gui.exe` | 内嵌 WebView 打开同源 `/static/` | 桌面进程启动本地 API |
| 浏览器访问桌面服务 | 打开桌面服务的 `/static/` | `http://127.0.0.1:9080/static/` | 复用同一个 API 与数据库 |

日常开发不需要桌面启动器自动管理 Vite，也不需要复制模板的 `DevelopmentFrontend` 子进程管理。以后确有桌面热更新需求时，再增加明确的联调入口。

现有 `web/vite.config.ts` 构建基址为 `/static/`；路由使用 `import.meta.env.BASE_URL`；API 使用根路径 `/api`，事件 WebSocket 从当前页面地址构造。因此构建后的页面可以通过现有 `SpaStaticFiles` 提供，历史路由刷新也有回退能力。应让 WebView 打开 HTTP 页面，保持这些地址关系。

业务记录通过共同服务共享；普通浏览器与 WebView 的浏览器配置文件独立，排序等本地偏好不会自动互通。开发环境的 9081 与制品的 9080 也属于不同 origin。

## 分层与模块建议

| 位置 | 职责 |
| --- | --- |
| 新增 `src/agent_relay/desktop.py` | 薄启动入口，解析桌面参数并交给组合根 |
| 新增 `bootstrap/desktop.py` | 装配窗口、受控的 Uvicorn 后台线程、启动失败处理与停止流程 |
| `bootstrap/settings.py` | 新增真正需要的桌面配置，如标题、尺寸、调试开关 |
| `bootstrap` 中的路径解析模块 | 集中区分只读资源、用户配置和可写数据目录 |
| `bootstrap/http.py` | 继续作为 HTTP 组合根，桌面复用 `build_app(settings=..., static_directory=...)` |
| `infrastructure/persistence/` | 继续拥有迁移、数据库和存储适配，接收明确的资源与数据库路径 |
| `interfaces/http/` 与 `web/src/services/` | 继续承载全部现有业务协议 |

领域层与应用层不导入 `webview`、Uvicorn、冻结环境标记或窗口类型。首版没有业务必须使用原生桥接，模板的系统信息、执行 Shell、通知和 Greeting API 都不需要引入。未来出现文件选择等具体原生能力时，再设独立接口适配，并让浏览器模式保持可用。

PyWebView 放入 `desktop` optional extra；PyInstaller 放入开发依赖。独立 HTTP 和 CLI/MCP 入口不应导入桌面模块，使浏览器开发和 CLI 安装不必加载 GUI 依赖。保持当前 Hatchling 构建后端。

## 启动、端口与停止

建议的桌面启动顺序：

1. 解析并校验配置、资源路径和用户数据路径，初始化文件日志。
2. 检查前端入口及迁移资源，预绑定配置的 loopback 监听端口，再创建数据库和应用。
3. 必要时升级用户数据库，复用现有 `build_app`，在后台线程运行 Uvicorn。
4. 等待 API 完成启动；失败或超时应向入口传递原因并清理已创建的资源。
5. 在主线程创建窗口并执行 `webview.start()`，打开同源 `/static/`。
6. 关闭窗口时确认；取消则继续运行，确认则按下述规则发送离线通知，再请求 Uvicorn 正常停止，复用 FastAPI lifespan 收尾。

监听地址建议固定 `127.0.0.1:9080`。当前 CLI 默认地址和插件 MCP 使用同一端口；随机端口需要另建跨进程地址发现机制，并会改变前端本地存储的 origin。配置为其他端口时，要同步通过已有 `AGENT_RELAY_URL` 或 CLI 参数指定服务地址。

首版端口占用时提示“管理端已运行或端口被占用”，保持固定地址。桌面只管理自己启动的 API。

现有 `SubmitterLock` 继续按数据库路径保护投递者。按用户反馈，本轮采用现有能力和明确的退出确认，不扩展实例发现、服务身份校验或额外的安全机制。

### 退出确认与离线通知

1. 窗口关闭统一弹出确认，取消不发送通知、不停止后台。
2. “发送过消息”按本次 app 运行期间已成功提交的管理端用户消息判断，草稿或失败请求不计入。通知范围是这些消息所在的聊天室，各聊天室通知一次。
3. 确认后，用现有固定人类成员“你”发布“管理端已离线。”，目标为该聊天室当前的 Agent 成员，按成员直接定向，不受当前话题筛选限制；没有 Agent 的房间跳过。
4. 在服务仍运行时执行现有发布与投递流程，给离线通知一次正常提交机会，再停止服务。验收要检查实际提交步骤，不能仅在本地保存待办后立即停止投递器。
5. 不等待模型回复或收到后的回执；投递失败记录日志后继续退出。复用已有结果未知处理，不为离线通知增加盲目重发或长时间阻塞退出的流程。
6. 内部清理继续使用 `bootstrap/http.py` 的 runner、数据库关闭顺序，并保留 `server.py` 的 Windows SelectorEventLoop 配置。不将通用 RPC 取消协议或后台停止体系重构作为本次前置任务。

桌面退出仅清理本次启动的 Codex proxy 及连接，继续遵守 `ProxyRpc.close()` 的边界，保留用户共享 daemon 和已有 Codex 会话。

## app profile 与用户覆盖

桌面入口固定选择 `app` profile，源码桌面模式和冻结制品使用相同约定。`make desktop` 进入此模式；浏览器开发保留 `make webapi` 的 `dev` profile 和仓库 `.env.dev`。前端仍按现有生产构建生成资源，后端的 `app` profile 不要求增加 Vite 配置环境。

app 模式的用户根目录固定为 `Path.home() / ".agent-relay"`，覆盖文件就是 `~/.agent-relay/.env`。Windows 对应当前用户主目录下的 `.agent-relay`，不使用 LocalAppData，也不再增加 profile 子目录或 `.env.app` 文件。

```text
~/.agent-relay/
  .env
  data/agent-relay.sqlite3
  logs/
  webview/
```

配置优先级为：制品内置默认 YAML → 用户目录 `.env` → 系统环境变量。`.env` 可缺省，缺省时使用内置配置；用户只维护覆盖值，无需复制或管理一份 YAML。配置加载入口显式接收桌面 profile 和覆盖文件位置，桌面启动不受开发 shell 中 `AGENT_RELAY_PROFILE=dev` 的误导。

app 模式中配置的相对数据、日志路径均以 `~/.agent-relay/` 为基准，实际传给存储和日志模块时转成绝对路径；资源目录由包位置确定。重启、移动或替换制品继续使用同一用户目录。

## 资源、配置与数据

| 内容 | 当前情况 | 桌面建议 |
| --- | --- | --- |
| 默认配置 | 从当前目录的 `config/config.yaml` 加载，支持显式 fallback | 制品带默认配置，用户只用 `~/.agent-relay/.env` 覆盖 |
| 前端 | 构建到 `web/dist`，HTTP 默认静态目录为 `./static` | 随制品携带构建资源，启动时显式注入实际目录 |
| 日志配置 | 相对包内 `logging.yaml` 定位 | 显式打包，保持只读资源访问方式 |
| Alembic | `Path.cwd()/alembic.ini`，配置再引用根目录迁移树 | 显式资源根，包含 ini、env、revision 及对应 SQL；消除工作目录依赖 |
| SQLite、锁、日志 | 多处相对当前目录解析 | 使用稳定的用户可写目录和绝对路径 |
| WebView 浏览器配置 | 模板直接调用 `webview.start(debug=...)` | `private_mode=False`，设置稳定且可写的 `storage_path` |

用户根目录按上一节固定为 `~/.agent-relay/`。开发阶段继续使用仓库内数据路径；制品升级或移动安装目录不会创建新的用户数据库。

PyWebView 6.2.1 的 `private_mode` 默认为 `True`；当前页面通过 localStorage 保存排序，照搬模板会导致重启后偏好不持久。将其设为 `False` 并指定存储目录后，还要保持服务 origin 稳定。现有 sessionStorage 中的待确认发布记录仍遵守会话级语义，不因 WebView 接入改为持久草稿。

只读资源根可通过包资源或冻结资源目录解析，用户目录单独传递。制品携带默认资源；用户 `.env`、数据库和浏览器配置留在用户目录。通过明确路径装配，消除当前工作目录依赖。

当前生产默认配置 `migrate_on_startup=false`，新库直接打开会被数据库适配器拒绝。桌面默认应在提供服务前对明确的用户数据库执行受控升级，沿用现有迁移链；遇到不受支持的旧库应提示处理方式，不能重建覆盖。开发数据库不会自动复制到用户目录。

还存在一个会直接影响桌面启动的既有配置问题：`load_settings()` 将所有 `AGENT_RELAY_*` 变量作为服务配置字段，而 CLI/MCP 已使用同前缀的 `AGENT_RELAY_URL` 和 `AGENT_RELAY_HTTP_TIMEOUT`。在进程内临时设置两项变量、分别只调用配置加载，已确认它们触发 `url`、`http_timeout` 的 `extra_forbidden`。桌面进程可能继承这些合法的客户端变量，接入时应明确划分并排除已声明的客户端变量，保留对真正未知服务字段的严格校验。

## 制品与 CLI/MCP

建议桌面制品先采用 Windows 本机构建的 `onedir` 目录包；GUI 入口使用 `windowed`，无需为形式改成单文件。新增 `make binary` 统一执行锁定依赖安装、前端构建与 PyInstaller，保持现有浏览器开发命令。

GUI EXE 不能替代 stdio MCP：当前插件 `.mcp.json` 运行的是 `agent-relay mcp`，要求可用的标准输入输出。建议桌面分发目录提供两个入口：

- `agent-relay-gui.exe`：打开窗口并拥有本地后台服务。
- `agent-relay.exe`：控制台 CLI，继续提供现有命令和 `mcp`，连接同一个 HTTP 服务，不自行启动第二套后台。

二者可以使用 PyInstaller spec 共享目录依赖。安装说明通过 PATH 或明确的绝对路径配置控制台入口，让现有插件能够执行 `agent-relay mcp`。现有 Python CLI 安装途径继续有效。

当前 wheel 主要交付 CLI/MCP，包配置只显式列出 `src/agent_relay`，没有桌面默认配置、前端和根目录迁移树的完整资源契约。桌面包要独立验证资源清单；如果还要承诺 wheel 安装后可直接运行桌面或独立服务，应同步补全 wheel 的资源包含与安装后路径契约。

WebView2 Runtime 是 Windows 图形运行前提；Codex CLI、认证与共享 daemon 仍是投递能力的外部前提。Relay 制品只内置自身 Python 运行环境。需要验证从资源管理器双击时的 PATH 与 Codex 命令解析，不能只以开发终端运行成功作为验收。缺少 Codex 连接能力时应保留可诊断的离线状态。

无控制台入口的启动失败需要用户可见的错误及日志位置，不能仅输出 stderr。GUI 调试默认关闭，明确使用 WebView2，避免浏览器内核回退导致现有现代前端能力失效。

## 建议实施顺序与验收

第一批完成桌面运行基础：`app` profile、`~/.agent-relay/.env`、迁移资源定位、客户端与服务配置变量边界、桌面入口、稳定浏览器配置，以及退出确认和离线通知。先证明源码桌面模式可以打开构建页面；保留 `make webapi` 与 `make web` 的既有职责。

第二批完成制品交付：锁定桌面和打包依赖，增加 `make binary`、GUI/CLI 入口及资源清单，以及 `.github/workflows/build-desktop.yml`。GitHub Actions 在 Windows runner 调用相同 Makefile 入口，验证并上传完整目录压缩包作为可下载的 Actions artifact，再在脱离仓库目录的环境验收制品。具体任务、依赖和执行情况以 SpecFlow 总计划为准。

最小验收范围：

1. 浏览器开发命令、CLI 和 stdio MCP 继续可用；未安装桌面 extra 时可导入并运行非桌面入口。
2. 从非仓库工作目录和含空格的目录启动制品；默认配置、日志配置和迁移 SQL 均可定位，新用户数据库可以初始化；`app` profile 正确读取 `~/.agent-relay/.env`。
3. 浏览器与 WebView 连接同一服务，均能加载聊天室、收发消息、更新 WebSocket 事件；构建路由刷新、复制消息等现有交互正常。
4. 重启窗口后数据库和排序偏好保留；浏览器与 WebView 的本地偏好独立符合预期；替换制品目录不影响用户数据。
5. 端口冲突、迁移失败和 WebView 初始化失败都能反馈并回收已创建资源；启动失败后可以再次启动。
6. 关闭窗口先确认；取消继续运行。未发送消息时直接退出；已发送时向相关聊天室 Agent 投递离线通知，再按现有流程退出，记录通知提交结果而不等待模型回复。
7. 控制台入口执行 `--help`，stdio MCP 完成 initialize 和一个只读工具请求；GUI 构建不破坏控制台协议。
8. 无 Python、无 Node 开发工具的目标环境可以运行 GUI/CLI 制品；投递验证环境另具备已认证的 Codex 和所需运行依赖。
9. GitHub 打包 YAML 可以手动触发，并在版本 tag 上构建 Windows 包；使用 `make binary`，上传包含两个入口及全部资源的压缩制品。控制台实际运行在制品阶段验证。

单元验证重点是配置优先级、路径解析、窗口关闭取消/确认，以及离线通知触发条件，采用现有 fake/mock 约定。依据用户消息 `room-94f73433cde7-msg-0123` 不添加集成测试；真实迁移、WebSocket、WebView2 和 CLI/MCP 使用代码完成后真实构建的制品验证，不增加 smoke 脚本或产品内测试入口。

本轮进行了当前代码、模板及其本机 PyWebView 源码的静态检查，并运行了上述配置加载探针；未安装依赖、访问数据库、启动服务、弹出桌面窗口或构建制品。接入工作量判断为中等，主要工作是配置路径、桌面装配、离线通知与制品链路，后续按 SpecFlow 计划实施。
