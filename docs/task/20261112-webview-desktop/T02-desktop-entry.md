# Task / 子任务 T02：桌面窗口与后台入口
最后修改时间: 2026-11-12 14:00:31

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[浏览器与 WebView 双模式](../../intent/20261112-webview-desktop.md)。
- 权威总计划：[Plan](../../plan/20261112-webview-desktop.md)，方案修订 2，任务 T02。
- 依赖、分配和审查均以总计划为准，方案状态不表示实现完成。

## Handoff basis / 交接依据

- 当前分配：`WEBVIEW-T02-20261112-01`，执行者为当前架构师会话 (`member-d8bc7b2eec9a`)；当前方案修订 2，沿用有效分配。
- 实施授权：用户消息 `room-94f73433cde7-msg-0119` 授权五项任务开始 Implementation；本 task 限于源码桌面入口、启动/关闭适配、必要依赖和开发检查。
- 协议入口：SpecFlow skill 与协作契约，位置及仲裁会话见总计划。
- 工作区：`D:\SourceCodes\mywork\agent-relay`；派发时登记实际基线与已接受输入版本。
- 可写记录：本文“接收与进展”“交付与审查”；回报总计划仲裁会话。

## Goal and acceptance / 目标与验收

交付可运行的源码桌面入口，对应 A01、A04、A08。

- 在主线程运行 WebView，后台启动既有 FastAPI，打开同源 `/static/`。
- 浏览器开发继续可用，非桌面入口无需加载 GUI。
- 窗口关闭提供确认与可接入通知流程的协调点；重开保留本地偏好。

## Inputs and eligibility / 输入与可开始条件

已核对总计划授权、当前分配和直接前置 T01 的接受记录。消费其 app 配置、资源/用户路径契约；可访问版本为当前共享工作区。

## Scope and files / 范围与文件

- 新 `src/agent_relay/desktop.py`、`bootstrap/desktop.py`。
- `bootstrap/http.py` 必要装配、Makefile 的 `desktop` 目标，以及桌面 extra 的最小依赖声明与锁文件。
- 桌面启动/关闭适配单元测试及启动说明；与后续任务串行修改共享文件。

## Technical decisions / 局部技术设计

- 复用 `build_app(settings=..., static_directory=...)`，将 PyWebView 保留在启动外层。
- 固定 loopback 9080；预绑定失败时反馈端口占用。API 启动失败向入口报告并关闭已创建资源。
- 复用现有 Windows SelectorEventLoop 和 FastAPI lifespan；记录启动失败日志位置。
- WebView2、`private_mode=False`、`~/.agent-relay/webview/`；前端仍通过原 HTTP/WebSocket 使用业务能力。
- 关闭时确认，取消保持运行；为确认后的通知回调保留清晰接入点，后续任务接线。不启动额外 Vite 管理流程。

## Implementation outline / 实施安排

1. 新增薄入口和桌面装配，接入 app 配置与本地 API。
2. 打开构建页面，设置浏览器配置与窗口参数，接入关闭确认。
3. 完善启动失败及正常收尾，验证独立 server/CLI 导入边界。

## Checks and delivery / 检查与交付

- 使用 fake/mock 检查 API 就绪、失败清理、确认取消和正常关闭；运行相关类型、lint/format 检查。
- 记录源码窗口、页面路由、复制和 WebSocket smoke；真实 GUI 检查若未获运行授权则注明未执行。
- 交付桌面启动命令、关闭通知接入点、可访问版本及检查结果。

## Risks / 风险

GUI 要求主线程，后台线程错误需要传回入口；无控制台构建的失败反馈由此入口承担。关闭流程仍需下游通知接线完成后才能整体验收。

## Reception and progress / 接收与进展

| 时间 | 记录 |
| --- | --- |
| 2026-11-12 12:56:20 | 接收 `WEBVIEW-T02-20261112-01`，方案修订 1。执行者：当前架构师会话 (`member-d8bc7b2eec9a`)。授权依据：用户消息 `room-94f73433cde7-msg-0119`。基线 HEAD `0e12906754eb84e9dd0a3c09fd1d9849081fd4ea`，含已接受的 T01 当前工作区交付；依赖版本与审查结果见总计划 T01 行和 T01 Delivery。范围限 T02；不触发远端工作流或真实 Codex 会话。 |

## Delivery and review / 交付与审查

- 交付：2026-11-12 13:08，`WEBVIEW-T02-20261112-01`，当前共享工作区；基线 HEAD `0e12906754eb84e9dd0a3c09fd1d9849081fd4ea`，消费已接受 T01。
- 变更：新增薄入口 `agent_relay.desktop` 和 `bootstrap.desktop`；桌面 extra 固定 PyWebView 6.2.1，Makefile `desktop` 先构建前端再以 app 模式启动；app 静态资源默认目录指向 `web/dist`。桌面 API 预绑定 loopback socket 后在后台 SelectorEventLoop 线程运行 Uvicorn，等待 lifespan ready；启动失败清理 listener/数据库，窗口关闭后请求正常停止。GUI 导入延迟到启动；WebView2 偏好存储在用户根，关闭事件具备确认取消及一次性确认回调。
- 验收与检查：合计 24 项 T01/T02 定向测试通过，覆盖真实本地 Uvicorn 服务/停止、端口冲突、应用构建失败释放端口、WebView 取消/确认/一次性回调和非桌面导入隔离。PyWebView 6.2.1 本机 API 签名确认支持 `private_mode` 与 `storage_path`。相关 3 文件 mypy、Ruff check、Ruff format --check、`git diff --check` 通过；`uv lock` 与 `uv sync --locked --extra desktop` 成功。
- 未运行：未启动真实桌面窗口，避免弹出/接管用户 GUI；源码页面交互留待整体 Verification。
- 主会话审查：实际 diff、生命周期与前置路径契约通过，交付接受；放行 T03。

修订 2 更新（2026-11-12 13:43:01）：按用户消息 0123，socket/Uvicorn/thread/WebView 均以替身检查，不启动真实 HTTP 服务；覆盖绑定先于 app 装配、端口失败、构建失败释放、确认取消和重复回调，显式断言 WebView2 与持久 profile 参数。最终单元/静态检查通过，主会话接受当前代码；前述真实 HTTP 检查仅为中间版本历史。

主任务继续核对（2026-11-12 14:00:31）：当前有效分配不变。补充通知异常时仍确认退出、重复回调不再次执行的纯替身单元；与 T03 定向合计 13 项通过，全量 Python 264 项和前端 156 项通过。mypy、Ruff、格式检查通过；产品装配行为未改变，实际 GUI 保持后续验证。
