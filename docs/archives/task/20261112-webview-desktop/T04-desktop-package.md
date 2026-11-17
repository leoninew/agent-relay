# Task / 子任务 T04：桌面与控制台完整目录包
最后修改时间: 2026-11-12 14:25:53

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[浏览器与 WebView 双模式](../../intent/20261112-webview-desktop.md)。
- 权威总计划：[Plan](../../plan/20261112-webview-desktop.md)，方案修订 2，任务 T04。
- 依赖、分配和审查均以总计划为准，方案状态不表示实现完成。

## Handoff basis / 交接依据

- 当前分配 `WEBVIEW-T04-20261112-01`，执行者为当前架构师会话；用户消息 `room-94f73433cde7-msg-0119` 授权五项 Implementation，T03 已经总计划接受。
- 协议入口：SpecFlow skill 与协作契约，位置及仲裁会话见总计划。
- 工作区：`D:\SourceCodes\mywork\agent-relay`；派发时固定实际基线与完整桌面输入版本。
- 可写记录：本文“接收与进展”“交付与审查”；回报总计划仲裁会话。

## Goal and acceptance / 目标与验收

交付可由本地和 CI 共同调用的完整 Windows 目录包，对应 A03、A06、A08。

- `make binary` 从锁定环境构建前端和两个产品入口。
- `dist/AgentRelay/` 包含 GUI、console CLI/MCP、运行库及所有默认资源。
- 脱离仓库可运行，用户配置与数据仍在 `~/.agent-relay/`；实现完成后由用户真实构建并验证控制台、MCP 和 GUI，不增加集成测试。

## Inputs and eligibility / 输入与可开始条件

按总计划 T04 行核对已接受的完整桌面运行交付，取得实际默认资源路径、入口与退出通知版本。T03 交付接受并分配后实施；先核对本机 Windows 构建环境。

## Scope and files / 范围与文件

- Makefile、pyproject、uv.lock、受版本管理的 PyInstaller spec 与必要构建辅助脚本。
- 默认配置、前端构建输出和迁移资源的包含规则，必要的冻结路径适配。
- README 中构建、完整目录分发、控制台路径与运行前提说明。
- 构建目录为 `build/`、`dist/`；用户目录不是打包输入。

## Technical decisions / 局部技术设计

- 保持 Hatchling 和现有 CLI 安装方式；desktop extra 与开发构建工具分别声明并锁定。
- GUI `agent-relay-gui.exe` 为 windowed，`agent-relay.exe` 保留 console/stdio；使用 onedir 共享运行库，不以 GUI 程序接 stdio MCP。
- `make binary` 负责同步桌面构建依赖、前端构建与 PyInstaller；参数集中在 Makefile/spec，供 T05 直接调用。
- 明确包含默认配置、logging.yaml、前端、Alembic ini/env/revision/SQL 等实际资源；不依靠开发工作目录或源码树。
- 只分发整个目录；说明如何使插件当前的 `agent-relay mcp` 定位 console 入口。Codex 和 WebView2 依旧按现有运行前提准备。

## Implementation outline / 实施安排

1. 定义两个入口、资源清单、依赖与 PyInstaller spec，统一 Makefile 构建。
2. 检查完整输出目录与动态导入/资源包含规则，形成后续 YAML 的输出约定。
3. 单元/静态检查后交付实现；用户随后构建实际制品并验证默认配置、新库及 console/MCP。

## Checks and delivery / 检查与交付

- 记录锁文件校验、`make binary`、输出目录和资源清单。
- 不增加 smoke 脚本或产品内测试入口；最终版本的 console、MCP、GUI 和新库由用户真实构建后验证。
- 交付包结构、版本/平台命名约定、构建命令及可访问实现版本，供 CI 消费。

## Risks / 风险

Python/.NET 的动态导入及包资源可能只在冻结后暴露缺失，应以实际产物定位问题。GUI 的交互验收与无界面 runner 上的 console 检查分别记录。

## Reception and progress / 接收与进展

2026-11-12 13:23:36 接收 `WEBVIEW-T04-20261112-01`，执行者当前架构师会话 (`member-d8bc7b2eec9a`)，方案修订 1。已核对用户授权和 T03 接受记录；基线 HEAD `0e12906754eb84e9dd0a3c09fd1d9849081fd4ea` 加 T01–T03 当前未提交工作区。仅构建和隔离 smoke，不触达用户数据库、真实 Codex 会话或远端发布。

## Delivery and review / 交付与审查

2026-11-12 13:37:33，当前架构师会话交付 `WEBVIEW-T04-20261112-01`。基线 `0e12906`，前置 T01–T03 已接受工作区，交付为当前未提交 diff 和 `dist/AgentRelay/`。

- 新增受控 spec、console 构建入口、`make binary`、`make smoke-binary` 和独立 smoke 脚本；PyInstaller 6.22.3 为锁定 dev 依赖，PyWebView 6.2.1 为 desktop extra。
- `make binary` 成功：GUI/console 共享 `_internal/`，包含默认配置、日志、前端、完整 Alembic/SQL 资源与 WebView2 DLL。实际打包检查修复了 console UTF-8 和迁移脚本动态导入遗漏。
- `make smoke-binary` 通过：从临时复制目录及无关 cwd 运行两个 EXE 的 PE/x64/子系统检查、console --help、MCP initialize/tools list；隔离用户 `.env` 的端口覆盖生效，新库迁移和 `/static/` HTTP 成功；再从原目录使用同一临时数据库保留原房间。用户目录和真实 Codex 会话未触达。
- 完整前后端 `make check test` 通过：Python 262 项、前端 156 项测试；mypy、Ruff、Prettier、vue-tsc 均通过。既有 `MessageTimeline.vue` 的 vue/no-v-html warning 仍存在，无新增 lint error。此机 Cygwin make 直接执行 `.cmd` 受限，检查时通过 `PNPM=node <本机 Corepack JS 路径> pnpm` 覆盖，原 `make binary`/`make smoke-binary` 无须覆盖即可运行；CI 使用原生 GNU Make。
- `uv lock --check`、Ruff 全库检查通过；构建仅有未使用的可选后端 hook warning。未执行真实 GUI 交互；这是后续整体 Verification 项目。
- 主会话依据实际包和 smoke 接受 T04，放行 T05。T05 只扩展压缩/版本输出的 Makefile 辅助入口，保持本 spec 和构建入口。

修订 2 更新（2026-11-12 13:43:01）：用户消息 0123 后，已删除 `scripts/desktop_console.py`、`scripts/smoke_desktop.py` 和 `make smoke-binary`，spec console 入口直接指向公开 `agent_relay/cli.py`，仅保留 UTF-8 初始化。`make binary` 和双入口/资源规则保留。最终代码通过单元和静态检查；旧中间制品不作为最终交付，停止重复构建，最终制品由用户后续执行。当前分配继续有效，主会话复核接受修订后实现。

2026-11-12 14:25:53，按用户本轮要求将 GUI 可执行文件名明确为 `agent-relay-gui.exe`，与控制台入口 `agent-relay.exe` 成对易辨；PyInstaller spec 与 `scripts/binary.py` 完整性清单、README、评估、总计划和本 task 已同步。目录仍为 `dist/AgentRelay/`，共享 `_internal/` 和 CLI/MCP 行为不变；不重建最终制品，留待用户按安排真实构建。脚本 Ruff lint/format、mypy、spec/完整性清单定向核对、旧名全仓搜索及 `git diff --check` 通过。
