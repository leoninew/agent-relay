# Verification / 验证：浏览器与 WebView 桌面双模式
最后修改时间: 2026-11-12 15:19:12

## Review status / 审查状态

Draft

用户在五项代码交付与脚本清理后要求“继续推进主任务”。本次继续整体代码审查及必要单元/静态检查，保留用户“不添加集成测试，代码完成后真实构建制品”的安排；最终制品、真实 Codex 投递和远端 Actions 尚未运行，因此不将整体验收记为通过。

## Intent alignment / 意图对齐

依据[Intent](../intent/20261112-webview-desktop.md)核对浏览器开发兼容、固定 app profile、用户 `.env`、资源/数据根、退出确认/通知、双 EXE 和 Windows artifact。

- 桌面通过既有 `build_app`、HTTP 静态页面和 WebSocket 复用前后端；未加入原生业务桥接或 GUI 依赖到 CLI/HTTP 启动路径。
- application 负责通知发布，bootstrap 装配生命周期，persistence 只读筛选当前运行用户消息对应的有效 Agent；资源解析是中立模块，没有持久化层反向导入 bootstrap。
- 删除全部 8 个 probe，只保留实际安装和压缩入口；没有产品测试开关、集成测试脚本或对现有用户数据库/会话的操作。

## Plan alignment / 计划对齐

以[Plan 修订 2](../plan/20261112-webview-desktop.md)为依据。沿用 T01 → T02 → T03 → T04 → T05 的有效交付；用户约束未改变业务或包结构。真实构建与运行检查留待后续，不以旧中间版本替代最终制品。

## Task deliveries and integration / 子任务交付与集成

当前基线 HEAD `0e12906754eb84e9dd0a3c09fd1d9849081fd4ea`，交付为同一工作区未提交 diff；无分支/提交操作。

| ID | 当前有效交付版本 / 位置 | 必要检查与审查证据 | 集成与基线核对 | 验收归属与结果 |
| --- | --- | --- | --- | --- |
| T01 | config、paths、resources、migrations 当前工作区 | profile/环境变量/绝对路径与 mock Alembic 单元 | T02/T04 均使用该资源和用户根 | A02 源码通过；A03 真实迁移后置 |
| T02 | bootstrap/desktop.py、公开 desktop 入口 | socket/服务/WebView 替身，确认取消及失败后退出 | 复用既有 HTTP lifespan，显式 WebView2 | A01 源码通过；A04 实际窗口后置 |
| T03 | desktop application、查询、关闭接线 | 发布目标/幂等标识/逐房间失败，通知等待边界单元 | 复用原 runner 和单库锁，退出等待活动提交完成 | A05 单元/源码通过；真实提交后置 |
| T04 | spec、make binary、desktop extra/dev lock | 双入口、资源与动态导入静态核对 | console 直接使用公开 CLI，无 smoke 开关 | A03/A06 最终制品待构建 |
| T05 | workflow、archive 脚本、README | actionlint、YAML/版本/脚本语法检查 | 复用 Makefile，不复制 PyInstaller 参数 | A07 静态通过；实际 artifact 后置 |

## Corrections and scope / 修复与范围

| 对齐依据 | 发现的偏差 | 实际修复 | 复验结果与证据 |
| --- | --- | --- | --- |
| A05 失败后退出、不等待模型回复 | 删除集成检查后，纯单元未直接覆盖通知等待状态边界 | 补充 Mock 用例：pending 到 submitting 即停止等待、领取超时、无消息、查询失败；关闭通知抛错仍确认退出 | 13 项定向单元及后端全量 264 项通过 |
| Plan 协调表、Intent 风险记录 | 分配历史表被空行拆断；已修复的客户端环境变量仍列作当前错误 | 合并 Markdown 表并更新事实 | 文档复核，未改变产品契约 |

此次继续未修改产品行为；单元使用 fake/mock，不创建 SQLite、不启动 HTTP/GUI/协议子进程，不新增独立验证脚本。

## Acceptance results / 验收结果

