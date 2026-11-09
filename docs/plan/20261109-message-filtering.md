# 计划：统一话题与成员消息筛选
最后修改时间: 2026-11-09 16:59:54

## 审查状态

Accepted

## 意图依据与授权

依据 [意图](../intent/20261109-message-filtering.md) A01–A05。用户已授权记录后实施，并追加 checkbox 联动要求，覆盖必要开发检查；本次不额外进入独立的整体 Verification 阶段。

## 技术设计与约束

- 后端 `RoomQueries._page` 删除话题条件中接收者为 `user` 的 OR 分支，严格匹配 `topic_ids`。
- 成员条件改为 `(publisher_id = M OR recipient_ids 包含 M)`，用 `EXISTS` 查询 JSON 数组，避免多接收者或同时命中发送与接收时重复消息。
- 所有启用的条件以 AND 组合，复用于分页查询和 `hasNewer` 探测；不修改 API 参数或数据库结构。
- 前端 `rooms.applyMessages` 同步采用严格话题匹配和发送者/接收者匹配。已加载消息继续更新，历史窗口不追加越过窗口的新消息。
- 页面维持已有选择行为：话题和成员可组合，点击全部消息清除两者，再次点击成员取消该条件。增加交互回归，不改变发布和引用导航。
- checkbox 联动通过房间草稿模型实现：`RoomComposer` 使用 `v-model:draft`，侧栏操作更新当前草稿的路由，保留正文；全部消息设置两组空数组。输入区继续支持手动多选。组件内一次更新完整草稿，避免连续字段更新丢失内容；待确认请求锁定期间不改写草稿路由。
- 历史意图和计划保留原始决策；本次意图取代旧固定用户任务中“发给用户的消息豁免话题筛选”的规则。

## 实施步骤与预期文件

1. 记录意图、计划，按授权进入实施。
2. 修改 `src/agent_relay/room_queries.py` 与 `web/src/stores/rooms.ts` 的过滤谓词。
3. 更新 `tests/test_room_queries.py` 的组合分页预期，增加话题、发送/接收、固定用户及空结果检查。
4. 更新 `web/tests/stores/rooms.test.ts`，覆盖实时新增、组合筛选和历史窗口；在 `web/tests/domains/room/RoomPage.test.ts` 覆盖选择和取消选择。
5. 执行必要开发检查，复核正在运行的页面和 API，记录结果及实际偏差。
6. 按追加要求修改 `RoomPage.vue` 和 `RoomComposer.vue` 的草稿绑定与筛选联动，更新二者相关测试并运行前端开发检查。

## 子任务与协调

不适用；当前会话实施单任务，不派发其他会话，不进行 Git 暂存或提交。

## 开发检查

- 后端：现有 pytest 的 room_queries、room_api、user_members 回归，Ruff、mypy。
- 前端：现有 Vitest 的 rooms store、RoomPage 回归，typecheck、ESLint、Prettier。
- 正在运行的开发服务：只读核对严格话题、成员收发和组合筛选；不新建消息或向真实 Codex 会话投递测试。
- `git diff --check`；不新增迁移测试，不更换运行环境或重启开发服务器。

## 风险与回滚

成员查询结果会按用户要求扩展，已有只统计发送者的测试预期必须更新。真实页面中的话题消息可能较少，以既有测试夹具补足分页和接收场景。没有数据写入或 schema 迁移，回滚仅撤销本任务新增差异，保留此前成员改名和界面修改。

## 实施记录

2026-11-09 16:43:27：意图和计划按用户授权记录并接受，进入 Implementation。结果在必要开发检查完成后补充。

2026-11-09 16:51:02：实现及必要开发检查完成。

- 实际产品改动仅涉及 `room_queries.py` 与 `web/src/stores/rooms.ts`；另修改计划中的三个测试文件，范围符合预期。
- 话题严格匹配显式话题；成员按发送者或 `recipientIds` 匹配；组合条件在后端分页、更新消息探测和前端实时追加中一致。
- 查询回归覆盖直接接收、话题订阅解析的接收、固定用户收发、无话题消息、空交集、分页及全房间统计；页面回归覆盖切换话题、保留/取消成员条件和全部消息重置。
- 保留原有成员改名、消息布局及其他工作区改动，没有修改 README、schema、运行环境或 Agent 上下文规则，无范围偏差。

## 开发检查结果

| 检查 | 结果 |
| --- | --- |
| 根目录 `uv run --locked pytest tests/test_room_queries.py tests/test_room_api.py tests/test_user_members.py -q` | 32 项通过 |
| web 下 `corepack pnpm --config.engine-strict=false test tests/stores/rooms.test.ts tests/domains/room/RoomPage.test.ts` | 14 项通过 |
| web 下同一 pnpm 入口的 `typecheck` | 通过 |
| web 下同一 pnpm 入口的 `exec eslint src/stores/rooms.ts tests/stores/rooms.test.ts tests/domains/room/RoomPage.test.ts` | 通过 |
| web 下同一 pnpm 入口的 `exec prettier --check src/stores/rooms.ts tests/stores/rooms.test.ts tests/domains/room/RoomPage.test.ts` | 通过 |
| 根目录 `uv run --locked ruff check src/agent_relay/room_queries.py tests/test_room_queries.py` 与对应 `ruff format --check` | 通过 |
| 根目录 `uv run --locked mypy src/agent_relay/room_queries.py tests/test_room_queries.py` | 通过 |
| `git diff --check` | 通过 |
| 正在运行的 API 与浏览器 | 全部消息、话题、成员、固定用户及组合查询与规则一致；页面只显示前端话题消息，叠加后端成员得到空状态，点击全部消息后两项选择均清除。仅读取现有消息并切换筛选，没有发送测试消息 |

## 交付边界

必要开发检查均通过，没有已知未完成的实现项。未运行无关的完整后端/前端套件，未新建独立整体验证报告，未进入整体 Verification 阶段，未进行 Git 暂存或提交。

## 追加实施

2026-11-09 16:55:31：按用户补充的 A05 进入 checkbox 联动实现，覆盖发送区草稿模型、侧栏操作和相关回归。

2026-11-09 16:59:54：A05 实现及必要开发检查完成。

- `RoomPage` 在侧栏操作时把当前话题、可发送的 Agent 成员写入房间草稿；全部消息清空两组 ID，保留正文。`RoomComposer` 使用草稿双向绑定，手动多选、回复路由及发送后重置通过同一模型更新。
- 更新页面回归，覆盖话题替换、成员联动/取消、组合选择、全部消息清空、正文保留、手动路由调整和按联动后的路由发布；原有回复、字段校验、失败草稿及发布编号恢复继续通过。
- web 下 `corepack pnpm --config.engine-strict=false test tests/domains/room/RoomComposer.test.ts tests/domains/room/RoomPage.test.ts`：16 项通过。相同 pnpm 入口的 `typecheck`、相关文件 ESLint 与 Prettier 全部通过，`git diff --check` 通过。
- 浏览器实测：选前端话题后勾选对应话题，叠加后端成员后两者均选中，点击全部消息后两组为空，正文保持；未发送真实测试消息。
- 本次追加仅涉及前端与已有任务记录，不重复运行此前已通过的后端检查；无已知未完成实现项，未暂存或提交。
