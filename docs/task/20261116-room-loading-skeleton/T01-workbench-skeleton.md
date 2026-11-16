# Task / 子任务 T01：整体工作台骨架
最后修改时间: 2026-11-16 17:34:19

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[聊天室骨架屏与加载体验](../../intent/20261116-room-loading-skeleton.md)。
- 权威总计划：`D:/SourceCodes/mywork/conflua/docs/plan/20261116-room-loading-skeleton.md`；任务 ID：T01；方案修订：1。
- 依赖、分配及仲裁以总计划为准，本文记录局部设计和事实。

## Handoff basis / 交接依据

- 协议入口：总计划 Coordination 引用的 SpecFlow 子任务协作契约。
- 授权：用户“先实现 T01”；当前分配 `T01-e17cf59c-6bd3-4a27-b1a7-9adf25387d67`，由当前 Codex 主会话直接实施。
- 工作区：`D:/SourceCodes/mywork/conflua`；基线 `396f703fd4221fdb7d8b38201133ba429abbeb35`，已有本功能未提交意图记录。
- 可写记录：本文接收、进展与交付章节；主会话在同一工作区直接审查，并维护权威总计划。

## Goal and acceptance / 目标与验收

交付无 snapshot 加载时的整体工作台骨架，覆盖初次进入、房间／频道切换。对应 A01、A02、A06 初次加载部分、A07 基础语义和 A09 编辑器占位约束。沿用现有布局与主题，不加载占位编辑器，旧请求不覆盖当前目标状态，错误和无房间状态保留。

## Inputs and eligibility / 输入与可开始条件

无前置 task。已核对意图、总计划、代码基线和工作区；实施范围已授权，分配唯一，无共享写入冲突。

## Scope and files / 范围与文件

- 新增 `web/src/components/AppSkeleton.vue`、`web/src/domains/room/RoomLoadingSkeleton.vue`。
- 修改 `RoomPage.vue` 的无 snapshot 加载分支、房间打开时的状态与查询范围保护。
- 维护本功能意图、总计划及三个 task 方案；不实施 T02、T03。

## Technical decisions / 局部技术设计

- `AppSkeleton` 为静态装饰块，使用主题颜色，尺寸通过聊天室局部样式确定。
- 聊天室骨架复用 `RoomWorkbench` 的三个插槽；展示频道／话题／成员列表、消息作者与正文、输入轮廓、详情与队列轮廓。占位工作台使用 `inert` 和 `aria-hidden`，外层提供一个读屏加载提示及忙碌状态。
- 无 snapshot 且 loading 时挂载骨架；有 snapshot 时保留原渲染分支，错误和空房间分支保持明确。
- 在 `openRoom` 开始时取消旧查询、设置 loading 并清除旧错误，以版本号保护频道列表等待后的成功和失败路径。频道列表未就绪时发生目标变化，重新按最新目标发起打开流程；失效加载不执行后续滚动。

## Implementation outline / 实施安排

1. 完成骨架组件和插槽内容，复用既有样式并限制占位内容溢出。
2. 接入加载入口及范围保护，审查首次进入、切换、取消、失败和空状态路径。
3. 执行已有前端开发检查，登记交付和待用户界面检查项。

## Checks and delivery / 检查与交付

按总计划在 `web/` 执行类型、lint、格式和已有单测；静态呈现不新增模板镜像测试。检查记录写入下方交付章节，交付版本使用基线加明确路径的工作区 diff，不执行提交。浏览器、慢请求及真实焦点／滚动检查由用户测试，未执行项如实登记。

## Risks / 风险

本轮不细分已有 snapshot 下的加载状态；短请求防闪烁和视觉校准仍属于后续节点。自动检查不能证明实际布局和辅助技术体验。

## Reception and progress / 接收与进展

| 时间 | 分配编号 / 执行者 | 接收、进展或阻塞 | 证据 / 回报位置 |
| --- | --- | --- | --- |
| 2026-11-16 17:26:03 | T01-e17cf59c-6bd3-4a27-b1a7-9adf25387d67 / 当前 Codex 主会话 | 已接收；方案修订 1，用户授权 T01 Implementation 与开发检查。实际基线 `396f703`，无前置节点，协议和工作区可读写 | 本文与总计划执行登记；当前会话直接实施，无转交 |
| 2026-11-16 17:32:15 | T01-e17cf59c-6bd3-4a27-b1a7-9adf25387d67 / 当前 Codex 主会话 | 已完成整体骨架、加载入口和过期请求保护；复核后将发送占位对齐现有编辑区，并将读屏提示放在忙碌区域之外。开发检查通过 | 下方交付记录；无阻塞或范围扩大 |

