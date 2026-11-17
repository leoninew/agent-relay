# Plan / 计划：右侧消息队列面板
最后修改时间: 2026-11-10 22:46:28

## Review status / 审查状态

Accepted

## Intent basis / 意图依据

- [已接受意图](../intent/20261110-message-queue-panel.md)，A01–A16。最新规则以下方当前技术方案为准，原有交付节保留历史证据。
- 基线：b24fb5a，工作区初始无修改。授权：用户要求记录任务并开始实现，遵循现有设计。

## Technical decisions / 技术设计与决策

- 原聊天分页默认最近 50 条，不能充当队列。只读 `GET /api/room/{roomId}/queue` 以 `EXISTS deliveries.status IN ('pending', 'submitting', 'queued')` 在分页前筛选，保留完整 Message 及投递字段。队列由当前详情目标确定范围，独立于聊天搜索及当前聊天页。
- 队列响应包含 messages、totalMessages、hasMore、nextBeforeSeq；接受 before_seq 与 limit（默认 50，最大 200）。按消息 seq 降序展示，用严格小于上页最后 seq 的条件向更早消息分页；统计匹配消息数而非投递数。同步本轮未发布的前后端新增契约，不保留反向语义的 after_seq 别名。totalMessages仅供分页与按钮控制，不在队列标题展示。
- 队列接受可选 topic_id/member_id，复用聊天查询的显式消息话题和发送者或已解析接收者条件；组合参数取交集。查询和总数使用相同范围及活动条件，before_seq 只作用于当前页。不存在或不属于当前房间的资源返回既有 404。
- 前端 API 和队列 composable 维护独立列表、数量、游标、加载和错误；刷新保留已展开的列表容量，切换房间、详情范围或新请求使旧响应失效。消息详情不传范围，话题详情仅传话题 ID，成员详情仅传成员 ID，不叠加另一侧栏筛选；范围变化重置列表与分页。
- 复用既有 message/delivery 事件触发队列刷新；重同步和房间重新加载同样刷新队列。队列刷新失败保留已有内容并提供重试，不解释为空队列。
- useRoomPanel 接收当前消息列表 getter，明确选择仅为可空的 message/topic/member；为空时由 computed 派生列表最后消息。关闭清除明确选择，上方详情始终挂载。统一 selectSidebar 更新两维筛选与明确选择并返回是否发生筛选变化；RoomPage 只在变化时同步输入区、加载和滚动。不保存 latest/closed 对象、不在请求后恢复面板、不通过实时回调替换显式消息。显式消息直接持有对象，接收或重新加载仅更新同 ID；发布成功沿用显示发送消息入口。
- MessageQueue 使用“消息/状态”两列表格，正文按 Unicode 字符取前15个，超过才加省略号，悬停显示全文；MessageDetails成员投递表为“名称/状态”。共享阶段计算忽略deletedAt记录，全部已接收显示已接收，均已入队但尚未全接收显示接收中，否则显示入队中；混合消息按最早未完成阶段展示。旧入队/接收 x/y 计算及表头已移除。
- 队列选择入口先复用selectMessage显示详情，再调用时间线已有scrollToMessage；该方法仅查找已渲染消息节点并居中滚动/聚焦，无节点时无操作。主列表点击继续使用原入口，不增加滚动副作用；不请求额外消息或改变筛选。
- 保留现有桌面三列宽度与分隔线；MessageDetails 始终挂载，MessageQueue 通过详情下级内容挂载，取消右列底部常驻区域。各类详情均有队列小节，消息详情全房间、资源详情限定对应资源。小屏沿用统一详情抽屉与收起入口。
- 两个全部入口放在 VueDraggable 外，复用 sidebar-node-fixed 的缩进与既有图标。selectedTopicId/selectedMemberId 为 undefined 时表示对应全部并选中该入口；选择具体项直接赋值，不进行第二次点击反选。全部入口只清除自身筛选维度；双全部或当前详情对应维度清除时回到默认派生消息，其余明确选择保持。不创建虚拟 ID，也不改变原有输入区的真实路由校验。
- 20:22 筛选触发补充：RoomPage 先处理详情展示，再比较所选 ID；同一 ID（包括 undefined 的全部项）直接结束，不同步输入区路由、不请求消息或队列、不滚动聊天。ID 实际变化才更新该维度并执行原有加载流程；搜索、分页、实时数据更新继续使用当前筛选参数。
- 双全部入口通过统一 selectSidebar 清除明确选择；重复选择返回 false，不触发重新请求、输入区同步或滚动。默认详情始终由当前列表派生，消除 restoreAllMessageDetails/showLatestMessage 等请求后补偿。
- 20:49 消息摘要删除：删除 MessageDetails 消息分支顶部的发送者、创建时间和正文摘要，以及仅其使用的计算字段、格式化导入和 CSS。消息详情从话题开始，首个详情小节不再增加前置小节间距。移除测试中已失效的正文展示断言，保留话题、成员及分发状态的有效断言。
- 标题操作布局：话题/成员的编辑、删除使用同一个 detail-heading-actions 类，按钮间 gap 8px，与标题 gap 12px，flex baseline 对齐；保留既有字体和状态，不使用相对定位或像素位移。
- 最新展示统一：右侧二级小节共用标题/正文/空态样式，不加小节分隔线；“队列”隐藏数量，刷新右侧增加清空按钮。空队列同其他无数据内容对齐，不再居中使用独立风格。
- 消息详情移除独立 @成员小节和孤立计算，投递表标题改“成员”；不显示人为删除文案，保留底层真实状态、时间与回执数据。
- 清空为 `DELETE /api/room/{roomId}/queue?topic_id=...&member_id=...`，返回 `{removedMessages}`。按当前详情范围在单一写事务处理全部活动消息，不受分页影响；复用资源范围校验，写入每条未完成投递的 deleted_at 和 updated_at，保留状态及回执等事实，记录 delivery 事件。原消息和已接收投递保留，重复清空返回0。
- Delivery 新增可空 deleted_at（前端 deletedAt），通过增量 SQL 迁移添加字段，不改写已有基线。队列、后台待提交/激活/核验与状态汇总排除人为删除记录；完成回写不能清除标记。清空端点不依赖 QueueDriver，不调用 Codex；正在执行的外部请求不尝试取消，回写失败后不启动后续激活。
- 迁移只在临时测试数据库验证；用户自行管理现有数据库和服务，本会话不迁移真实开发库、不启动或重启服务。最终交付注明升级命令及由此造成的页面检查限制。

