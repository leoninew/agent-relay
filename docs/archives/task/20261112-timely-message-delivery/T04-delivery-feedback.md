# Task / 子任务 T04：用户状态与兼容说明
最后修改时间: 2026-11-12 10:13:33

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[提高消息投递时效](../../intent/20261112-timely-message-delivery.md)。
- 权威总计划：[Plan](../../plan/20261112-timely-message-delivery.md)，协调根 `D:\SourceCodes\mywork\agent-relay`；T04，方案修订 1。
- 本窗口执行，编号 `TIMELY-T04-01`；T01 前置已接受。

## Goal and acceptance / 目标与验收

让用户继续照常发消息，状态准确表达发送与接收事实，清空不误导为撤回，对应 A06、A07、A08。

- 不增加 queue/steer 模式选项，兼容旧字段和发布请求。
- 时间线、详情、待办面板用语一致；当前轮次输入不被当作可删除的原生队列项。
- 更新现行设计说明，并提供用户可直接操作的验收步骤，不宣称时效已经实测。

## Scope and files / 范围与文件

- `web/src/services/roomApi.ts`。
- `web/src/domains/room/deliveryStage.ts`、`MessageTimeline.vue`、`MessageQueue.vue`，必要的 `MessageDetails.vue/useMessageQueue.ts` 文案及类型消费。
- `docs/design/codex-session-chat-collaboration.md`、`docs/design/codex-integration-capabilities.md` 的现行行为说明；保留历史证据的版本边界，不回写旧计划的交付事实。
- 仅同步三份现有 MessageQueue/MessageDetails/MessageTimeline 测试的状态断言，避免文案漂移，不新增或运行 UI 测试。
- 不改后端业务、driver、迁移、发布表单流程或能力选择；不新增 UI 测试。

## Inputs / 输入

直接前置 T01：需主会话接受可访问的 API 字段、状态含义、queue-only 删除边界和检查证据。自动路由语义已在总计划确定，不等待 T02/T03 再选择方案；最终集成需主会话核对 T03 实际行为。

## Technical decisions / 局部技术设计

- TS `Delivery` 增加可空 `submissionMethod/steeredTurnId`，状态枚举保留。旧客户端不提供方法，前端不把方法变成发送参数或用户偏好。
- 保留已接收/接收中判定的事实来源，把 pending/submitting 的“入队中”改为“发送中”；失败/未知分别为“发送失败 / 发送待确认”。状态未知不新增自动重试。
- 更新待办空列表描述，明确待办面板包含待接收确认的消息，不等于 Codex 原生 queue。清空反馈说明只移除待办、不能撤回已送入会话内容；不把 steer 无队列凭证说成上游删除失败。
- 详情若展示时间，queue 才有 queuedAt；steer 不凭 updatedAt 伪造入队时间。历史 receivedAt 仍表示输入确认，不能展示成已处理或已回复。
- 现行接入文档说明自动路由、旧队列积压不重投、两类接纳回执、精确历史确认、原 proxy 调用以及未知不重发。保留旧版本能力探测的历史结论。

## Implementation outline / 实施安排

1. 更新 wire 类型与共享状态函数，检查所有调用处用词一致。
2. 调整时间线、详情、待办空态及清空反馈，不增加发送选项。
3. 更新现行设计说明，记录 schema 与真实行为验证的证据边界。
4. 运行前端静态检查/build，给出以下手工验收步骤，由用户验证真实工作者表现。

## Checks and risks / 检查与风险

- 在 `web` 运行 `corepack pnpm typecheck`、`corepack pnpm lint`、`corepack pnpm format`、`corepack pnpm build`；只记录实际结果，格式问题只修本任务范围。
- 不新增或运行浏览器、整页、组件/UI、真实 SQLite 或跨层测试；不因测试缺失恢复用户删除目录。
- 用户验收步骤：目标长任务运行时照常发送，确认无需选择模式且新消息进入当前轮次；目标空闲时发送，确认原队列可受控启动；发送带 Skill 的消息检查能力保留；对照详情确认接纳/历史接收含义；清空待办确认提示不宣称撤回。
- 验收忙碌场景须记录消息创建、提交接纳及历史接收时间。工具长时间执行或审批等待可能延迟模型处理，不能用页面状态单独推断工作者已读或已执行。

## Handoff basis / 交接依据

- 本窗口，`TIMELY-T04-01`；用户“开始实现”授权，已核对 T01 API 字段、语义与清空边界。
- 协议入口：`C:/Users/leon/.codex/plugins/cache/specflow-local/specflow/0.2.1/skills/specflow/SKILL.md` 及其 `references/task-coordination.md`。
- 授权、依赖及基线以权威总计划为准；派发时补 T01 已接受版本。
- 可写回报位置：本文“接收与进展 / 交付与审查”；主会话直接读取。默认输出可复制摘要，由用户转交，不发送协作消息。

## Reception and progress / 接收与进展

2026-11-12 09:39，本窗口接收 `TIMELY-T04-01`，修订 1；依据用户“开始实现”，当前工作区包含已接受 T01 字段及 T02/T03 后端，无前端并发修改。

| 时间 | 分配编号 / 执行者 | 接收、进展或阻塞 | 证据 / 回报位置 |
| --- | --- | --- | --- |

## Delivery and review / 交付与审查

- 2026-11-12 10:13 整体验证复核：web 产品代码未变，32 项相关既有组件断言通过；jev 实测成员添加、发送、Skill 选择、接收状态、预期能力失败详情与清空说明。真实链路不再是未验证项，仍不承诺模型处理 SLA；见[验证记录](../../verification/20261112-timely-message-delivery.md)。下方保留 Implementation 历史交付事实。

- 交付：2026-11-12 09:44:20，本窗口，`TIMELY-T04-01`，修订 1；当前 web/设计说明/现有断言 diff，使用已接受 T01 字段并核对 T02/T03 实际实现。
- 实际变更：新增可空且可选的 TS 投递事实兼容旧响应；统一发送/接收/失败状态，修正详情将失败显示为发送中的问题；待办清空提示说明已送入内容不能撤回，无模式开关。
- 验收：A06/A07 状态与清空语义已审查，A08 typecheck/lint/Prettier/build 通过。三份既有组件测试仅更新断言，未运行，也未增加任何 UI 测试。
- 保留 warning：既有 MessageTimeline `v-html` 规则及生产 bundle >500 kB 提示，均非本次新增错误，不扩展整改范围。
- 未完成用户验收：真实长任务中的消息时效、空闲启动、能力引用和清空界面，按本文手工步骤执行。没有真实会话或数据库操作。
- 主会话开发交付审查接受；整体 Verification 未开始，未创建 Git 提交。