## Delivery and review / 交付与审查

### Delivery / 交付记录

- 交付时间：2026-11-16 17:32:15。
- 执行者：当前 Codex 主会话；分配编号 `T01-e17cf59c-6bd3-4a27-b1a7-9adf25387d67`；方案修订 1。
- 实际变更：新增通用静态骨架和聊天室骨架；`RoomPage.vue` 接入无 snapshot 加载分支，在房间切换开始时进入加载并取消旧查询，以版本保护频道列表结果，处理列表未返回时的频道目标变化，失效加载退出后不继续滚动。
- 范围偏差：无；刷新及新查询状态衔接、延迟显示和动效细化留在后续 task。

| 验收范围 | 交付证据与结果 |
| --- | --- |
| A01 | `RoomLoadingSkeleton` 复用 `RoomWorkbench`，提供导航、消息、输入及详情／队列插槽占位；静态审查沿用相同断点与折叠偏好，实际跨视口观感待用户检查 |
| A02 | 代码审查确认 `openRoom` 的成功和失败均检查查询版本与 active，等待频道列表期间目标变化会重新打开最新目标；旧加载失败返回后不执行频道打开的滚动。快速切换的运行实测尚未执行 |
| A06 初次加载 | 条件为 `!snapshot && loading`；加载失败设置错误并结束 loading，原重试及无房间分支保留；错误、重试和空状态路径已审查，真实接口失败界面未实测 |
| A07 基础语义 | 一个复用现有翻译的 `role=status` 提示，位于 `aria-busy` 区域之外；装饰工作台 `aria-hidden` 且 `inert`，骨架块不可聚焦，使用主题变量且没有动画。读屏实际体验待检查 |
| A09 编辑器约束 | 输入占位仅由 `div` 和 `AppSkeleton` 组成，不挂载真实编辑器；发送、草稿及待确认发布保存逻辑没有修改 |

开发检查均在 `D:/SourceCodes/mywork/conflua/web` 使用既有入口执行：

| 命令 | 结果 |
| --- | --- |
| `corepack pnpm typecheck` | 通过；布局收尾后复跑通过 |
| `corepack pnpm lint` | 通过；布局收尾后复跑通过 |
| `corepack pnpm format` | 通过；布局收尾后复跑通过 |
| `corepack pnpm test --reporter=default --silent=false --no-color` | 26 个测试文件、178 项测试通过，未输出警告；最后仅整理骨架模板和样式，未改变已检查的请求逻辑 |
| `git diff --check` 及新增文件空白检查 | 通过；新增文件使用 no-index 检查，并区分正常差异退出码与空白错误 |

本轮没有新增或删除测试；项目现有 Vitest 为 Node 环境，静态占位不增加模板镜像测试或整页模拟。未运行浏览器、桌面应用、慢请求、快速切换、折叠／窄屏及真实读屏测试，沿用用户自行测试的安排；没有启动或停止服务，也没有执行整体 Verification。

可访问版本为代码基线 `396f703fd4221fdb7d8b38201133ba429abbeb35` 加当前工作区以下三个产品文件，未创建提交。无前置 task 版本。

| 文件 | SHA-256 |
| --- | --- |
| `web/src/components/AppSkeleton.vue` | `3FDD783F6332B140CD2842779E3F91848F9979BB484C00995EECCF029EBFD76F` |
| `web/src/domains/room/RoomLoadingSkeleton.vue` | `529C00E909FA03265D26BD7D11BF1DC5B33C96799BA0C1AD0F2F9CA68B15B2C6` |
| `web/src/domains/room/RoomPage.vue` | `7221C33110C3C69C60C48E141712DC91BC9A06D61908E9066CB45C70B063C724` |

未完成项与风险：界面运行证据尚未采集；同一查询刷新时保留内容属于 T02，视觉校准与短请求策略属于 T03。本轮没有新增阻塞，后续 task 需要以主会话接受的本交付版本为基线，并获得对应实施授权。

### Review / 审查记录

2026-11-16 17:34:19：主会话已读取并核对当前分配的交付记录、产品修改和文件 SHA-256；接受 T01 实现与开发检查，权威状态见总计划 Delivery review。界面实测和父级剩余验收仍按上述边界保留，T02、T03 未开始。
