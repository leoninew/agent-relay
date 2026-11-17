# Task / 子任务 T04：频道会话与消息投递
最后修改时间: 2026-11-14 12:30:00

## Review status / 审查状态

Draft，未分配。

## Parent and authority / 父任务与权威记录

- [意图](../../intent/20261113-channels-worktrees.md)；[总计划](../../plan/20261113-channels-worktrees.md)，协调根 `D:\SourceCodes\mywork\agent-relay`，T04，修订 3。

## Goal and acceptance / 目标与验收

- A04、A05、A07、A08：以频道工作目录发现及绑定会话、发现能力并投递；保持身份唯一、原状态和非重发语义。

## Scope and files / 范围与文件

- members、capabilities、delivery、desktop 应用与 Codex/dispatch、投递仓储资格过滤及测试；共享 schema 不变，存储结构缺陷回交 T01。

## Inputs / 输入

- T01 模型和 T03 频道资源/消息契约均已接受且版本可用；消费频道工作目录、消息、成员和事件接口。

## Technical decisions / 局部技术设计

- 会话候选、绑定、在线刷新和能力查询核对实际频道 cwd；同一 room 的活动 Agent session 唯一，最终以 DB 唯一约束处理并发绑定。目录缺失或频道已归档时不能绑定和投递，不移动/恢复 thread；归档只释放 Relay 身份，不消除原会话历史。
- `ClaimedDelivery` 携带频道和 cwd，envelope 同时带 roomId/channelId；catalog 另给 workingPath。claim 只能选择活动房间未归档频道的活动成员；归档和 claim 在写事务中互斥，submitting 时归档拒绝。activation 也核对归档时间；queued/unknown 的精确历史观察可继续，不能补投或激活归档频道。目标仍按 session 串行，保留原 client ID 及 queue/steer 回执。
- 向会话提交和 queue/start 前获取 T01 的共享频道 guard，并在锁内重查活动资格，锁跨外部写入保留至结果保存/标未知；归档使用同一 guard，避免核验后归档、随后才 activation 的竞态。DB 事务不跨 RPC，无法取锁不重复外部动作。
- 桌面退出通知以频道为单位筛选目标并生成频道级 publication ID，避免广播到其他频道。默认频道迁移投递继续使用原目录和回执。

## Implementation outline / 实施安排

1. 更新会话绑定、元数据、skill/MCP 目录及相关校验。
2. 更新投递 claim、envelope、cwd 与通知；沿用既有恢复与不重发策略。
3. 完成目录、绑定竞争、通知隔离和旧投递测试，交付服务契约。

## Checks and risks / 检查与风险

- `uv run --locked pytest tests/unit/application/test_member_binding.py tests/unit/application/test_capabilities.py tests/unit/application/test_delivery_actions.py tests/unit/application/test_desktop_exit.py tests/unit/infrastructure/codex tests/unit/infrastructure/dispatch`；补充双频道与旧回执案例。
- 旧 Agent 作用域缺失由 T05 在任何工具副作用前返回 channel_required/身份不匹配；不依赖用户勾选版本。补充归档与 claim、activation、晚到回执竞争场景。

## Handoff basis / 交接依据

- 未分配；协议入口 `C:/Users/leon/.codex/plugins/cache/specflow-local/specflow/0.2.1/skills/specflow/SKILL.md` 和 `references/task-coordination.md`。
- 总计划记录授权和基线；在本文回报接收、进展与交付，主会话读取，默认输出可复制摘要。

## Reception and progress / 接收与进展

- 未接收。

## Delivery and review / 交付与审查

- 尚无交付；执行时记录检查、版本、未验证项及风险。
