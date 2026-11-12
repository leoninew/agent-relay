# Task / 子任务 T02：Codex 自适应输入
最后修改时间: 2026-11-12 10:13:33

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[提高消息投递时效](../../intent/20261112-timely-message-delivery.md)。
- 权威总计划：[Plan](../../plan/20261112-timely-message-delivery.md)，协调根 `D:\SourceCodes\mywork\agent-relay`；T02，方案修订 1。
- 本窗口执行，编号 `TIMELY-T02-01`，前置 T01 已接受。

## Goal and acceptance / 目标与验收

交付可直接调用的 `CodexDriver.submit`：忙碌时追加当前轮次，空闲时入队，严格限制竞态回退并保持原生能力输入，对应 A01、A02、A04、A08。

- 原会话、原客户端消息 ID、完整原生输入保持一致；不创建/恢复执行宿主。
- 能力失败不写入，steer 结果未知不补投；受限拒绝回退最多 queue/add 一次。
- 返回 typed 结果，协议字段不泄漏到 application。

## Scope and files / 范围与文件

- `src/agent_relay/infrastructure/codex/driver.py` 的输入构造、结构化 RPC 拒绝和 `submit`；传输保持共享 daemon 的 WebSocket-over-proxy。
- `tests/unit/infrastructure/test_codex_driver_unit.py`、`test_capability_delivery.py`，可新增专用单层 steer adapter 测试。
- 不改 T01 ports/domain/persistence、T03 service/runner 或 web。若需变更公共契约，先回总计划修订。

## Inputs / 输入

直接前置 T01：需主会话接受可访问的 `DeliveryDriver/SteerReceipt/SubmissionRejected/SubmissionUnknown` 契约及相应模型版本，相关检查通过。派发时记录实际版本，不能只凭 T01 自报完成开始。

## Technical decisions / 局部技术设计

- 用现有 `ProxyRpc.call`，不换成任意 JSONL stdin、不调用 `codex exec`、不模拟终端按键。`enqueue` 保留纯 queue 语义，`submit` 负责自动路由。
- 提取两条路径共用的输入预检，保留每目标项目目录、当前可用 Skill/MCP、强制 Relay Skill 和去重。`submit` 只构造一次完整输入，不能在 steer 路径丢失能力。
- 能力查询后重新读 thread 摘要；idle 直接 queue，active 只取最新一条 `thread/turns/list(itemsView=notLoaded)` 的有效 inProgress ID。最新条目不是活动轮次时按总计划降级，不使用 UI presence、不全量扫描历史。
- steer 必须传 `threadId/expectedTurnId/clientUserMessageId/input`。返回 `turnId` 与预期不符属于 unknown，不制造 queue receipt。
- `RpcRejected` 增加可访问的结构化 code/message/data 并兼容已有构造。仅 `-32601`，或总计划规定的参数类拒绝且状态变化，允许一次 queue fallback。其他内部错误、超时、断连或坏回执不回退。
- 拒绝后只复核一次状态，换轮次也不再尝试 steer；queue/add 失败不反向 steer。日志保留安全原因，页面不直接显示原始协议或认证内容。
- activeFlags 为等待审批/输入时不代答、不中断；追加输入不代表审批已解除，不另发启动请求。

## Implementation outline / 实施安排

1. 结构化保存 RPC 拒绝，整理共用输入构造和 queue 写入 helper，保证既有 enqueue 行为不漂移。
2. 实现最新状态/活动轮次定位以及 submit 的 typed steer/queue 结果。
3. 实现一次性、白名单竞态回退和明确的 unknown 传播。
4. 用 RPC 替身验证路线、原生输入、客户端 ID、异常分类和外部写入次数，交付 T03 可用版本。

## Checks and risks / 检查与风险

- `uv run --locked pytest tests/unit/infrastructure/test_codex_driver_unit.py tests/unit/infrastructure/test_capability_delivery.py`，连同本任务新增的单层测试运行。
- 至少覆盖 active 成功、idle、活动轮次不可定位、方法缺失、拒绝后 idle/换轮次/仍原轮次/复核失败、服务端内部错误、断连、超时、坏 turn ID、queue fallback 失败和能力缺失。
- 关键断言：可能已接纳后第二次输入写入为零；成功 steer 不触发 queue/add、queue/start 或 turn/start；所有输入保留原客户端 ID 和完整能力。
- mock/schema 结果不等于真实 steer 时效或历史关联已验证。本任务不向用户工作会话发送探测消息、不启动独立执行宿主；实际能力差异回报主会话。

## Handoff basis / 交接依据

- 本窗口，`TIMELY-T02-01`；用户“开始实现”授权，已核对当前工作区的 T01 契约交付与检查。
- 协议入口：`C:/Users/leon/.codex/plugins/cache/specflow-local/specflow/0.2.1/skills/specflow/SKILL.md` 及其 `references/task-coordination.md`。
- 授权、依赖及基线以权威总计划为准；派发时补 T01 已接受版本。
- 可写回报位置：本文“接收与进展 / 交付与审查”；主会话直接读取。默认输出可复制摘要，由用户转交，不发送协作消息。

## Reception and progress / 接收与进展

2026-11-12 09:33，本窗口接收 `TIMELY-T02-01`，修订 1，用户授权“开始实现”；实际输入为 `a5c0609` 上已接受 T01 工作区（ports 指纹见 T01），无冲突。

| 时间 | 分配编号 / 执行者 | 接收、进展或阻塞 | 证据 / 回报位置 |
| --- | --- | --- | --- |

## Delivery and review / 交付与审查

- 2026-11-12 10:13 整体验证复核：driver 指纹不变；实际 Codex 0.167.1 保留忙碌 steer 的原轮次、客户端 ID、必需/所选 Skill 与 MCP mention。9 条接纳输入各有唯一历史，无效能力零输入；见[验证记录](../../verification/20261112-timely-message-delivery.md)。下方保留 Implementation 历史交付事实。

- 交付：2026-11-12 09:36:44，本窗口，`TIMELY-T02-01`，修订 1；`a5c0609` 上当前 driver/test diff，使用已接受 T01 契约。
- 实际变更：同连接共用能力预检、最新轮次定位、steer/queue 自动路由、结构化 RPC 错误、受限竞态回退及安全降级 note。未改变 proxy 传输或执行宿主。
- 验收：A01 活动轮次/空闲路径；A02 明确拒绝、版本不支持、竞态和结果未知的写入次数；A04 原生能力及客户端 ID；A08 单层替身。相关 50 单测、全量 mypy（137 files）、定向 Ruff 通过。
- 修复：新增测试异常泛型收窄及格式已修复复验。无范围偏差；未运行真实 steer、SQLite 或界面检查，真实时效留待用户验收。
- 主会话审查接受，放行 T03；不创建 Git 提交。
- 最终纳入 222 全量单测、mypy/Ruff/格式检查通过；driver SHA-256 `80924437a3035056fb9b9ee7d32225191778a8621eca9129d1b6676ea14cca4d`。T01 历史确认约束修复不改变 adapter 契约，已复核兼容。