## Implementation steps / 实施步骤

1. 增加队列只读契约、查询和 HTTP 接口，验证全房间筛选、去重、游标和数量（A02、A03）。
2. 增加前端队列 API、数据与面板状态、列表组件及必要轻量单测（A01–A05）。
3. 接入 RoomPage、既有实时事件及响应式布局，保留发布消息详情入口，默认消息由当前列表派生（A01、A04、A05）。
4. 运行后端及前端相关测试和既有质量检查，审阅 diff，将实际交付证据写入本计划（A06）。
5. 在 TopicSidebar、MemberPanel 增加固定全部入口，将 RoomPage 筛选改为直接选择；更新现有轻量组件测试和前端检查（A07、A08）。
6. 按补充要求为 RoomPage 两个选择处理函数增加相同选项短路，保留详情操作；通过页面请求与滚动检查核对实际切换和重复点击，再运行相关前端单测及质量检查（A08）。
7. 历史右列分区交付已完成；最终详情状态以第 10 步为准，最新内嵌队列以第 12 步为准（A01、A04、A05）。
8. 补双全部入口恢复消息详情及空结果处理；在面板状态层补轻量测试，复核重复点击短路和加载后结果选择，回报产品经理进行针对性集成检查（A09）。
9. 按截图删除消息详情摘要，清理孤立样式、计算字段和失效测试断言，检查相关组件测试与前端质量入口（A10）。
10. 按最终规则收敛可空明确选择和默认派生状态，清理旧方法/属性/测试；统一两类标题操作布局（A01、A04、A09、A11）。
11. 扩展队列活动状态和降序游标，前后端契约同步；由产品经理完成三列表格与计数展示，联合完成相关查询、API、分页和组件检查（A02、A03、A05）。
12. 按最新截图统一已完成进度；增加队列资源范围查询和轻量测试；产品经理把队列嵌入各类详情并按详情目标切换范围，完成必要检查与已有 tab 页面检查（A05、A12）。
13. 统一二级样式、空态和队列标题/操作；实现范围清空的人为删除标记、增量迁移和后台排除，检查清空范围/分页/幂等/留存/事件及旧回写不覆盖标记（A13、A14）。
14. 按最新补充合并右侧入队/接收为状态列，抽取共享阶段计算，清理数值进度和独立 @成员小节的旧计算/样式/测试，完成最终针对性检查及已有tab页面检查（A05、A15）。
15. 队列选择接入既有时间线定位，使用已有组件检查；仅在已有队列含消息时尝试页面定位确认，不发布测试消息（A16）。

