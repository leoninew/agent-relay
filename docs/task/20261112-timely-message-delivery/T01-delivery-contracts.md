# Task / 子任务 T01：投递契约与存储
最后修改时间: 2026-11-12 10:13:33

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[提高消息投递时效](../../intent/20261112-timely-message-delivery.md)。
- 权威总计划：[Plan](../../plan/20261112-timely-message-delivery.md)，协调根 `D:\SourceCodes\mywork\agent-relay`；T01，方案修订 1。
- 本窗口执行，编号 `TIMELY-T01-01`；授权来源为用户“开始实现”。

## Goal and acceptance / 目标与验收

建立不混淆 queue 与 steer 的提交事实，交付后续可直接使用的 typed outcome、领域转换和兼容存储，对应 A02、A03、A06、A08。

- 旧 queue 回执往返不变；steer 不能伪装队列 ID 或历史接收。
- 新字段、状态语义、mapper 和数据库约束一致；旧数据前滚兼容，历史积压不重投。
- 激活与原生队列删除明确排除 steer。

## Scope and files / 范围与文件

- `src/agent_relay/application/delivery/ports.py`。
- `src/agent_relay/domain/rooms/models.py`、`delivery.py`。
- `src/agent_relay/infrastructure/persistence/models.py`、`mappers.py`、`repositories/deliveries.py`、`repositories/messages.py` 及必要的 store 转发。
- `migrations/sqlite/versions/0003_delivery_steering.py`、对应 SQL、`MIGRATION_HEAD`、`migrations/README.md`。
- `tests/unit/domain/test_delivery.py`、`tests/unit/infrastructure/test_persistence_records.py` 及必要的单层查询契约检查。
- 不修改 driver、delivery service、runner、web 或旧迁移；共享文件由本任务独占。

## Inputs / 输入

无直接前置任务。按总计划修订 1 第 3 节实现固定接口，不将字段或回执选择留给下游。派发时记录实际 HEAD、用户改动和可用基线。

## Technical decisions / 局部技术设计

- 保留 `QueueRequest/QueueReceipt/QueueDriver`，新增 `SteerReceipt(turn_id)`、提交结果联合、带 method 的 `SubmissionRejected/SubmissionUnknown`、扩展 `QueueDriver` 的 `DeliveryDriver.submit`；旧调用方仍可检查通过。
- 模型新增 `submission_method: Literal[queue, steer] | None`、`steered_turn_id: str | None`，API 自动 camelCase。新增 steer 接纳领域转换，状态仍为 queued；只填 steer 事实与 note，不填 queue 专有字段和任何 received 事实。
- queue 接纳转换记录 method=queue；未知/拒绝转换可保留 method，启动恢复仍 unknown、不重发。精确历史确认独立于提交方法。
- mapper 保持现有 queue receipt 双 ID 校验；支持无 queue receipt 的 steer 往返，拒绝相互矛盾的事实。数据库与模型限制 steer 的队列专有列为空、非空 steer turn ID 只能归属 steer。
- 新 revision `delivery_steer_20261112` 接 `capabilities_json_20261111`，SQL-first 添加可空两列；旧非 pending 数据回填 queue，旧 pending 不选择方法。不改已交付迁移，不对运行库执行迁移。
- `claim_activation` 排除 steer；`codex_queue_targets` 排除已知 steer。未知方法但没有队列凭证的记录仍只能计为无凭证，不能发原生 delete。清空本地待办沿用软删，不宣称撤回外部输入。

## Implementation outline / 实施安排

1. 增加端口及领域事实、转换和防矛盾约束，保持原 queue 路径兼容。
2. 同步持久化字段/mapper 与激活/删除过滤；外部 RPC 不进入事务。
3. 增加前滚迁移、head 和指南；离线检查旧记录回填及约束。
4. 完成领域/mapper 单测，向 T02/T04 交付可访问的接口与 wire 字段版本。

## Checks and risks / 检查与风险

