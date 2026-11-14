# Task / 子任务 T03：频道资源与消息隔离
最后修改时间: 2026-11-14 12:30:00

## Review status / 审查状态

Draft，未分配。

## Parent and authority / 父任务与权威记录

- [意图](../../intent/20261113-channels-worktrees.md)；[总计划](../../plan/20261113-channels-worktrees.md)，协调根 `D:\SourceCodes\mywork\agent-relay`，T03，修订 3。

## Goal and acceptance / 目标与验收

- A03、A05、A07、A08：频道级话题、成员、订阅、消息、引用、查询、队列、事件、图片及清理完整隔离；所有频道使用统一接口。

## Scope and files / 范围与文件

- rooms/messages/context 领域与 application、图片存储/输出及相关测试；消费 T01 已按频道隔离的仓储，不重做公共持久化。存储缺陷回交 T01 串行修复；与 T02 仅共享已固定契约。

## Inputs / 输入

- T01 已接受的频道复合键、作用域仓储、归档端口和迁移版本；沿用房间全局 seq 与现有接收快照。

## Technical decisions / 局部技术设计

- 所有查询和写入以 room/channel 显式作用域约束；发送时过滤话题订阅与 @，校验引用和目标均同频道，成员上下文只读取本频道内自身、实际接收和订阅可见消息。
- 全局 seq 保持原规则；分页、消息数量和位置按频道过滤。事件用全局 ID，但只查询本频道及不包含其他频道内容的房间元数据事件，游标合法性按 room 检查；clear 的 resync 只影响所属频道，房间归档影响全部。snapshot 与其初始 eventId 在同一读快照中产生，避免漏掉夹在两次读取间的消息。
- 队列/消息清空仅作用于频道，外部回执语义保持；房间归档委托 T01 原子存储契约。图片与正文 URL 解析同步带频道，默认频道使用相同目录结构；路径不存在不能向其他频道、房间或旧目录回退。

## Implementation outline / 实施安排

1. 更新资源、消息及关系写入，覆盖接收人解析、幂等与引用边界。
2. 在应用内部显式传频道，更新 positions、事件、队列、附件与归档入口，提供 T04/T05 服务契约。
3. 使用双频道样例验证同名资源和恶意跨频道 ID，确认默认频道旧数据。

## Checks and risks / 检查与风险

- `uv run --locked pytest tests/unit/domain tests/unit/application/test_message_service.py tests/unit/application/test_context_provision.py tests/unit/infrastructure/persistence`，按实际改动补充隔离用例。
- 并发发布、snapshot/事件间隙和归档竞争在 `tests/integration` 验证；图片禁止跨频道读取。

## Handoff basis / 交接依据

- 未分配；协议入口 `C:/Users/leon/.codex/plugins/cache/specflow-local/specflow/0.2.1/skills/specflow/SKILL.md` 和 `references/task-coordination.md`。
- 总计划记录授权、基线和前置；本文为接收和交付位置，主会话读取，默认输出可复制摘要。

## Reception and progress / 接收与进展

- 未接收。

## Delivery and review / 交付与审查

- 尚无交付；执行时记录验收、版本、检查及风险。