## Files to change / 修改范围

- `application/rooms/contracts.py`、`ports.py`、`infrastructure/persistence/queries.py`、`interfaces/http/rooms/routes.py`。
- `web/src/services/roomApi.ts`、`web/src/domains/room/RoomPage.vue`、`room.css` 及新增队列和面板状态模块。
- 追加范围：`TopicSidebar.vue`、`MemberPanel.vue` 及其既有组件测试；不涉及后端变更。
- 相关后端查询、前端组件、API 和状态测试，以及本功能的意图、计划、验证记录。

## Tasks and coordination / 子任务与协调

不建立独立 task。原队列由当前会话完成，在本计划记录进展和实现交付；通过 Agent Relay 向用户同步实质进展与完成情况。

20:13 追加范围协作：产品经理已在消息 0008 先行认领侧栏实现；消息 0010 明确由产品经理修改 TopicSidebar、MemberPanel、RoomPage 及其组件测试并回报检查，当前会话仅维护本功能过程文档、独立审阅和页面检查。生产文件不交叉写入，交付依据为共享工作区的实际 diff 与检查回报，无新增会话或 Git 操作。

20:22 补充范围由当前会话修改 RoomPage 选择处理函数并检查，Relay 消息 0014 已向产品经理和用户同步范围；产品经理上一轮交付已完成，不重复修改其侧栏文件。

20:29 新方案分工接收（消息 0017、0018）：产品经理修改 room.css、MessageQueue.vue 及队列组件测试并汇总最终交付；当前会话修改 RoomPage.vue、useRoomPanel.ts、面板状态测试与三份过程文档，负责必要状态测试和页面集成检查。接收位置即本节，进展及交付写入本计划新增的右列分区交付节，并通过 Relay 回报产品经理。DOM、关闭语义及条件跟随边界已在消息 0018 明确，不交叉写入生产文件。当前工作区既有变更作为基线，不新增 task 或 Git 操作。

20:43 双全部补充分工接收：当前会话继续修改 RoomPage/useRoomPanel、轻量状态测试和过程文档，接收及设计边界已在消息 0033 同步；产品经理在接入完成后执行针对性集成检查。页面检查按用户最新要求仅通过 jev-ultrafast-mcp 列举并复用已有 tab，不新建 tab 或检查页；当前列举失败及连接诊断结果已在消息 0031 回报。

20:49 截图补充由当前会话修改 MessageDetails、对应测试及孤立 CSS，并维护记录；消息 0040 已向产品经理同步新增范围。已有双全部修正保留，不干预用户管理的开发服务器；现有 tab 的后续页面检查交由产品经理，避免并行操作。

21:15 最新分工（0049、0053）：产品经理负责 MessageQueue、队列样式和组件测试；当前会话负责后端查询/契约/路由与测试、roomApi/useMessageQueue 及分页测试、最终详情状态和记录。最终规则以0044/0046及新队列表格要求为准。页面检查按0043由当前会话复用自身可用的已有Jev tab，禁止新建页面；用户0032明确自行管理开发服务器，所有会话均不启动、停止或重启服务。

21:39 当前有效分工（0050、0052、0055、0063、0064）：产品经理负责最终详情 getter 模型、全部队列前端及测试和必要前端检查；当前会话负责后端队列范围/分页契约、查询/HTTP 测试、三份记录及已有 Jev tab 页面检查。计数修正由当前会话完成并在0064交回 MessageQueue 与组件测试，后续不交叉写入；后端范围采用 topic_id/member_id，与前端约定一致。继续禁止新建 tab 或管理用户开发服务器。

