# Intent / 意图：浏览器与 WebView 桌面双模式
最后修改时间: 2026-11-12 13:55:35

## Review status / 审查状态

Accepted

用户已接受主体评估和五项方案；消息 `room-94f73433cde7-msg-0119` 授权五项 Implementation，后续“继续推进主任务”后进行整体代码审查。按用户约束不新增集成测试，真实制品构建与运行检查后续执行。

## Background / 背景

Agent Relay 目前通过 `make webapi`、`make web` 开发，CLI/MCP 连接固定 HTTP 服务。用户希望保留浏览器开发，同时交付可运行的 WebView 桌面应用。现有分层与业务流程可复用，参考仓库内相邻的 FastAPI + PyWebView 模板。

依据：[接入评估](../design/20261112-webview-integration-assessment.md)，代码基线 `0e12906`。

## Goals / 目标

- 保留浏览器开发，新增使用同一前端、API 和 WebSocket 的 Windows 桌面入口。
- 桌面固定 `app` profile，默认配置随包，用户覆盖固定为 `~/.agent-relay/.env`；数据、日志、浏览器配置同属用户目录。
- 关闭窗口先确认，发送过管理端消息时向相关聊天室成员投递“管理端已离线。”后退出。
- 交付完整桌面目录包、可用的 CLI/MCP 控制台入口及 GitHub Actions 打包 YAML。

## Non-goals / 非目标

- 不添加集成测试；代码完成后由用户真实构建制品。保留 fake/mock 单元和静态检查，不执行 Git 提交、远端发布、GitHub Actions dispatch 或真实 Codex 投递。
- 首版聚焦 Windows；托盘常驻、自启动、自动更新和其他平台发行不属于本轮任务。
- 按用户要求保持直接的配置、确认和投递流程，不扩展安全专项或通用后台退出体系。

## Scenarios / 场景

- 开发者继续通过 `make webapi` 和 `make web` 在浏览器调试。
- 用户双击桌面程序，打开构建后的聊天室页面，CLI/MCP 使用同一 `127.0.0.1:9080` 服务。
- 用户在 `~/.agent-relay/.env` 修改覆盖值，重启应用生效；替换制品不改变用户数据库和偏好。
- 关闭窗口时取消，界面与后台继续运行；确认后按是否发送过消息决定是否发布离线通知，再关闭应用。
- GitHub 手动触发或推送版本 tag，通过 YAML 构建并下载包含 GUI、CLI 与运行资源的 Windows 压缩包。

## Acceptance criteria / 验收标准

- A01：`make webapi`、`make web`、现有 CLI/MCP 保持可用；非桌面入口不加载 GUI 依赖。
- A02：app 模式明确选择 `app` profile，配置优先级为内置默认 YAML → `~/.agent-relay/.env` → 系统环境变量；相对数据路径以用户目录为基准，不读取开发 `.env.dev`。
- A03：制品含前端、默认配置、日志配置及完整迁移资源；脱离仓库启动可初始化用户数据库，移动或升级制品保留原数据。
- A04：桌面与浏览器共用 API/WebSocket 和页面；桌面重新打开保留排序等本地偏好。
- A05：退出必须确认；取消不停止服务或发通知。确认后，本次运行成功发送过管理端消息的聊天室，各向其当前 Agent 成员定向发送一次“管理端已离线。”，无 Agent 则跳过；通知走既有投递、不等待模型回复，失败记录后退出。
- A06：完整目录包提供 GUI 与控制台入口，`agent-relay.exe --help` 可运行，stdio MCP 能初始化，现有插件可定位控制台程序。
- A07：交付 `.github/workflows/build-desktop.yml`，支持手动与版本 tag 触发，在 Windows runner 复用 Makefile 构建并上传完整 ZIP artifact；YAML 与制品入口检查有证据。
- A08：提供必要单元与静态检查，以及源码桌面、冻结包和工作流的实际验证记录；未执行的项目如实登记。