| 验收 ID | 结果 | 证据或未满足原因 |
| --- | --- | --- |
| A01 | 源码/单元通过；真实浏览器联调未验证 | 开发入口保留，非桌面路径不导入 webview |
| A02 | 单元与源码通过 | app profile、内置默认 → 用户 .env → 系统环境；数据/资源分根 |
| A03 | 源码通过；最终制品未验证 | spec 资源和绝对迁移定位齐全；真实新库、升级/移动需最终制品 |
| A04 | 源码通过；实际交互未验证 | 共用页面/API/WebSocket、持久 profile 参数已核对；路由/复制/排序重开待实测 |
| A05 | 单元与源码核对；真实投递未验证 | 固定用户、当前运行房间、有效 Agent、单次确认、正常提交机会及失败日志 |
| A06 | spec/入口核对通过；最终 EXE/MCP 未验证 | GUI/windowed 与 console 两入口；最终制品按用户安排后续构建 |
| A07 | 静态核对通过；远端运行未验证 | workflow 触发/工具链/Makefile/完整 ZIP/artifact；不触发远端 |
| A08 | 单元/静态检查通过；运行部分未验证 | 后端 264、前端 156 项通过；本文明确登记未执行的真实制品与远端检查 |

## Check results / 检查结果

| 命令 / 检查 | 实际结果 | 未运行原因 |
| --- | --- | --- |
| pytest test_desktop.py + test_desktop_exit.py | 13 项通过 | 无 |
| make check test | 后端 264、前端 156 项通过；mypy 156 文件、Ruff、vue-tsc、Prettier 通过 | 本机 Cygwin make 使用 `PNPM=node <Corepack JS 路径> pnpm` 覆盖，避免直接执行 .cmd 的环境限制；日志为 `check-webview-review.log` |
| actionlint 1.7.7 | 通过 | 无 |
| spec / archive AST、YAML BaseLoader 结构检查 | 通过，触发方式及 Makefile 五个入口齐全 | 没有运行 app 或打包脚本 |
| uv lock --check、git diff --check | 通过 | 无 |
| binary 命名统一后的定向检查 | 脚本 Ruff lint/format、mypy、版本读取 0.1.0、actionlint 1.7.7、make -n binary、旧名检索及 diff 空白检查通过 | 仅展开构建命令，未执行构建或压缩 |
| Windows Actions formatter 行尾修正 | Ruff 报 `156 files would be reformatted`，Prettier 报 84 个文件且集中在 JSON/TS；新增 `.gitattributes` 的 `* text=auto eol=lf`，使所有文本文件在 Windows checkout 保持 LF，不改 formatter 规则 | 本机 `ruff format --check .` 显示 250 files already formatted；本地 Prettier CLI 对 web 全部文件检查通过；`git check-attr` 确认 JSON/TS `eol=lf`；actionlint 与 diff 空白检查通过。GitHub hosted runner 尚待重跑 |
| make binary、GUI、MCP、真实 Codex | 未运行 | 按用户约束留待代码完成后的真实制品阶段 |
| 远端 GitHub Actions | 未运行 | 本次没有远端执行授权 |

## Risks and incomplete items / 风险与未完成项

- 最终冻结制品尚未构建，A03/A04/A06 的实际运行证据待补齐；旧 dist 是中间版本。
- 退出通知最多等待 5 秒获得原 runner 的领取机会；已有长 RPC/积压或外部提交器持锁时可能超时，记录后退出，未声称模型已读。实际负载下的通知行为须在真实制品阶段核对。
- 本次不增加自动集成测试或 smoke 入口，也不触碰用户现有数据库、会话或开发服务。
- 前端仍有既有 `MessageTimeline.vue` 的 vue/no-v-html warning，无新增 lint error。

## Conclusion / 结论

本次继续完成了五项交付的代码核对和单元/静态复验，未发现需要改变既定产品方案的偏差。补充 5 个纯单元场景后，全量检查通过，当前代码可进入用户安排的真实制品构建。真实 GUI、冻结目录、迁移/CLI/MCP 和远端运行证据未齐，整体验收保持 Draft，不标记为全量运行通过。

2026-11-12 14:25:53：按用户本轮要求将 GUI EXE 命名改为 `agent-relay-gui.exe`；spec 和 ZIP 内容完整性清单已一致，旧 GUI EXE 名称检索无残留。脚本 Ruff lint/format、mypy、定向名称检查及 `git diff --check` 通过。未运行 PyInstaller/ZIP 构建，最终制品检查仍待用户真实构建。