21:52 追加清空及展示分工（0068、0070、0071）：产品经理负责前端二级样式、标题/空态、清空按钮/API和人为删除展示；当前会话负责清空服务/持久化/HTTP、迁移、后台排除及必要测试和记录。共享契约为 deletedAt 字段，非新增投递状态；清空使用当前详情scope，返回 removedMessages。

22:11 当前补充：0072明确不显示删除文案；产品经理0073交付样式/清空及独立成员小节移除，0075继续负责最新状态列及测试和已有tab页面检查。当前会话完成后端检查、三份记录和交付，不并行导航；若同伴页面工具受限再接回已有tab检查。

22:25 最新接收：产品经理0078/0079已交付名称/状态、15字符预览及检查，0077将页面检查交回当前会话。新增A16由当前会话仅修改RoomPage队列选择入口并检查；不交叉修改状态模型。用户明确停止聊天室发布，后续更新只在当前对话及本记录，不再发布Relay消息。

## Verification plan / 检查与验证安排

- 后端集成测试：积压超出最近 50 条、活动状态去重、混合接收状态、全部接收移出、降序翻页、房间隔离、资源范围/交集/发送者和接收者语义及参数校验。
- 清空与迁移检查：范围内全部页、已接收和其他范围留存、事件及幂等；迁移旧基线数据不丢失；人为删除后不再待提交/激活/核验，旧回写不覆盖标记、不触发额外驱动操作。
- 前端轻量测试：队列请求范围、分页、已完成进度、空/错误/加载反馈、点击事件；独立面板状态覆盖默认派生当前列表最后消息、关闭回默认、明确选择稳定、同 ID 更新和双全部。不整页挂载 Router/Store/API，不再测试已删除的条件跟随。
- 追加筛选检查：默认全部、具体项及全部的切换、重复点击保持选中、全部项不在排序容器及持久顺序中；通过页面操作核对重复点击仍保留筛选、两个维度独立恢复及重开房间默认全部。
- 开发检查：根目录 `make check`、`make test-unit`；相关后端集成测试；`make -C web test`。必要时使用 Makefile 对应的 uv/corepack 入口排查失败，不安装或升级依赖。
- 实现完成后记录证据并交付，整体 Verification 尚未获得单独授权，验证记录保持 Draft。

## Risks and recovery / 风险与恢复

- 实时列表变化可能使后续页缩短，刷新重新构建已加载范围并更新总数；请求失败不丢失现有列表。
- 不访问真实 Codex 队列做开发测试，不修改现有发布或接收逻辑。
- 清空追加nullable字段的增量迁移，原基线可原地升级且数据保留；不支持降级，不删除或重建用户库。回退应用前须核对旧版本对新增字段及删除标记的处理，不能将软删记录重新当作待投递。

## User review notes / 用户审查记录

- 2026-11-10：按已有评估及用户明确实现授权接受本计划，局部技术选择遵循仓库现有分层和组件规范，无待决方案缺口。
- 2026-11-10 20:08：按用户消息 0007 接受 A07、A08 追加方案，原有队列交付保留；本次进展和检查追加记录于本计划。

## Implementation delivery / 实现交付

以下原始队列及侧栏交付为历史证据；20:28 后的右列布局与详情入口以最新意图、设计和后续右列分区交付为准。

- 执行状态：实现完成，必要开发检查通过，待独立整体 Verification；方案状态仍为 Accepted。
- 交付位置：基于 b24fb5a 的当前工作区 diff，未提交 Git。新增只读队列接口、独立队列数据及面板状态、队列组件，调整 RoomPage 与原有响应式面板样式，清除重复的时间线 showDetails 事件。
- 详情改为直接持有所选消息，队列刷新和聊天筛选不会清除该对象；加载所选详情后再启动事件补取，避免旧详情响应覆盖后续接收事件。
- 后端新增 3 个队列集成用例，覆盖 125 条历史中的旧积压、多个投递去重、消息数量与投递数量差异、房间隔离、混合接收状态、全部接收移出及参数校验。
- 前端新增队列组件、队列数据及面板状态测试，补充独立 API 参数用例；保留既有测试，仅删除已移除 showDetails 事件的失效断言。全量前端测试显式显示日志，无测试警告。