## Workload assessment / 工作量评估

工作量中等，复杂度集中在五个可分别 review 的交付：配置资源路径、桌面装配、退出通知、本地制品、GitHub 构建链。现有业务无需重写，需关注配置客户端变量误入服务校验、迁移依赖当前目录、无控制台程序的错误反馈，以及通知保存后未获得提交机会的问题。

实现检查覆盖 Python 配置/装配/投递的替身单元测试和现有前后端静态检查；真实 WebView、迁移与 CLI/MCP 留在用户构建制品后的验证，不添加集成测试脚本。review 结合 `bootstrap/http.py`、迁移加载、消息发布与投递、Makefile 和插件 `.mcp.json`。共享文件按依赖串行修改。

结论：建立五个 task；技术契约与实施状态由总计划集中管理。

## Candidate tasks and dependencies / 候选子任务与依赖

| 候选节点 | 主要交付 | 初始输入与依赖理由 | 验收归属 |
| --- | --- | --- | --- |
| T01 配置与资源路径 | app profile、用户 `.env`、资源与数据库定位 | 现有配置/迁移；提供桌面运行契约 | A02、A03、A08 |
| T02 桌面入口 | 可打开共用页面的窗口与后台装配 | 消费 T01 配置、路径；提供关闭确认接入点 | A01、A04、A08 |
| T03 退出离线通知 | 确认后的聊天室定向通知及退出 | 消费 T02 关闭接入点，复用发布与投递 | A05、A08 |
| T04 本地制品 | GUI/CLI 完整目录包与 `make binary` | 消费 T03 完整运行行为和前置资源 | A03、A06、A08 |
| T05 GitHub 打包 YAML | Windows 自动构建和 ZIP artifact | 消费 T04 构建入口与制品清单 | A07、A08 |

以上为拆分说明；可执行依赖只以[总计划](../plan/20261112-webview-desktop.md)为准。

## Open questions / 待定问题

暂无需要用户确认的未决事项。离线通知范围按本次 app 运行成功发送过管理端消息的聊天室执行；GitHub 交付是可下载的 Actions artifact。

## Decisions / 决策

- D01：用户目录为 `~/.agent-relay/`，覆盖文件 `.env`，替代早期 LocalAppData 建议。
- D02：桌面入口选择 `app` profile；开发入口维持现有 `dev`，桌面无须增加 `.env.app` 或 profile 子目录。
- D03：默认配置随包，用户只维护覆盖值；后台仍为固定端口、本地 HTTP 和现有投递。
- D04：退出以确认和必要离线通知为产品行为，复用既有资源关闭。
- D05：GitHub 打包 YAML 是明确任务交付，使用 Windows 原生 runner 和项目构建命令。
- D06：用户消息 `room-94f73433cde7-msg-0123` 明确不添加集成测试；代码实现完成后真实构建制品，取消自动 smoke/产品测试开关。
- D07：用户后续要求清理 scripts 中可由测试承担的验证入口；删除全部 8 个 probes，保留实际安装和正式制品压缩脚本，不新增集成测试。

## Risks / assumptions / 风险 / 假设

- T01 已修复 `AGENT_RELAY_URL`、`AGENT_RELAY_HTTP_TIMEOUT` 被误当作服务字段的问题，客户端变量边界由单元测试覆盖。
- 真实 WebView2、冻结资源和 GitHub runner 行为需实施后验证，当前静态评估不构成运行通过证据。
- 离线通知提供正常提交机会，不将其等同于模型已读或回复；退出失败路径保留现有投递结果语义。

## User review notes / 用户审查记录

- 2026-11-12：用户“大部分接受”，要求用户目录管理、内置默认配置与 `.env` 覆盖、直接的退出确认和离线通知。
- 2026-11-12：用户要求“完成后用 $specflow:specflow 记录任务，任务要包含 github 打包 yaml”。
- 2026-11-12：用户明确“要用用户目录 ~/.agent-relay/.env”，已同步所有当前方案。
