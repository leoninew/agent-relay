# Task / 子任务 T02：worktree 生命周期
最后修改时间: 2026-11-14 12:30:00

## Review status / 审查状态

Draft，未分配。

## Parent and authority / 父任务与权威记录

- [意图](../../intent/20261113-channels-worktrees.md)；[总计划](../../plan/20261113-channels-worktrees.md)，协调根 `D:\SourceCodes\mywork\agent-relay`，T02，修订 3。

## Goal and acceptance / 目标与验收

- A01、A02、A07、A08：当用户选择 worktree 时，从当前 commit 创建独立 worktree 频道；默认不勾选，未选择时不执行 Git；失败由现有请求事务回滚数据库写入，不覆盖或清理外部资源。

## Scope and files / 范围与文件

- `application/channels`、Git adapter、频道仓储、请求事务依赖接线与测试。复用现有事务切面，不另设事务实现。

## Inputs / 输入

- T01 已接受且可访问的频道模型、查询/创建/归档端口与持久化版本；创建幂等规则取自总计划。

## Technical decisions / 局部技术设计

- 固定目录为 Relay 数据根 `worktrees/<room-id>/<channel-id>`，分支由 room/channel ID 派生。服务端在创建时读取当前 HEAD，请求不能指定提交，不提供预览和状态核验接口。
- 创建参数包含名称、描述及 `useWorktree`，默认 `false`。未勾选时沿用房间目录，不检查或执行 Git；勾选后创建并核对 worktree。
- 同 ID 同创建参数返回原频道，不再 Git add；异参数冲突。结果未知按 ID 查回，不生成新 ID 重试。
- 频道及初始资源通过现有请求事务一起提交，失败由切面回滚数据库写入；仓储只 flush，不独立提交中间状态。Git 产物不随数据库回滚自动删除，不接管现存目录或分支。
- 归档保留工作目录、分支和记录，无永久预留/释放管理功能；创建与归档互斥，submitting 进行中拒绝归档。调用 T01 的原子归档契约，冻结新操作，pending 软移出，queued/unknown 保留观察；默认频道仅随房间归档。
- 创建和归档必须使用 T01 的共享 guard，不能只锁 Git adapter 内部；Git 结果无法确认时返回错误，保留外部产物供人工检查，不自动重试。

## Implementation outline / 实施安排

1. 实现只读仓库检查、worktree 创建与无 shell 的 Git adapter。
2. 实现创建幂等、请求事务接线、Git 操作互斥、异常回滚和归档。
3. 用隔离临时仓库检查成功、冲突、故障和资源保留，交付明确服务契约给 T05。

## Checks and risks / 检查与风险

- `tests/unit` 验证参数、依赖接线与客户端请求；`tests/integration` 临时库和仓库验证真实 Git、当前 commit、dirty 源目录、路径/分支冲突、响应丢失和请求事务回滚，不修改现场仓库。
- Git 与数据库无法原子提交；无法确认所有权时仅报告并保留外部产物，不能调用强制删除。

## Handoff basis / 交接依据

- 未分配；协议入口 `C:/Users/leon/.codex/plugins/cache/specflow-local/specflow/0.2.1/skills/specflow/SKILL.md` 和 `references/task-coordination.md`。
- 总计划记录授权、基线与前置版本；执行者仅写本文接收及交付，主会话读取，默认输出可复制摘要。

## Reception and progress / 接收与进展

- 未接收。

## Delivery and review / 交付与审查

- 尚无交付；执行时记录实际版本、验证、未运行项及风险。
