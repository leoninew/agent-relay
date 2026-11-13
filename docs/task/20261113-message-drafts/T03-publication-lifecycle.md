# Task / 子任务 T03：发送后清理
最后修改时间: 2026-11-13 11:36:39

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[刷新后恢复未发送消息草稿](../../intent/20261113-message-drafts.md)。
- 权威总计划：[20261113-message-drafts](../../plan/20261113-message-drafts.md)；任务 ID：T03；方案修订：2。
- 权威协调根：`D:/SourceCodes/mywork/agent-relay`；只由主会话维护依赖、分配与交付审查。

## Handoff basis / 交接依据

- 已分配本会话架构师，编号 `T03-7ea4c9b2-d505-49d7-a8bf-300a4b3aa848`；消息 0113 授权实施及必要检查，不含整体 Verification。
- 协议入口：`C:/Users/wangm25/.codex/plugins/cache/specflow-local/specflow/0.2.1/skills/specflow/references/task-coordination.md`。
- 分配与授权来源：总计划阶段授权及分配历史，方案修订 2，允许修改发布／清理区域及本文执行记录。
- 代码工作区与基线：09556ed 加已接受 T02-v1（含 T01-v1）和并行工作区；最终交付为 T03-v1。
- 可写记录位置：分配后在本文接收、进展、交付章节及最后修改时间记录事实；产品范围如下。
- 回报方式：执行会话输出接收／阻塞／交付待审查摘要，由主会话读取证据并仲裁；不自动进入父级验证。

## Goal and acceptance / 目标与验收

主要交付：把编辑草稿与既有冻结发布、房间删除及清空历史衔接为不会误删或重复发送的完整生命周期。

- 负责 A04、A05、A06、A08，并集成复核 A01–A03；A07 已撤销。
- 有效待确认发布优先显示，原 publicationId／payload 不变；普通恢复无发送动作或新 ID。
- 明确发送失败可继续编辑，结果未知保留原核对入口；成功按发送所属房间清理，其他房间不受影响。
- reset 不复活旧内容；清空正文、取消引用、删除成功／失败和清空历史符合父级规则。
- 既有 Node 检查、类型、lint、格式和构建通过，或如实记录不通过与原因；真实浏览器体验单独列待验证。

## Inputs and eligibility / 输入与可开始条件

依赖仅以总计划任务定义表为准。输入为主会话已接受的 T02 完整基线，包含其已接受的 T01 版本、编辑状态操作契约和检查证据；开始前核对两者实际版本是否仍有效。

复用 RoomPage 的 pendingPublication、主动 resume／lookup 流程及 rooms store 删除成功边界；方案、实施授权、有效分配和共享文件范围均已核对，实际接收见后文。

## Scope and files / 范围与文件

- `RoomPage.vue` 的 openRoom、sendMessage、publish、clearCurrentRoom 及相关生命周期区域。
- `RoomComposer.vue` 的 reset 衔接及必要草稿行为测试；提取了 composable 时同步维护。
- `web/src/stores/rooms.ts` 的删除确认成功边界和 `web/tests/stores/rooms.test.ts` 的必要行为用例。
- 不新增保存故障提示或相关词条；若需要扩大读写函数范围，先回报主会话。
- 不修改后端幂等发布契约、后台调度或真实数据库，不增加自动重发、服务端草稿和端到端环境。

## Technical decisions / 局部技术设计

- 遵循总计划 D03，沿用现有待确认请求、publicationId 和编辑锁定行为，不增加草稿修订或发送关联字段。
- 恢复待确认请求时可锁定其显示，但不得让编辑器 watcher 把冻结 payload 覆盖为另一份普通草稿；元数据校验也不能改变冻结发送目标。
- 成功回调按发送时的 roomId 清除草稿，不能用切换后的当前房间 ID 删除其他房间内容。
- 清理、reset、引用清空及恢复自动保存使用明确顺序，防止旧内容回写。仅默认话题选择不自动形成“已发送内容”的新草稿。
- 明确拒绝解锁时保留对应编辑快照；未知结果保持冻结请求和原主动核对流程，不能因草稿持久化自动分配新 ID。
- rooms.remove 成功后清理对应草稿；API 失败时不清理。clear history 保留正文，重查引用，处理过程中不以空列表冲掉未发送内容。

## Implementation outline / 实施安排