### Development checks / 开发检查

| 工作目录 | 命令 / 检查 | 实际结果 |
| --- | --- | --- |
| 仓库根 | `uv run --locked pytest tests/integration/test_room_queries.py tests/integration/test_room_api.py tests/integration/test_user_members.py -q` | 40 passed |
| 仓库根 | `make test-unit` | 31 passed |
| `web` | `corepack pnpm test --reporter=default --silent=false --no-color` | 24 文件、132 测试全部通过，无警告 |
| 仓库根 | `make check` | Mypy、Ruff lint/format、Vue 类型、ESLint、Prettier 全部通过 |
| 仓库根 | `make -C web check` | 最后一次前端调整后再次通过类型、lint、格式检查 |
| 仓库根 | `git diff --check` | 通过 |

- 默认 Node 22.22.2 被项目 engines 拒绝；切换当前检查进程 PATH 至本机已安装的 Node 24.22.2 后通过。未安装依赖、未修改项目版本要求或全局 Node 配置。
- 先对本次前后端修改运行既有 formatter，再执行只读检查。前端首轮针对性测试中一个分页替身不符合满页契约，已修正为真实的 50+1 条分页数据，全量前端测试通过。

### Browser smoke checks / 页面开发检查

- 真实开发页面确认默认队列、空态、关闭消息/话题/成员详情返回队列；保留现有桌面三列宽度、字体和详情样式。
- 临时 SQLite + FakeSessionDriver + FakeQueueDriver、关闭后台 lifespan 的隔离服务中构造 66 条消息：聊天最新 50 条不含消息 1–6，队列仍展示这 6 条；点击消息 1 正确打开详情，中间聊天页不跳转。
- 隔离页面搜索不存在的正文后，聊天显示“未找到匹配的消息”，队列仍为 6 条，且能继续打开旧消息详情。
- 对隔离数据库通过既有 confirm_input 写入模拟接收，触发现有 delivery 事件；详情保持消息 1 并更新接收时间，关闭后队列由 6 变 5，消息 1 移出。
- 已检查空态及非空队列截图：`C:/Users/leon/.jev-ultrafast-mcp/shots/queue-panel-default.png`、`C:/Users/leon/.jev-ultrafast-mcp/shots/queue-panel-populated.png`。临时前后端服务均已停止；临时操作没有写入真实房间或实际 Codex 队列。

### Remaining review / 待审查事项

- 未进入独立整体 Verification，记录保持 Draft；完整后端集成套件、人工窄屏抽屉操作与长时间断线恢复未单独执行。小屏状态已由轻量状态测试及响应式代码检查覆盖，不声称已完成人工窄屏验收。
- 无已知未修复实现问题、无方案范围偏差、无数据库迁移或新增依赖。

### Sidebar selection delivery / 侧栏筛选追加交付

- 2026-11-10 20:16：产品经理在 Relay 消息 0011 回报实现交付，修改限于 TopicSidebar、MemberPanel、RoomPage 及两份侧栏测试；当前会话复核最终实际 diff 与页面操作后接受该局部交付，A07、A08 的实现及开发检查完成。
- 全部入口采用现有 sidebar-node-fixed、hash/at 图标和 is-active 高亮，位于排序容器之外；没有虚拟 ID、样式新增或后端修改。页面默认两个全部入口高亮，固定用户“你”位于全部成员之后。
- RoomPage 将原先点击同 ID 设为 undefined 的逻辑改为直接赋值；undefined 仅由全部入口和既有房间重置使用。全部入口恢复自身维度；当当前详情属于该维度时关闭并回队列，其他详情不变。
- 检查回报（Relay 消息 0011）：在 web 使用本机 Node 24.22.2，定向运行 TopicSidebar、MemberPanel、RoomComposer、useSidebarOrder 共 4 文件、31 测试通过；前端 Vue 类型、ESLint、Prettier 检查通过，git diff --check 通过。未改环境配置；本会话在接收检查回报后未重复运行相同检查。
- 本会话独立检查：审阅默认高亮、可选事件、固定项与普通资源排序边界、RoomPage 两维直接赋值；运行 git diff --check 通过。页面先默认全部，再连续两次点击“架构”，聊天持续为空、话题详情保持；选产品经理后恢复全部话题，保留成员详情及成员筛选；重复点击产品经理仍保持其消息范围；连续点击全部成员及全部话题、重新打开房间均恢复默认全部。
- 页面证据：`C:/Users/leon/.jev-ultrafast-mcp/shots/sidebar-all-default.png`，已视觉检查默认两个全部项高亮、位置与既有字体、图标、缩进一致。页面开发检查补足产品经理无法打开浏览器的工具限制。
- 无额外代码修复或范围偏差；整体 Verification 仍保持 Draft。

