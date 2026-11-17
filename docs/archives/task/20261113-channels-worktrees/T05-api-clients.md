# Task / 子任务 T05：接口与协作客户端
最后修改时间: 2026-11-14 12:30:00

## Review status / 审查状态

Draft，未分配。

## Parent and authority / 父任务与权威记录

- [意图](../../intent/20261113-channels-worktrees.md)；[总计划](../../plan/20261113-channels-worktrees.md)，协调根 `D:\SourceCodes\mywork\agent-relay`，T05，修订 3。

## Goal and acceptance / 目标与验收

- A05、A06、A08：HTTP、CLI、MCP 和协作 skill 支持频道管理与显式频道作用域，移除旧资源入口。

## Scope and files / 范围与文件

- `interfaces/http` 路由与 DTO、`interfaces/client.py`、CLI、MCP、插件 skill 和接口测试；协调主会话接线与共享 DTO，Web 交由 T06。

## Inputs / 输入

- T02、T03、T04 提供 worktree 创建、频道资源查询、会话和投递契约。

## Technical decisions / 局部技术设计

- REST 前缀 `/api/room/{room_id}/channel`：GET 列表、POST 创建（channelId/name/description/useWorktree）、GET `/{channel_id}` 查回结果、DELETE `/{channel_id}` 归档。`useWorktree` 默认 `false`，未勾选时不执行 Git；请求不接受基准提交，服务端自动取当前 HEAD。不公开频道状态、预览或核验接口。
- 创建、归档通过现有请求事务切面提交；错误响应沿用项目统一契约。归档频道退出活动列表，按 ID 保留历史查询。
- MCP/CLI 频道资源工具必填 channel_id；带会话上下文的调用先验证目标频道绑定，省略频道直接拒绝，无副作用。房间/频道发现工具只返回定位必要元数据。身份按 room/channel/threadId 解析，publication 同作用域。
- 创建相同 ID/参数返回原结果，异参数冲突；响应未知通过 GET 查回。POST 的幂等语义必须写入 CLI/MCP 描述和 UI；不能继承通用重试逻辑再次 Git add。
- capability、图片、队列和事件均使用显式频道契约，输出包含频道信息。跨频道 ID 不得隐式回退，客户端和插件统一升级。

## Implementation outline / 实施安排

1. 接线新旧路由及 DTO，覆盖名称描述、创建、事务失败和默认映射。
2. 实现 CLI/MCP 参数、身份解析与说明，更新 skill 的消息上下文和示例。
3. 以接口替身与临时库验证旧调用、新调用、非法 ID、位置、队列及事件；交付 Web 契约。

## Checks and risks / 检查与风险

- `uv run --locked pytest tests/unit/interfaces tests/unit/application/test_request_contracts.py`，检查显式频道契约及旧入口拒绝。
- 更新 skill/MCP instructions，验证所有频道资源工具省略频道参数均被拒绝。

## Handoff basis / 交接依据

- 未分配；协议入口 `C:/Users/leon/.codex/plugins/cache/specflow-local/specflow/0.2.1/skills/specflow/SKILL.md` 和 `references/task-coordination.md`。
- 总计划提供授权、基线、前置与仲裁；本文为接收和交付位置，主会话读取，默认输出可复制摘要。

## Reception and progress / 接收与进展

- 未接收。

## Delivery and review / 交付与审查

- 尚无交付；执行时填写检查、版本、未验证项与风险。
