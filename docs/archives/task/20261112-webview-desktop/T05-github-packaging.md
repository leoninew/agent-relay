# Task / 子任务 T05：GitHub Actions 桌面打包 YAML
最后修改时间: 2026-11-12 14:12:23

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[浏览器与 WebView 双模式](../../intent/20261112-webview-desktop.md)。
- 权威总计划：[Plan](../../plan/20261112-webview-desktop.md)，方案修订 2，任务 T05。
- 依赖、分配和审查均以总计划为准，方案状态不表示实现完成。

## Handoff basis / 交接依据

- 当前分配 `WEBVIEW-T05-20261112-01`，当前架构师会话执行；用户消息 `room-94f73433cde7-msg-0119` 已授权五项 Implementation，T04 已接受。远端 workflow dispatch/run 不在本轮授权内。
- 协议入口：SpecFlow skill 与协作契约，位置及仲裁会话见总计划。
- 工作区：`D:\SourceCodes\mywork\agent-relay`；派发时固定实际构建入口与产物版本。
- 可写记录：本文“接收与进展”“交付与审查”；回报总计划仲裁会话。

## Goal and acceptance / 目标与验收

交付 `.github/workflows/build-desktop.yml`，对应 A07、A08。

- 支持 `workflow_dispatch` 和 `v*` 版本 tag push，使用 Windows x64 runner 构建。
- 调用项目 Makefile 入口，生成可下载的完整桌面 ZIP artifact。
- YAML、工具链和构建/压缩入口静态检查有记录；不添加集成测试，实际制品及 Actions 后续执行，未执行不标成运行通过。

## Inputs and eligibility / 输入与可开始条件

按总计划 T05 行核对已接受的 `make binary`、目录清单和包命名。T04 修订 2 取消 smoke 脚本，T05 使用其最终代码与正式构建入口；远端 workflow 不在本轮执行。

## Scope and files / 范围与文件

- 新 `.github/workflows/build-desktop.yml`。
- README 的 GitHub 手动打包、tag 触发和 artifact 下载说明。
- 正式 ZIP 压缩/版本检查脚本与 Makefile 入口；已协调 T04 的共享 Makefile，不增加 smoke 脚本。

## Technical decisions / 局部技术设计

- Windows 原生构建，与本机包保持相同 OS/CPU；checkout 触发 ref，版本 tag 检查其与项目版本的对应关系。
- 根据 `.python-version`、`.node-version` 与 `web/package.json` 准备 Python、uv、Node 和 Corepack/pnpm。
- 显式准备 GNU Make；通过 Git Bash 执行既有 Makefile，满足 Windows `cygpath` 和路径分隔符要求。
- 使用 Makefile 的依赖、检查、测试与 `make binary` 入口准备桌面环境；PyInstaller 参数只在本地构建入口维护。
- workflow 执行现有单元/静态检查及 `make binary`，在同一步骤完成目录构建与 ZIP 压缩，不附加 console/MCP/GUI 集成测试。
- 将整个目录压成 `agent-relay-<version>-windows-x64.zip`，上传 Actions artifact；上传缺失文件时报错，不能只上传 GUI EXE。
- 当前交付为构建与可下载 artifact。使用普通只读仓库访问即可，不增加 Release 发布链或独立 wheel 发布任务。

## Implementation outline / 实施安排

1. 编写触发、Windows 工具准备和 checkout/version 约定。
2. 接入项目单元/静态检查、正式构建、完整目录压缩与 artifact 上传。
3. 检查 YAML 与 actionlint，记录本地可验证项；在后续授权范围内运行 Actions 并核对下载包。

## Checks and delivery / 检查与交付

- YAML 解析及可用的 actionlint；核对 trigger、runner、工作目录、Makefile 入口、资源路径和 artifact 命名。
- 交付 workflow 文件、使用说明、检查输出和代码/前置版本。
- 远端执行后记录 run URL、触发 ref/版本、artifact 名称和下载验证结果；未执行注明原因。

## Risks / 风险

Windows hosted runner 的 GNU Make、Corepack 和 GUI 交互能力不同于开发机；工具准备及实际窗口验证需分别给出证据，静态 YAML 通过不等同于制品可运行。

## Reception and progress / 接收与进展

2026-11-12 13:37:33 接收 `WEBVIEW-T05-20261112-01`，执行者当前架构师会话 (`member-d8bc7b2eec9a`)，方案修订 1。已核对五项 Implementation 授权、T04 的实际包和完整 smoke 通过；HEAD `0e12906754eb84e9dd0a3c09fd1d9849081fd4ea` 加 T01–T04 当前工作区为输入。协调 Makefile 增加 archive 入口；只做本地 YAML/actionlint、版本与完整 ZIP 检查，不执行远端。

## Delivery and review / 交付与审查

2026-11-12 13:43:01，当前架构师会话交付 `WEBVIEW-T05-20261112-01`，方案修订 2。基线 `0e12906` 加 T01–T04 最终工作区，交付为当前未提交 diff。

- 新增 `.github/workflows/build-desktop.yml`，支持 workflow_dispatch / v*，Windows x64 使用版本文件、uv、Corepack 和 GNU Make，复用 `make deps/check/test/binary`，只上传完整 ZIP artifact。
- 新增正式 `scripts/binary.py`：读取项目版本、拒绝不匹配 tag、核对必需目录文件，压缩完整 AgentRelay 目录并输出 GitHub artifact 路径。它承担实际制品打包，不是验证探针。
- actionlint 1.7.7 通过；版本读取为 0.1.0；完整 Python 单元 259 项与 mypy 通过，Ruff 全库通过。前端代码没有改动，既有 156 项单元与类型/格式检查仍有效。
- 按用户消息 0123 不增加集成测试或 smoke 开关；实际最终构建、ZIP 及远端 Actions 留待用户后续执行，不报告其运行通过。主会话依据最终代码和静态检查接受实现。

2026-11-12 14:10:55，按用户消息 0127 统一 binary 命名：脚本为 `scripts/binary.py`，`make binary` 依次同步依赖、构建前端、构建双 EXE 目录并压缩 ZIP；workflow 合并构建与压缩步骤，上传读取 `steps.binary.outputs`。沿用当前分配和业务方案，不新增测试或执行真实制品构建。

本次定向检查通过：脚本 Ruff lint/format、mypy、`--check-version` 输出 0.1.0、actionlint 1.7.7、`make -n binary` 的四步顺序、旧命名无残留及 `git diff --check`。