### Filter trigger correction / 筛选触发补充交付

- 2026-11-10 20:26：补充实现完成。RoomPage 的 selectTopic/selectMember 在详情操作之后比较当前 ID，同一选项直接返回；实际切换才同步输入区路由并重载消息、滚动到末尾。重复点击当前话题、成员和已选全部项均不触发这些副作用，具体项仍可再次打开详情。现有侧栏组件、样式及数据刷新流程保持原有契约。
- 必要开发检查：使用 Node 24.22.2，在 web 运行 `corepack pnpm test tests/domains/room/TopicSidebar.test.ts tests/domains/room/MemberPanel.test.ts tests/domains/room/RoomComposer.test.ts tests/domains/room/useRoomPanel.test.ts --reporter=default --silent=false --no-color`，4 文件、30 测试通过，无警告；`make check` 的 Vue 类型、ESLint、Prettier 全部通过；`git diff --check` 通过。此次为两个处理函数的局部控制流修正，保留现有测试，未新增整页挂载测试。
- 已审阅选择入口与调用链，确认详情操作位于短路前，输入区同步、loadRoom 和滚动位于短路后；两个维度独立比较。
- 本次页面复测未执行完成：旧浏览器连接出现 transport closed，新建会话两次返回 browser_unavailable / 缺少 DevToolsActivePort，doctor 显示未连接。此前页面证据只覆盖上轮交付，不作为本次补充的页面证据；请求数量、滚动及草稿保留的人工页面检查仍待可用浏览器。整体 Verification 保持 Draft。

### Split right-column delivery / 右列分区交付

- 2026-11-10 20:35：最新右列方案实现完成。RoomPage 直接同时挂载上方 MessageDetails 与下方 MessageQueue，队列不受消息/话题/成员详情切换影响。showQueue 只打开共同抽屉；关闭详情只隐藏上方区域，底部队列保留。
- 当前会话修改 RoomPage、useRoomPanel 及状态测试：初始和切换房间时默认消息详情，加载后选择最新消息且不自动展开小屏；发布成功显式展示发送消息；实时处理仅在时间线原本处于末尾、出现更高 seq 且消息详情打开时跟随最新消息。查看话题、成员或关闭详情时不跟随；同 ID 投递更新仍刷新当前对象，队列旧消息不依赖当前聊天页。两个筛选处理函数的同 ID 短路保持。
- 产品经理在消息 0020 交付 room.css、MessageQueue 及组件测试：右列 flex 上下分区，详情使用剩余空间，队列通过 margin-top:auto 固定底部、max-height:40% 限制高度，内容使用现有 overflow-y:auto 独立滚动；空态保留标题和一行说明。窄屏沿用共同抽屉，“收起右侧面板”按钮关闭共同容器。当前会话独立审阅实际样式及 DOM 接口一致，未发现额外集成修复项。
- 按用户显式调用的 frontend-unit-testing，原面板测试中“关闭详情切换到 queue”及“默认不选择消息”的失效断言已替换。保留同 ID 接收更新和跨聊天页选择测试，现有 4 个状态用例覆盖默认最新/房间重置、抽屉与详情独立、条件跟随、选择与接收更新。没有整页挂载 Router/Store/API、竞态或复杂生命周期测试，没有新增测试工具和依赖。
- 本会话必要开发检查：使用 Node 24.22.2，在 web 运行 `corepack pnpm test tests/domains/room/useRoomPanel.test.ts tests/domains/room/useMessageQueue.test.ts tests/domains/room/TopicSidebar.test.ts tests/domains/room/MemberPanel.test.ts tests/domains/room/MessageTimeline.test.ts --reporter=default --silent=false --no-color`，5 文件、26 测试通过，无警告；独立运行 git diff --check 通过。搜索生产调用和测试，已无 queue 类型的旧面板状态引用。
- 产品经理在消息 0024 审阅当前 RoomPage/useRoomPanel 与状态测试后，于消息 0026 回报最终集成态检查：Node 24.22.2、web `make check` 的 Vue 类型、ESLint、Prettier 全部通过；MessageQueue/MessageDetails/useRoomPanel 共 3 文件、15 测试通过，无警告；git diff --check 通过。收到回报后未重复运行同一批质量检查。
- 本轮页面检查未完成：通过 CUA 新建 Chrome 检查页时明确返回“The browser access host is unavailable”；前轮专用浏览器工具也无法建立 Chrome 连接。本轮没有页面截图、人工滚动或窄屏证据，不沿用旧互斥布局截图证明新分区效果。该限制已通过消息 0025 回报产品经理；整体 Verification 仍为 Draft。
- 交付位置为当前未提交工作区，未创建 Git 分支或提交。产品经理负责汇总用户交付；本会话在同一计划记录当前实现、检查与限制并通过 Relay 回报。

