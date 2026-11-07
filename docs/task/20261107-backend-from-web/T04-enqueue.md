# Task / 子任务 T04：真实 Codex 入队与未知结果恢复
最后修改时间: 2026-11-07 19:41:39

## Review status / 审查状态

Draft。修订 9 使用共享 daemon 的原会话 queue；T02 的发现/绑定与 T03 发布交付后，按本节点局部设计实现。

## Parent and authority / 父任务与权威记录

- [总意图](../../intent/20261107-backend-from-web.md)、[权威总计划](../../plan/20261107-backend-from-web.md)。任务 ID：T04；方案修订：10。
- 协调根：`D:/SourceCodes/mywork/agent-relay`；依赖与仲裁见总计划。

## Goal and acceptance / 目标与验收

G02、G06、G07 及 G10 轻量提交部分，对应 A04、A05、A16：真实入队凭证可解释，忙碌不阻塞提交，断连/崩溃未知结果不会被自动重发。

## Scope and files / 范围与文件

独立 `drivers/`、`delivery_service.py`、投递状态/凭证 repository、集中驱动/超时/并发配置、应用 lifespan 和驱动/调度测试。housekeeper 仅作参考；不读取输出后才认定入队。

## Inputs / 输入

见总计划 T04：T01 真实会话与协议契约；T03 持久 Delivery、目标快照、短事务、事件写入接口及其 T02 proxy/绑定版本。T02 是传递前置，不新增反向依赖。

## Technical decisions / 局部技术设计

- 队列驱动返回可区分的 queued/明确 rejected/unknown 结果。成功必须核验本次客户端标识及队列项 ID；保存目标会话、原始凭证必要字段和本地确认时间。
- D02 最新纠偏为已有会话绑定。复用 T02 的共享 daemon proxy 协议与原绑定，实现 queue/add 与 queue/list；不创建替代会话，不以 resume 接管原宿主。T01 已证明 active 可入队、分页可用、相同 clientUserMessageId 会产生新队列项；核对不能重放 add。
- 调度从 DB pending 领取；同一真实 session 按持久顺序发起，控制总并发，不等上一条模型输出。调用前短事务写 submitting、稳定 clientMessageId 与领取版本，外部 I/O 不持锁。
- 成功/拒绝/未知通过版本条件更新并追加事件，过期执行者不能覆盖新事实。RPC 已可能发出后，取消、超时、响应不匹配均保留 unknown；历史暂缺不是拒绝。
- 已确认 queued 永不因输出等待转失败。重启遗留 submitting 进入 unknown 核对，不恢复成 pending；后台唤醒丢失通过持久扫描找回尚未提交工作。
- 不以忙碌或 notLoaded 代替实际入队结果。需要核对时按本次标识查询 queue/list，准确命中只证明对应事实；列表暂缺不判拒绝。本轮不新增会话输出观察或历史扫描。
- Prompt 只含本次消息、成员职责、房间/消息标识、显式目标与可选查阅入口，不注入 Offset 区间全文。明确拒绝后的人工再发需新操作记录；不实现自动重试引擎。

## Implementation outline / 实施安排

1. 在 T02 proxy 协议基础上实现窄入队/核对端口、协议适配和回执分类，补确定性伪 RPC 测试。
2. 接上持久领取、调用前关联保存、短事务结果与事件；应用生命周期启动/停止提交器。
3. 实现重启 unknown、只读证据核对与无凭证时的诚实展示；只读展示确定或未知结果，不增加通用自动重试入口。
4. 在明确的隔离会话验证单目标/连续入队和忙碌情况，取得实际凭证；不使用用户工作会话做测试。

## Checks and risks / 检查与风险

- 伪 RPC 覆盖明确拒绝、响应丢失、凭证字段不匹配、过期领取者、数据库提交失败、重复调度及关闭中断。
- 重点故障点：上游接受后本地凭证落库前退出，恢复保持 unknown 且外部调用次数不增加；不声称跨系统恰好一次。
- 局部 pytest、mypy、ruff，加隔离环境协议证据；无法获得真实环境时标记未验证，不用模拟代替验收。

## Handoff basis / 交接依据

未分配。按总计划引用的 SpecFlow 协议接收有效编号、修订和实施授权；实际基线、隔离会话与前置版本由派发记录指定。本文为回报位置，主会话读取证据并审查；不自动发送测试消息。

## Reception and progress / 接收与进展

无接收、无入队调用。后续记录授权范围、隔离环境和前置核对事实。

## Delivery and review / 交付与审查

无交付。需记录实际协议版本、驱动/DB diff、凭证及故障证据、检查/复验、未支持的核对能力，并输出交付摘要。
