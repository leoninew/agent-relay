# Task / 子任务 T06：Web 频道体验
最后修改时间: 2026-11-14 12:30:00

## Review status / 审查状态

Draft；前端契约骨架已实现并通过定向检查，业务验收未开始。

## Parent and authority / 父任务与权威记录

- [意图](../../intent/20261113-channels-worktrees.md)；[总计划](../../plan/20261113-channels-worktrees.md)，协调根 `D:\SourceCodes\mywork\agent-relay`，T06，修订 3。

## Goal and acceptance / 目标与验收

- A02、A03、A06、A08：用户可查看和切换频道，右侧详情只展示名称和描述；新建频道时提供 worktree 选项且默认不勾选，直接提交创建；频道的成员、话题、消息、队列及草稿不混杂。

## Scope and files / 范围与文件

- `web/src` 路由、API、store、频道导航、创建界面、i18n、草稿和事件订阅，以及必要前端测试；不改后端语义。

## Inputs / 输入

- T05 的 HTTP 频道 API 和错误契约；UI 提供创建、切换和详情。

## Technical decisions / 局部技术设计

- 路由显式携带 room/channel；旧 room 路由打开默认频道。切换时取消旧请求/事件，防止迟到响应覆盖新频道；选中项、详情、队列、搜索与能力按频道重置。
- 创建表单提供名称和描述，使用 Reka UI 提供默认未勾选的“创建 Worktree”选项；不提供预览或提交选择，直接提交一次创建请求。
- 点击频道在右侧显示名称和描述，复用话题、成员详情布局，不展示频道状态、时间或工作区；选择与新消息均不主动展开折叠面板。
- 草稿、待确认 publication、创建请求、本地缓存按 room/channel 区分；创建响应未知按原 ID 查回，不自动换 ID 创建第二份。归档保留 worktree、分支和历史。

## Implementation outline / 实施安排

1. 增加频道导航、默认频道使用旧 room 路由、非默认频道使用显式 channel 路由，以及频道范围的 API/service。
2. 增加名称、描述及可选 worktree 的创建表单，详情只显示名称和描述。
3. 隔离草稿、请求、事件与队列并补定向测试，准备实际浏览器验收路径。

## Checks and risks / 检查与风险

- 在 `web` 执行 `corepack pnpm typecheck`、`lint`、`test`、`build`；按现有脚本及受影响状态测试验证切换/迟到响应。
- 实际桌面与移动视口、worktree 创建对话和双频道路由在授权整体验证后以隔离环境检查。

## Handoff basis / 交接依据

- 未分配；协议入口 `C:/Users/leon/.codex/plugins/cache/specflow-local/specflow/0.2.1/skills/specflow/SKILL.md` 和 `references/task-coordination.md`。
- 总计划记录授权、基线与前置；本文记录接收/交付，主会话读取，默认输出可复制摘要。

## Reception and progress / 接收与进展

- 主会话按 2026-11-14 用户指示直接实现前端骨架，不视为 T06 正式分配或前置任务已接受。
- `web/src/domains/channel`、频道 API/store、room/channel 路由、草稿/发布/事件/侧栏排序均使用显式频道；worktree 创建选项默认未勾选。
- 定向检查：`typecheck`、`lint`、`vitest`（135 passed）通过；后端 501 契约下未执行真实频道或 worktree 操作。

## Delivery and review / 交付与审查

- 交付为前端契约骨架，不是 T06 业务完成。未执行真实浏览器视觉验收、非默认频道业务链路或 worktree 创建；这些仍需后端业务实现及用户整体验证授权。