### Current delivery / 当前交付与检查

- 2026-11-10 21:43：本节覆盖最终 getter 模型、截图修改、表格进度及详情范围队列。以上互斥面板、固定右下、条件跟随、latest/closed 缓存和待处理数进度为历史方案，不作为当前行为或页面证据。
- 最终详情状态由产品经理在0050交付：可空的明确消息/话题/成员目标，默认从当前结果 getter 派生最后消息；关闭和双全部清除明确选择，重复筛选不重载；显式消息仅接受同 ID 更新。没有请求后恢复、默认消息缓存或条件跟随入口。
- 截图修改已交付：删除消息发送者/时间/正文摘要及孤立计算、样式和失效断言；话题/成员标题共享基线对齐的编辑删除动作组。
- 新队列查询纳入 pending/submitting/queued，按 seq 降序、before_seq 严格向旧分页；完整保留混合状态的投递记录，按消息去重。当前增加 topic_id/member_id，与聊天共用资源校验及范围条件；消息总数基于相同范围和活动状态，游标不缩小总数。
- 进度修正：用户截图指出 queued 消息入队 0/1 不符合左侧“已入队”；MessageQueue 改为已入队数/全部 Agent 投递数、已接收数/全部 Agent 投递数。入队累计 queued+received，接收累计 received；单 queued 显示 1/1、0/1，混合 queued+received 显示 2/2、1/2。表头 title 明确口径，已接收不代表任务完成。
- 后端最新开发检查：`uv run --locked pytest tests/integration/test_room_queries.py tests/integration/test_room_api.py -q`，39 passed；`uv run --locked mypy src tests`，106文件通过；`uv run --locked ruff check .` 通过；`uv run --locked ruff format --check .`，157文件通过。新增范围跨多页、总数稳定、发送者/接收者含人类、交集空态和资源不存在/房间隔离检查。
- 前端历史集成检查：产品经理0056回报 MessageQueue/useMessageQueue/roomApi/useRoomPanel/MessageDetails 共5文件25测试及类型、lint、格式检查通过，无警告，覆盖内嵌队列之前的三列表格。当前会话随后修正进度，MessageQueue 4测试通过且无警告，Vue类型及ESLint通过；Prettier发现一处换行，已修正并全前端格式检查通过。该计数修正已在0064交回产品经理；这些结果不累加为同一批测试总量，也不替代后续内嵌布局检查。
- 页面中间态：仅复用 Jev 已有 index0，验证桌面默认详情/三列表格、话题与成员详情操作组对齐、队列排序；修改进度后页面文本显示1/1、0/1。旧截图 `queue-table-final-default.png`、`queue-table-final-topic.png`、`queue-table-final-member.png` 已查看，仅覆盖固定右下及旧进度，不证明最新内嵌布局；内嵌交付稳定后另行复测。
- 当前协作：产品经理按0063完成详情内嵌队列及前端范围切换；当前会话已交付后端范围和检查，在本节继续补最终页面与前端证据。用户管理的服务未被启动、停止或重启；未新建浏览器 tab、未执行 Git 写入。

