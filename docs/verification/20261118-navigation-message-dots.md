# 验证：聊天室与频道的新消息提醒
最后修改时间: 2026-11-18 17:25:05

## Review status / 审查状态

Accepted

## Intent alignment / 意图对齐

对照 [意图](../intent/20261118-navigation-message-dots.md) A01-A04：实现仅在非当前频道或非当前聊天室导航名称右侧呈现提醒；当前项不重复显示。#536 要求黄色，浅色主题渲染 `rgb(188, 142, 6)`，深色主题渲染 `rgb(251, 189, 35)`。提醒仅依据未删除、非本人消息；首次使用建立基线，查看位置保存在本浏览器。屏幕阅读描述、既有拖动手柄及名称省略样式保留。

## Plan alignment / 计划对齐

对照 [计划](../plan/20261118-navigation-message-dots.md)：新增只读批量频道消息摘要，没有迁移或正文传输；应用前台单一轮询，恢复前台立即查询；只有当前频道无筛选时间线已成功展示后，查看序号才前进。切换失败和后台不清除；投递及 WebSocket 链路未更改。默认频道由服务端摘要包含。

## Actual diff summary / 实际差异摘要

- 后端新增 DTO、查询端口与实现、路由 `GET /api/room/channel-message-heads`，按有效房间和频道返回最新非本人且未删除消息序号；空频道返回 0。
- 前端新增 `navigationActivity` Pinia store、前台轮询和 localStorage 查看位置；RoomSwitcher 聚合房间圆点，ChannelBar 显示单频道圆点。
- 时间线成功展示条件驱动查看位置，黄色提醒点适配亮暗主题，并提供“有新消息”无障碍描述。
- 新增数据库查询边界测试和 store 状态测试。无子任务，集成任务不适用。

## Expected vs actual changed files / 预期与实际修改文件对比

- 意图与计划预期的查询、导航、状态、样式和测试范围均已实现；新增本验证报告。无产品范围遗漏。
- 工作区本轮开始前已有与本功能无关的 `pyproject.toml`、`src/conflua/__init__.py`、`uv.lock`、`web/src/components/AppMenu.vue` 及英文/中文 AppMenu 文案修改。验证未将其纳入本功能，也未修改或回退它们；两份 i18n 文件同时承载了本功能 `navigation.newMessages` 文案。

## Acceptance criteria checklist / 验收标准检查清单

- A01：通过。无头 Edge 验证其他房间聚合圆点、当前房间非当前频道圆点、当前项抑制；浅色、深色的实际计算颜色均为黄色。
- A02：通过。store 测试覆盖初始基线、之后到达的新消息、频道独立位置及重载位置恢复；数据库测试覆盖本人消息、已删除消息、归档频道和房间隔离。
- A03：通过。无头 Edge 模拟频道 snapshot 503 后返回，圆点保留；成功展示时间线后只清除目标频道圆点。代码仅允许可见、无筛选、已成功加载且可见时间线引用存在时推进。
- A04：通过。圆点为固定 6px，不挤占拖动/菜单按钮；名称仍使用省略，导航链接的无障碍描述包含新消息状态。

## Test / command results / 测试 / 命令结果

- `uv run --locked pytest tests/unit -q`：511 passed。
- `uv run --locked mypy src tests`：224 source files，无问题。
- `uv run --locked ruff check .` 与 `uv run --locked ruff format --check .`：通过。
- `cd web && corepack pnpm test`：35 个文件、234 项测试通过。
- `cd web && corepack pnpm typecheck`、`corepack pnpm lint`、`corepack pnpm format`：全部通过。
- `cd web && corepack pnpm build`：Vite 生产构建成功。构建报告打包后 JS chunk 超过 500 kB 的既有性能提示；不影响本次构建结果。
- 无头 Edge + 本地开发服务：实际验证亮暗主题颜色、频道/房间显示、失败保留及成功清除；数据在隔离浏览器上下文中操作，未写入频道消息。
- `git diff --check`：通过。

## Missed or expanded scope / 遗漏或扩大的范围

无产品范围扩张。依赖本地轮询摘要，最多约五秒陈旧；没有压力测试大量房间和频道的查询成本。跨设备同步、精确未读计数、桌面通知均为意图明确的非目标。

## Risks / 风险

- 查看位置属于当前浏览器的 localStorage，清理浏览器数据会重置位置；不同设备间不共享。
- 单次摘要为每个有效频道计算最近消息，当前规模验证通过，极大频道数下的延迟尚未压测。
- 当前生产构建仍给出 JS chunk 大于 500 kB 的警告；代码分块不属于此次目标。

## Incomplete items / 未完成事项

无验收项未完成。高负载查询性能未测，按风险保留，不阻塞本次功能验收。

## Conclusion / 结论

通过。A01-A04 均有自动化、静态或无头浏览器证据；无未完成验收。建议提交前将本功能修改与工作区已有的无关修改分开检查和暂存。验证只读评估，没有暂存或提交。