- `uv run --locked pytest tests/unit/domain/test_delivery.py tests/unit/infrastructure/test_persistence_records.py`；新增用例只用领域/ORM 对象，不创建 SQLite。
- `uv run --locked alembic history`、`uv run --locked alembic heads`、`uv run --locked alembic upgrade capabilities_json_20261111:head --sql`。
- 检查 steer queued/unknown/received 往返、旧 queue receipt 校验、冲突事实拒绝和精确删除/激活过滤；mypy/Ruff 按修改范围检查。
- 离线 SQL 不证明运行库迁移已完成；明确记录此限度，不能顺手修复开发库或恢复已删除测试支持目录。

## Handoff basis / 交接依据

- 本窗口，`TIMELY-T01-01`；用户“开始实现”授权本任务实施及必要开发检查。
- 协议入口：`C:/Users/leon/.codex/plugins/cache/specflow-local/specflow/0.2.1/skills/specflow/SKILL.md` 及其 `references/task-coordination.md`。
- 授权、依赖及基线以权威总计划为准；派发时补实际版本。
- 可写回报位置：本文“接收与进展 / 交付与审查”；主会话直接读取。默认在执行会话输出可复制摘要，由用户转交，不发送协作消息。

## Reception and progress / 接收与进展

2026-11-12 09:30:21 本窗口接收 `TIMELY-T01-01`，方案修订 1；已核对用户“开始实现”授权，无直接前置，基线 `a5c0609`，仅有本功能未跟踪文档，产品文件无用户改动。

| 时间 | 分配编号 / 执行者 | 接收、进展或阻塞 | 证据 / 回报位置 |
| --- | --- | --- | --- |
| 2026-11-12 09:30:21 | TIMELY-T01-01 / 本窗口 | 已接收，开始实现契约与存储 | 当前工作区及权威总计划 |
| 2026-11-12 09:42:00 | TIMELY-T01-01 / 本窗口 | 实施审查返修：unknown 后的历史确证不要求提交响应 | 领域/SQL 约束及 mapper 回归用例 |
| 2026-11-12 09:44:20 | TIMELY-T01-01 / 本窗口 | 修复检查及复核接受，下游兼容复核通过 | 最终 222 单测及更新离线 SQL |

## Delivery and review / 交付与审查

- 2026-11-12 10:13 整体验证复核：产品交付未变；独立旧版数据库 6 条记录前滚保留原字段，5 条非 pending 回填 queue、pending 留空，5 类非法组合被数据库拒绝。真实投递事实往返和清空边界通过；见[验证记录](../../verification/20261112-timely-message-delivery.md)。下方保留 Implementation 历史交付事实。

- 交付：2026-11-12 09:33，本窗口，`TIMELY-T01-01`，修订 1，当前工作区 diff；前置无，基线 `a5c0609`。
- 实际变更：typed outcome 与方法异常、领域/mapper 防矛盾约束、两列前滚迁移、新 head、queue-only 激活/删除过滤。QueueReceipt 另加可选 note 供降级原因保存，原构造兼容。
- 验收：A02/A03 未知方法与 steer 接纳不冒充历史接收；A06 独立队列事实及前滚 SQL；A08 单层检查。21 项领域/mapper 单测通过，mypy src tests（137 files）及定向 Ruff 通过；离线 SQL 与 head 通过。
- 修复：定向检查发现测试链式 identity 比较及两处行宽，已修复复验通过。
- 版本：ports SHA-256 `20f472debc23ce6e1bd5919d0da0e7eb8e68dd2b28c9b6b61295ede0f3b09b02`；交付位置为本共享工作区，不创建提交。
- 未运行：真实 SQLite、运行库迁移及外部会话操作；保持用户测试边界。主会话审查接受，放行 T02/T04。
- 09:42 实施复核发现 unknown steer 被历史确证时可能没有响应 turn ID，已修正领域/SQL 约束：received 依历史证据成立，steered_turn_id 允许空；补充单层往返回归。此修复落实原 A03，不改变依赖或验收范围。
- 最终检查：222 全量单测、mypy/Ruff 与格式、更新后的离线 SQL/history/head 均通过。运行库仍未操作；需按项目正式入口升级。09:44 主会话复核接受并确认 T02/T03/T04 兼容。