### Latest queue cleanup / 最新清空与状态展示交付

- 2026-11-10 22:11：已完成范围清空、内部删除标记及增量迁移；最终展示以本节和当前技术方案为准，前节 x/y 进度与旧截图仅为历史。队列标题无数量，内嵌详情；二级小节无分隔线、统一空态。消息详情独立 @成员列表移除，成员表与队列表都改状态列。
- 后端 `DELETE /queue` 在单一写事务标记范围内全部未完成投递，返回去重消息数；不受当前分页影响。删除标记独立于原始投递状态和回执，写入delivery事件；重复清空返回0、无重复事件。原消息、已接收投递及其他范围保留，不调用Codex驱动。
- 后台查询与处理排除deleted_at：队列/汇总、pending领取、submitting阻塞、激活领取、核验清单、接收确认、note及中断收尾均处理标记。finish_delivery仅更新未删除的submitting记录并返回是否保存；旧回写未保存时不执行后续激活，避免清空后重新激活。
- 增量迁移 `queue_deleted_20261110` 在原baseline后为deliveries添加可空deleted_at，基线SQL不变；模型/序列化同步字段。迁移说明见 `migrations/README.md`。本会话仅对临时测试库执行迁移，未手动迁移真实库或管理用户服务。
- 最新后端检查：`uv run --locked pytest tests/integration/test_room_queries.py tests/integration/test_room_api.py tests/integration/test_migrations.py tests/integration/test_delivery_service.py tests/unit/test_delivery_actions.py -q`，53 passed。Mypy106文件、Ruff lint与158文件格式检查通过；`git diff --check`通过。检查中发现一处测试链式列表比较类型及迁移换行，均已修正后复查通过。
- 最新前端已有产品经理0073回报：6文件48测试及Vue类型、ESLint、Prettier、diff检查通过，无警告，覆盖样式/清空/软删忽略；其后0075状态列仍待最终检查，不将48项结果冒充后续版本证据。
- 只读排查用户0072长时间未接收：22:02从既有Codex公开RPC读到该项仍在真实队列第24位，前23项，目标active；队首为20:35用户0027，21:55已业务标删但仍保留真实Codex队列，说明业务清空按约不修改外部队列。未重发、删除、重排或启动任何真实队列项。
- 已核对本机codex0.167.0实验性协议schema，存在thread/queue/add、list、update、delete、reorder、start；普通codex queue只暴露新增，codex-cli包装层尚未暴露队列管理。该能力调查未扩大清空业务的实际外部操作范围。

### Final follow-up / 最终补充

- 22:28 当前会话在 web 运行 `MessageTimeline.test.ts` 与 `useRoomPanel.test.ts`，2 文件19测试通过；Vue typecheck、ESLint、Prettier通过。产品经理随后更新 MessageTimeline 的正常状态显示为单一阶段，并回报相关3文件30测试及 typecheck、lint、Prettier、diff检查均通过。
- 22:40 按最新界面意见将成员详情投递状态无阶段时的占位符从 `—` 改为 `-`；同轮将详情内订阅话题和消息话题从彩色标签改为与详情正文一致的纯文本排版，并为订阅话题增加轻量断言。`MessageDetails.test.ts` 10项通过，三处相关前端文件的 Prettier 检查通过。
- 页面复核仅复用已有 Jev tab：截图确认成员详情的订阅话题现以正文文本显示，不再使用彩色标签；切换话题/成员详情及返回全部入口正常。当前可见消息队列为空，因此没有制造测试数据，也无法人工实测 A16 点击队列行后的时间线滚动。此前页队列非空截图仍证明表格的15字符预览和名称/状态列，但不作为本次 A16 定位行为的页面证据。
- 用户要求不再连续发布聊天室消息后，未再发送任何 Relay 消息；未新建 tab、未管理开发服务、未对真实队列执行清空或操作。
- 整体 Verification 仍未获单独授权，本计划及验证记录维持 Accepted / Draft；代码改动未提交，未操作 Git index。
