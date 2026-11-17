# Task T03：实时消息筛选与活动更新
最后修改时间: 2026-11-17 16:37:50

## 方案与权威记录

Accepted；父意图和权威计划为 docs/intent/20261117-query-scoping.md、docs/plan/20261117-query-scoping.md，方案修订 1。当前未分配，前置版本及授权以总计划为准。

## 目标与局部设计

A04：新增限定变更 ID 的批量读取，话题/成员/关键词在 SQL 应用；已显示和详情使用的变更 ID 单独保留，避免状态更新遗漏。活动读取仅包含汇总、位置和事件版本，资源事件使用完整 metadata。前端保留当前查询代次、取消、分页和详情行为。

## 范围与检查

修改消息/房间 DTO、ports、queries、repository、HTTP routes、roomApi、RoomPage 事件同步、stores/rooms 及相关测试。仅在 T02 已接受契约上工作，保留 0415 确认的缓存区域。覆盖 SQL 组合筛选、ID 范围、旧消息/详情保留、资源与活动更新版本；运行相关后端和前端测试、类型与格式检查。不做迁移。

## 接收与进展

2026-11-17 16:24:09 架构师接收 QS-T03-20261117-01，方案 1，用户 0413 和 go on 授权的 Implementation；核对 T02 已接受工作区与查询契约，95 项测试及 Mypy 通过。前端缓存最终交付 0416 已确认，保留 cacheKeys 调用；本文由本会话维护。

## 交付与审查

2026-11-17 16:37:50 架构师交付 QS-T03-20261117-01，方案 1，前置为 T02 当前已接受工作区版本。

- A04：新增 POST /message/updates，限定本批最多 200 个消息 ID，在 SQL 应用话题、成员、关键词交集；retainedIds 仅能保留本批且当前频道未删除消息。前端将已展示消息、详情和回复目标纳入保留集合，每批一次请求，替代逐个消息请求。
- 活动读取 GET /activity 只返回 summary、positions、eventId；消息/投递/位置事件使用活动读取，room/topic/member/session 事件仍取完整 metadata。资源和活动维护独立版本，避免活动响应阻止较早但必要的资源响应，或旧资源响应覆盖较新统计。
- 保留分页、查询取消、事件游标、错误重连和历史详情；不修改既有 cacheKeys 调用。
- 新增 SQL 范围测试、HTTP 批量/上限/活动响应测试、前端请求次数和版本合并测试；同步中断与模型接口测试的 member mock。共享 raw_project_path 改动已保留，未新增/恢复迁移测试。

开发检查（仓库根目录，前端命令在 web）：

| 命令 / 检查 | 结果 |
| --- | --- |
| uv run --locked --no-sync pytest tests/unit -q | 452 passed |
| uv run --locked --no-sync mypy src tests | 208 source files 通过 |
| uv run --locked --no-sync ruff check src tests | 通过 |
| Ruff 改动范围 format --check | 35 files already formatted |
| corepack.cmd pnpm test | 31 文件、214 项通过 |
| corepack.cmd pnpm typecheck | 通过 |
| ESLint / Prettier 七个改动前端文件 | 通过 |
| git diff --check | 通过 |
| 开发服务 HTTP 只读实测 | activity 无完整资源；无匹配关键词返回空；retained 消息仍返回；会话均有关联成员 |
| 本机 Codex 只读实测 | 当前频道请求 3 个绑定，返回 3 个连接会话，未返回其他会话 |

开发服务检查使用 Python 标准库 urllib；初次探测因 httpx 不存在未运行，随后按原生 HTTP 响应结构修正探测脚本完成，未安装依赖。未执行真实清空、投递或中断等写操作，未进行浏览器交互与耗时压测。

交付为 d74f846 加共享工作区的当前源码及测试 diff；本任务不包含其他人的频道归档、缓存和原始路径持久化修改。主会话核对实际实现、失败后的回归修正和上述证据，接受交付。A04/A05 满足，无未完成实现项；尚未进入单独的整体 Verification。
