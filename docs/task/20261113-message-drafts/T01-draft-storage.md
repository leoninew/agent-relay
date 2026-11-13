# Task / 子任务 T01：草稿读写
最后修改时间: 2026-11-13 11:36:39

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[刷新后恢复未发送消息草稿](../../intent/20261113-message-drafts.md)。
- 权威总计划：[20261113-message-drafts](../../plan/20261113-message-drafts.md)；任务 ID：T01；方案修订：2。
- 权威协调根：`D:/SourceCodes/mywork/agent-relay`；分配、依赖与仲裁以总计划为准，本文的方案状态不表示交付状态。

## Handoff basis / 交接依据

- 已分配本会话架构师，编号 `T01-80a27839-41df-45d9-9d51-7826716366e5`。
- 协议入口：`C:/Users/wangm25/.codex/plugins/cache/specflow-local/specflow/0.2.1/skills/specflow/references/task-coordination.md`。
- 本次分配与授权来源：总计划阶段授权及分配历史，消息 `room-a2493e542ba3-msg-0113` 授权实施。
- 代码工作区与基线：权威协调根，09556ed 加接收记录注明的并行工作区；交付为 T01-v1。
- 可写记录位置：分配后仅在本文的“接收与进展”“交付与审查”及最后修改时间记录执行事实；产品范围如下。
- 回报方式：执行会话输出含任务 ID、分配编号和记录路径的接收／阻塞／交付摘要，交由主会话核对；不自动通知其他成员。

## Goal and acceptance / 目标与验收

主要交付：按房间读取、保存、删除草稿的简单函数。

- 支撑 A01、A02、A05、A06；本节点不宣称浏览器刷新恢复已完成。
- 正常存储条件下，完整 MessageDraft 可按 roomId 保存、读回、删除，不串房间。
- 不创建 publicationId，不写已有待确认请求键。

## Inputs and eligibility / 输入与可开始条件

直接前置以总计划任务定义表为准，本节点无前置交付。沿用现有 MessageDraft 与 JSON 存取方式。

已核对总计划及本方案 Accepted、实施授权、有效分配和实际基线；本节点新增文件，不与并行产品修改冲突。

## Scope and files / 范围与文件

- 新增 `web/src/stores/messageDrafts.ts` 和 `web/tests/stores/messageDrafts.test.ts`，命名可依仓库惯例微调并回报。
- 允许复用 `web/src/services/storage.ts` 的类型；若必须补 accessor，保留全部既有 localStorage 行为。
- 不修改 RoomPage、RoomComposer、通用 AppInput、后端接口或已有发布恢复逻辑。

## Technical decisions / 局部技术设计

- 遵循总计划 D01，使用 sessionStorage 的 `relay-draft:<roomId>`，直接保存 MessageDraft JSON。
- 只提供读取、同步保存、按房间删除；没有记录时返回空结果。
- 浏览器存储故障不属于本任务；不加格式版本、草稿修订、发送关联、错误状态或故障提示。

## Implementation outline / 实施安排

1. 复用业务类型及已有存储约定，实现按房间读、写、删草稿。
2. 检查正常读回与房间隔离，记录下游可使用的函数和实际交付版本。

## Checks and delivery / 检查与交付

- 在 `web` 运行 `corepack.cmd pnpm test tests/stores/messageDrafts.test.ts`；必要类型／lint 检查使用总计划列出的既有入口。
- 检查多行与空白原值、完整上下文、房间隔离及删除；不测试存储故障或坏缓存。
- 测试只验证本节点的存储行为；不同 fake 实例不能当成真实浏览器标签页或刷新证据。
- 交付列出读写函数、实际 diff／版本、检查结果及未运行项，供主会话审查并固定下游基线。

## Risks / 风险

- 使用 sessionStorage，不改变已有 localStorage 消费者或待确认发布记录。
- 若需要扩展任务边界，先回报主会话，不重新引入已被用户排除的存储故障处理。

## Reception and progress / 接收与进展

2026-11-13 11:28:14：本会话架构师接收 `T01-80a27839-41df-45d9-9d51-7826716366e5`，方案修订 2，授权来源为消息 0113 及总计划阶段授权。实际基线为 09556ed 加当前工作区；无前置交付。产品修改限于简单草稿读写和必要测试。

关键进展记录已做事项、剩余范围、证据和待仲裁事项；仅更新执行事实，不改总计划归属或方案状态。

## Delivery and review / 交付与审查

2026-11-13 11:29:40：本会话以编号 `T01-80a27839-41df-45d9-9d51-7826716366e5`、方案修订 2 交付工作区 T01-v1。

- 实际变更：新增 `web/src/stores/messageDrafts.ts` 与对应测试；提供 load／save／remove，正常 JSON 读写，不增加额外字段或容错。
- 检查：`corepack.cmd pnpm test tests/stores/messageDrafts.test.ts`，2 tests passed；覆盖原值及上下文、快照、房间隔离、删除和既有 pending 键保留。
- 版本位置：当前共享工作区上述两文件，基线 09556ed；无前置输入。主会话已核对实现与结果，接受此版本供 T02 使用。
- 范围偏差、未完成项、下游阻塞：无。浏览器刷新尚不适用本节点；11:36 集成补充：全量 93 tests、类型／build、格式检查通过，ESLint 0 errors、20 条既有 warning。

记录成功后输出“交付待审查”摘要；由主会话核对后维护 submitted／accepted，不自行宣称交付已接受。记录失败时明确“交付记录未完成”，不能据此放行 T02。
