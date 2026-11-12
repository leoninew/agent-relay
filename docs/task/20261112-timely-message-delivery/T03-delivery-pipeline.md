# Task / 子任务 T03：投递流水线与公平调度
最后修改时间: 2026-11-12 10:13:33

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[提高消息投递时效](../../intent/20261112-timely-message-delivery.md)。
- 权威总计划：[Plan](../../plan/20261112-timely-message-delivery.md)，协调根 `D:\SourceCodes\mywork\agent-relay`；T03，方案修订 1。
- 本窗口执行，编号 `TIMELY-T03-01`，前置 T02/T01 已接受。

## Goal and acceptance / 目标与验收

将自动输入接入实际投递链路，并保证持续发送下接收观察仍有执行机会，对应 A01、A02、A03、A05、A06、A08。

- 两类结果正确落库；只有真实 queue 且保存成功才进行一次受控激活。
- received 只来自客户端 ID 精确匹配，恢复/观察不重投。
- 在途总量有界，提交和观察不互相饿死，同一 session 不重复观察。

## Scope and files / 范围与文件

- `src/agent_relay/application/delivery/service.py`。
- `src/agent_relay/infrastructure/dispatch/delivery.py`。
- 必要的 `bootstrap/http.py`、Codex/dispatch dependencies 类型接线，使用已确定的 DeliveryDriver，不改变 HTTP 发布契约。
- `tests/unit/application/test_delivery_actions.py`；新增 runner 单层测试放在 `tests/unit/infrastructure/`。
- 不修改 driver、共享 ports/domain/persistence、迁移或 web；发现契约缺口回到总计划，不自行扩展任务。

## Inputs / 输入

直接前置 T02：需主会话接受可访问的 submit adapter，基线包含已接受 T01，typed outcome、能力与不重发检查通过。派发时记录 T02 和其 T01 实际版本。

## Technical decisions / 局部技术设计

- service 依赖 `DeliveryDriver`，调用 submit，现有 envelope 和保存的能力引用原样传递；按 QueueReceipt/SteerReceipt/两类提交异常分派领域转换。
- `finish_delivery` 条件保存失败时不再采取外部动作；QueueReceipt 保存成功才调用现有 `activate_after_submission`。SteerReceipt、unknown、rejected 均不启动队列。
- 保留 observer 的最新页及旧历史游标，按 client ID 精确确认；不能因 steer 返回 turn ID、轮次完成或等待超时标记 received。
- 恢复仅将遗留 submitting 转 unknown。观察错误、软删除竞态和进程重启不触发输入重发，也不背景唤醒已停止会话。
- runner 在空槽分配时公平处理“已到期观察”和提交：两类均待办时交替一种任务；一类无可用任务时让另一类使用容量。用本地选择状态控制，保持全局 concurrency 上限，不另起无界观察线程池。
- 观察 session 轮转、每 session 至多一个在途观察；每约 2 秒刷新快照，去重加入到期待办集合，安排后才移除。到期但无容量时保留资格，不能覆盖或将其余 session 整体延期。单并发也强制两类交替，不能被慢观察反向饿死提交。
- 保留文件锁、同一目标 submitting 互斥、future 回收、关闭等待和 RPC 超时。公平性约束针对空槽分配，不承诺挂起 RPC 在指定时限内完成。

## Implementation outline / 实施安排

1. 将 service 切换 submit，分别保存两种接纳事实和安全失败事实。
2. 固定 queue-only、saved-only 激活分支，补足恢复/核验不重放的检查。
3. 重排 runner 空槽选择及到期资格维护，保持有界并发与轮转。
4. 单层验证持续提交、持续观察、单并发/多并发和保存/关闭竞态，交付主会话集成。

## Checks and risks / 检查与风险

- `uv run --locked pytest tests/unit/application/test_delivery_actions.py` 及本任务新增的 runner 单测。
- service 端口 Mock 检查两类回执、unknown、拒绝、保存失败、精确历史匹配、恢复和无额外激活；不串联真实仓储/driver。
- runner 用可控时钟与 executor/future 替身检查 concurrency=1/4、无限待提交输入、多 session 观察、观察异常、future 完成/关闭。避免真实 sleep 和时序敏感断言。
- 回执接纳和历史可见存在间隔；保留接收中，不能为改善显示而冒充 received。观察公平性改善不等于模型处理时延已降低。
- 运行相关 mypy/Ruff；不连接 SQLite、真实 proxy 或用户会话，不恢复 support 目录。

## Handoff basis / 交接依据

- 本窗口，`TIMELY-T03-01`；用户“开始实现”授权，前置 T02/T01 版本与检查已核对。
- 协议入口：`C:/Users/leon/.codex/plugins/cache/specflow-local/specflow/0.2.1/skills/specflow/SKILL.md` 及其 `references/task-coordination.md`。
- 授权、依赖及基线以权威总计划为准；派发时补 T02 及其 T01 已接受版本。
- 可写回报位置：本文“接收与进展 / 交付与审查”；主会话直接读取。默认输出可复制摘要，由用户转交，不发送协作消息。

## Reception and progress / 接收与进展

2026-11-12 09:36:44，本窗口接收 `TIMELY-T03-01`，修订 1，依据用户“开始实现”；当前工作区包括已接受 T02/T01，相关 50 单测及 mypy/Ruff 通过，无写入冲突。

| 时间 | 分配编号 / 执行者 | 接收、进展或阻塞 | 证据 / 回报位置 |
| --- | --- | --- | --- |

## Delivery and review / 交付与审查

- 2026-11-12 10:13 整体验证复核：service/runner 指纹不变，222 单测及 mypy/Ruff 复验通过；真实连续发布得到历史确认，清空后不重投，输入与 received 精确关联。长期公平性仍由并发 1/4 确定性单测支持；见[验证记录](../../verification/20261112-timely-message-delivery.md)。下方保留 Implementation 历史交付事实。

- 交付：2026-11-12 09:39，本窗口，`TIMELY-T03-01`，修订 1；当前 service/runner 与必要依赖接线 diff，基于已接受 T02/T01。
- 实际变更：服务调用 submit，steer 接纳待历史确认、queue-only/saved-only 激活、保留降级原因；到期观察集合与交替分配，保持全局并发上限。
- 验收：A01/A02/A03 服务端口 Mock 验证接纳、未知、保存失败、精确输入与恢复；A05 并发 1/4、持续两类/单类任务、观察异常及满容量释放；A06 不反向激活或重投；A08 单层替身。相关 19 单测、mypy（138 files）及定向 Ruff 通过。
- 未运行真实 SQLite、外部 RPC 或 UI；不新增时延保证。主会话审查接受，无遗留失败；整体用户时效验收待实施完成后安排。
- 最终 222 单测、mypy/Ruff/格式通过；service SHA-256 `fdcc5ca4aff17893f9787aec6e0449994fae993481d627a6136959d7147d8400`，runner SHA-256 `86615c7817ba81ec18184b9335b85f1f805e398042bc83690ab907826d09c21e`。T01 unknown 后历史确认修复已复核，仍按原 observer 精确匹配，不增加重发。
