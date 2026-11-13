# Task / 子任务 T02：编辑保存与恢复
最后修改时间: 2026-11-13 11:36:39

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[刷新后恢复未发送消息草稿](../../intent/20261113-message-drafts.md)。
- 权威总计划：[20261113-message-drafts](../../plan/20261113-message-drafts.md)；任务 ID：T02；方案修订：2。
- 权威协调根：`D:/SourceCodes/mywork/agent-relay`；依赖、版本条件、分配和仲裁均以总计划为准。

## Handoff basis / 交接依据

- 已分配本会话架构师，编号 `T02-99fbdd8b-bd77-4802-a80f-539daa09b90f`，依据消息 0113 实施授权。
- 协议入口：`C:/Users/wangm25/.codex/plugins/cache/specflow-local/specflow/0.2.1/skills/specflow/references/task-coordination.md`。
- 分配与授权来源：总计划阶段授权及分配历史，方案修订 2；仅实施当前节点及必要检查。
- 代码工作区与基线：09556ed 加已接受 T01-v1 及并行工作区，实际位置见接收记录；交付为 T02-v1。
- 可写记录位置：分配后在本文接收、进展、交付章节及最后修改时间记录事实；产品写入范围如下。
- 回报方式：执行会话输出可复制摘要，由主会话核对本文；不自动派发或通知其他执行者。

## Goal and acceptance / 目标与验收

主要交付：在草稿存储之上接通输入期间的同步保存与完整编辑上下文恢复。

- 负责 A01、A02、A03，支撑 A08；浏览器行为结论需另有人工证据。
- input／compositionend 提交到模型的正文、空格、换行在当前调用内保存，不等待失焦或卸载。
- 房间隔离；恢复正文、目标、能力及引用 ID，房间切换不丢引用、不接受过期异步结果。
- 元数据未就绪时不按空列表过滤目标；失效对象提示处理并保留正文，不静默替换接收人。
- 保存与恢复不新增 Toast、保存状态、路由刷新、业务订阅或后端写请求。

## Inputs and eligibility / 输入与可开始条件

前置及版本条件仅引用总计划任务定义表。实际需要 T01 已被主会话接受的草稿读写函数；交付版本必须进入工作基线并可读取。

已核对 RoomPage 的 roomId／加载版本、RoomComposer 即时过滤、AppInput 输入法提交及消息查询接口；方案、授权、有效编号和前置版本均已核对，实际接收见后文。

## Scope and files / 范围与文件

- 修改 `RoomPage.vue`、`RoomComposer.vue` 的编辑、房间恢复、引用和元数据校验区域。
- 需要时提取简单的 `useRoomDraft.ts`，使用现有 Node 入口做必要行为检查，不为测试重构无关模块。
- 不改通用 AppInput 的输入法策略；不新增服务端接口或持久化设置。
- 与 T03 共享页面及可能提取的 composable；本节点交付由主会话接受后再交 T03 写入，不并行改动。

## Technical decisions / 局部技术设计

- 遵循总计划 D02；可用同步 watcher 或显式 setter，不能只靠默认异步 watcher。在 Node 中可用 Vue 响应式作用域检查保存时点。
- 初始化先读取后开放保存，保存暂停／恢复边界显式可控；冻结请求期间不能把锁定显示的 payload 当成普通新编辑覆盖独立草稿。
- 每个房间保存独立编辑状态；replyToMessageId 为引用唯一持久化来源，显示消息按房间加载版本解析。
- 区分“尚未加载”和“有效空列表”，避免 RoomComposer 的 immediate watcher 在初始化时丢失选择。恢复结果不自动选中替代目标。
- 仅明确缺失引用才移除；临时查询失败保留 ID，并允许后续重查。旧房间／旧引用响应不能回填当前编辑。
- 默认路由选择与用户编辑上下文分开判断；清空正文仅移除正文，取消引用仅移除引用，剩余有效上下文仍可保存。
- 向 T03 交付保存与恢复顺序及 reset 衔接点；不暴露草稿修订或发送关联机制。

## Implementation outline / 实施安排

1. 在已接受的 T01 基线上建立房间草稿状态与同步保存、恢复阶段控制。
2. 接入编辑器模型与引用来源，修正元数据就绪前过滤及过期查询回填。
3. 沿用既有发送校验，完成必要 Node 检查，交付包含 T01 的完整版本及 T03 衔接点。

## Checks and delivery / 检查与交付

- 在 `web` 运行 `corepack.cmd pnpm test tests/stores/messageDrafts.test.ts tests/domains/room/useRoomDraft.test.ts`，并使用既有 typecheck、改动范围 lint／格式入口。
- 重点检查模型变更后立即读存储、初始化不写空值、房间切换、引用与能力恢复、元数据加载期间保留选择及恢复不触发发送。不增加存储故障测试。
- 不为此引入组件挂载环境。中文输入法候选字与真实刷新时点由后续人工验证，不用模拟调用证明浏览器体验。
- 交付记录明确 T01 实际版本、编辑状态契约、Node 证据和未验证交互。本节点不宣称成功发送／清理生命周期已经验收。

## Risks / 风险

- 引用目前独立于 MessageDraft，迁移来源时可能造成循环 watch 或取消引用未保存；需控制更新方向。
- 切房间后的旧查询与 immediate 过滤会覆盖恢复内容；房间版本和就绪状态必须可检查。
- T02 是中间产物；T03 未完成前不能发布整项草稿功能。

## Reception and progress / 接收与进展

2026-11-13 11:29:40：本会话架构师接收 `T02-99fbdd8b-bd77-4802-a80f-539daa09b90f`，方案修订 2，依据消息 0113 及总计划授权。实际基线为 09556ed、已接受 T01-v1 和并行工作区；已核对 T01 三个读写操作与 2 tests passed。RoomComposer 只改草稿逻辑，保留并行样式改动。

后续仅记录实际进展、阻塞、证据及待仲裁事项，更新最后修改时间；不改总登记或自行标记交付 accepted。

## Delivery and review / 交付与审查

2026-11-13 11:32:31：本会话以编号 `T02-99fbdd8b-bd77-4802-a80f-539daa09b90f`、方案修订 2 交付工作区 T02-v1。

- 实际变更：新增 useRoomDraft 及四项 Node 检查；接入 RoomPage，模型深度变化同步写入；引用 ID 随草稿恢复、取消引用同步保存；RoomComposer 等待元数据就绪并跳过锁定状态过滤。保留并行样式 hunk。
- 输入版本：已接受 T01-v1。实际位置为当前工作区新增 composable／测试和 RoomPage／RoomComposer diff，主会话可直接访问。
- 检查：两份定向测试 6 passed，`pnpm typecheck` 通过；Prettier 发现 watch 数组换行，已修正，最终集成时复查。
- 验收：Node 覆盖 A01／A02 的模型保存与房间隔离、引用及能力恢复；A03 的页面元数据与引用恢复通过代码审查，真实 UI／输入法尚未验证。A07 已撤销。
- 范围偏差：无。11:36 集成补充：T03 已完成发布成功清理及房间生命周期，全量 93 tests、类型／build、格式检查通过，ESLint 0 errors、20 条既有 warning。真实 UI／输入法仍未实测。

写入完成后输出交付待审查摘要，请主会话审查完整基线。记录缺失、检查失败或版本不可访问时不得放行 T03；执行者不自行更新 submitted／accepted。
