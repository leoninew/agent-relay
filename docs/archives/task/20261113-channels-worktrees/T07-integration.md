# Task / 子任务 T07：集成与交付检查
最后修改时间: 2026-11-14 12:30:00

## Review status / 审查状态

Draft，未分配。

## Parent and authority / 父任务与权威记录

- [意图](../../intent/20261113-channels-worktrees.md)；[总计划](../../plan/20261113-channels-worktrees.md)，协调根 `D:\SourceCodes\mywork\agent-relay`，T07，修订 3。

## Goal and acceptance / 目标与验收

- A01–A08：集成已接受交付，逐项对照验收和频道隔离约束，运行必要开发检查并准备整体验证材料。

## Scope and files / 范围与文件

- 主会话复核各任务已随交付完成的接线与跨层契约，更新 README、迁移指南及现行设计；不把未设计的接线和功能留到本节点兜底。真实整体验证获授权后另按阶段执行。

## Inputs / 输入

- T02、T03、T04、T05、T06 已接受且其前置版本及检查证据均可访问；逐个核对有效版本与集成基线。

## Technical decisions / 局部技术设计

- 按总计划核对 SQLite 迁移、频道边界、真实 worktree、旧客户端默认映射、插件更新、桌面通知与队列回执。不得以 mock 代替真实 Git 或迁移结果，也不得把服务保存等同目标会话接收。
- 恢复说明区分数据库回滚与外部 Codex 输入不可撤回，旧备份不得直接恢复成可投递 pending；优先前滚，旧版本恢复前必须停投递并对账。记录归档停止新输入但保留 queued/unknown 观察，及创建同 ID 不重复 Git add 的端到端证据。

## Implementation outline / 实施安排

1. 集成每个 accepted 版本，检查共享文件改动及跨任务契约；发现缺口交回相应节点或按授权安排修复。
2. 运行项目既有开发检查和临时库/仓库回归，按 A01–A08 记录证据与未覆盖项。
3. 整理版本、限制、风险及实际验证前置条件；无整体验证授权时停止在实施交付。

## Checks and risks / 检查与风险

- `make check`、`make test`，另显式执行 `uv run --locked pytest tests/integration`；临时 Git、全表迁移及回滚不能由 mock 或本次简化 SQLite 探针替代。所有证据关联最终集成版本。
- 独立真实服务、专用 Codex 会话和浏览器验收属于后续 Verification，不得提前声称通过；不操作用户数据库和工作会话。

## Handoff basis / 交接依据

- 未分配；协议入口 `C:/Users/leon/.codex/plugins/cache/specflow-local/specflow/0.2.1/skills/specflow/SKILL.md` 和 `references/task-coordination.md`。
- 总计划记录授权、基线、前置和仲裁；本文记录接收/交付，主会话读取，默认输出可复制摘要。

## Reception and progress / 接收与进展

- 未接收。

## Delivery and review / 交付与审查

- 尚无交付；执行时记录所有验收证据、实际版本、检查与未完成风险。