1. 在 T02 基线上接通待确认请求优先恢复，保留现有发布流程。
2. 接通明确拒绝、未知结果、确认成功和 reset 的保存／清理顺序，保护旧房间及旧回调。
3. 接通删除房间成功清理与清空历史保留策略，检查引用失效处理。
4. 补必要 Node 行为用例，运行集成开发检查，交付 A01–A06、A08 的实际覆盖和待人工项。

## Checks and delivery / 检查与交付

- 在 `web` 使用 `corepack.cmd pnpm test`、`corepack.cmd pnpm typecheck`、`corepack.cmd pnpm lint`、`corepack.cmd pnpm format`、`corepack.cmd pnpm build`；仓库根运行 `git diff --check`。
- 检查 pending 优先且不产生写请求、原 payload／ID 保留、发送拒绝与未知结果保留、成功清理发送房间、reset 不回写、删除成功与失败、清空历史保留。浏览器存储故障不纳入测试。
- 用既有 Storage／API 替身和领域状态检查，不启动真实浏览器、WebView、服务或数据库。必要提取只围绕本功能状态边界，不为测试做无关重构。
- 交付时逐项区分 Node 已验证、静态检查已验证、人工未验证，特别列出真实刷新、输入法和标签页隔离缺少的证据。
- 汇集实际 diff、T01／T02 输入版本和全部检查结果，不创建整体 Verification 报告或执行 Git 写操作，除非后续授权已覆盖。

## Risks / 风险

- 发送成功的 reset 可能触发同步保存，需明确顺序，确保已发送正文不重新出现。
- 每个节点检查通过仍不代表真实刷新体验通过；整体结论由主会话结合父级证据给出。

## Reception and progress / 接收与进展

2026-11-13 11:32:31：本会话架构师接收 `T03-7ea4c9b2-d505-49d7-a8bf-300a4b3aa848`，方案修订 2，依据消息 0113 及总计划阶段授权。实际基线为 09556ed、已接受 T02-v1（含 T01-v1）与保留的并行工作区；已读取 6 项定向检查及 typecheck 结果，前置可直接访问。

后续记录实际进展、阻塞、证据、剩余范围及仲裁需求，更新最后修改时间；不自行修改总计划或方案状态来表示完成。

## Delivery and review / 交付与审查

2026-11-13 11:36:39：本会话以编号 `T03-7ea4c9b2-d505-49d7-a8bf-300a4b3aa848`、方案修订 2 交付当前共享工作区 T03-v1，输入为已接受 T02-v1（含 T01-v1）。

- 实际变更：useRoomDraft 增加按房间清理，RoomPage 成功发布后调用；clear history 取消引用并保留正文；RoomComposer reset 清引用，元数据未变化时不回写；rooms.remove 仅在删除 API 成功后清缓存。
- A04：沿用主动核对，pending 恢复保留 ID／payload，无自动发送；Node 已检查快照隔离，页面调用经代码审查。
- A05：Node 检查锁定／解锁后的内容保留、成功清理及 reset 不复活，网络拒绝／未知结果路径沿用原实现并经代码审查；没有运行真实 API 集成测试。
- A06：既有 rooms 测试扩展删除成功清理、删除失败保留、清空历史不删草稿断言；取消引用／正文清空和 reset 在草稿 Node 用例覆盖。
- A01–A03、A08：集成复核模型同步保存、房间隔离、上下文恢复及无新增订阅／后端写入；真实浏览器刷新、中文输入法及 WebView 交互仍待人工证据。
- 检查：`pnpm test` 15 files、93 tests passed；`pnpm build` 含 vue-tsc 通过，保留既有 500 kB chunk 提示；`pnpm lint` 0 errors、20 条既有 warning；最终 `pnpm format` 与 `git diff --check` 通过。
- 版本与位置：当前工作区的 RoomPage、RoomComposer、useRoomDraft、rooms、两个草稿测试及 rooms 测试；精确交接指纹见总计划实施结果。11:35 通过 Relay 消息 0118 释放 RoomComposer 给技能引用需求继续增量修改。
- 范围偏差、实现未完成项：无；未执行真实 GUI、服务或数据库验证，未进入整体 Verification、未创建验证报告，未暂存或提交。

记录完成后输出“交付待审查”摘要，请主会话审查；检查失败及人工证据缺失必须如实列明。主会话接受当前有效交付后维护执行登记，整体 Verification 另按阶段授权进入。
