# Task / 子任务 T02：输入框模型选择
最后修改时间: 2026-11-16 07:44:00

## 审查状态与权威记录

Accepted；任务 T02，方案修订 5。父意图 `docs/intent/20261115-member-model-selection.md`，权威计划 `docs/plan/20261115-member-model-selection.md`，协调根 `D:/SourceCodes/mywork/agent-relay`。

## 目标、范围与输入

交付 A01、A04–A05、A07–A11 的直接单选成员模型区域。范围为 roomApi、独立模型 composable/组件、RoomComposer、room.css、双语文案及 node 单元测试。依赖 T01 经主会话接受的工作区 API 与针对性测试证据；接口字段及错误语义均由总计划固定。

## 局部设计与实施安排

1. typed API 与作用域 key 含 room/channel/member/session；从 composer 直接选择的原始成员 ID 数量判断恰好一个，再核对未删除 agent 和 sessionId。
2. 作用域变化同步清除状态，以代次令牌拒绝旧加载/更新/失败；忙碌成员允许配置后续轮次。切换请求携带目标 sessionId，期间禁止重复切换。
3. 在相同 routing flex 行增加第三块模型，沿用原分隔符与列表项样式；只展示前 4 项 + “...”悬浮 Popover/Portal 完整列表。按钮显示 model、tip 显示 displayName，真实模型以同话题/成员的背景高亮（后续项高亮“...”）。加载/更新使用 spinner，无刷新图标、“当前”字样或现场错误/成功/后续轮次描述。失败通过 Toast 保留 requestId；成功只更新选中状态。失败后下次移入模型区域可重新读取，不盲重试写入。目标变化与选中时关闭浮窗。
4. 复用现有字体、选择样式及可访问按钮；不改变消息 draft、topic routing、sidebar filter 或发送接口。

## 检查与风险

修订 5 Accepted，覆盖前述旧方案：API 使用原始 id/model；列表显示 model、tip displayName；Popover 替代 HoverCard 以支持键盘，错误 Toast、无成功或现场提示；取消成员区弹性空白，项间距与选中背景共享现有规则。A09–A11 归本任务，输入/路由不变。

Vitest node 逻辑覆盖无/多选、话题无关、会话绑定变动、A→B→A、重复提交、拒绝/网络未知后只读刷新；typed API 路径编码。运行 typecheck 与相关检查；不启动浏览器/UI 测试。

## 分配、接收与交付

- 2026-11-15 22:42 接收：主会话、`model-T02-01`、方案修订 1；用户“拆分任务，推进实现”授权有效。父计划分配与 T01 accepted 已核对；实际基线为 HEAD `9bb93db0f6f0b05d00b6e493862e739dc81d6b3a` + 当前 T01 diff，34 后端测试/mypy/ruff 通过，接口可用。
- 工作区与可写范围：同权威根，前端文件及本文；本会话直接读取回报，无跨会话交接。
- 当时交付待实施；最终接受结论在权威计划维护。
- 2026-11-15 22:48：同编号接收修订 2（用户 seq259，A07），原有 T02 尚未交付；在 T01 兼容修正接受后继续。Toast 通过既有 Pinia store，逻辑单元测试核对提示及过期作用域不产生提示。
- 2026-11-15 22:50：已核对 T01 修订 2 接受记录、35 tests 和真实目录只读结果，继续同排模型及 Toast 调整。
- 2026-11-15 22:53：同编号接收修订 3，seq261/262 对 A08 的授权明确，T01 交付不受影响，继续前端实施。UI 测试仍不运行。
- 2026-11-15 23:15：同编号接收修订 5，seq267/268/270 授权明确；基线 HEAD + 已有工作区 diff，T01 原始字段补充待复验接受，前端按新字段同步。UI 测试仍由用户执行。
- 2026-11-16 07:44：补齐最终交付记录，已核对 T01 修订 5 工作区接口及 428 后端 tests 通过，前置接受有效。`model-T02-01` 交付上述前端范围，版本为原 HEAD + 本工作区 T02 修订 5 diff。
- A01/A05：目标仅取 composer 直接单选的有效绑定 Agent；作用域包含 room/channel/member/session，代次令牌拒绝旧响应，pending 集合防止重复提交；不修改话题、投递和侧栏筛选。
- A04/A07–A11：同排第三块、沿用分隔符/间距；取消成员至模型的 flex-grow 空白；前 4 项 + “...”悬浮完整列表；显示 model、tip 为 displayName；选中态复用话题/成员 CSS，超过四项的选择同步高亮“...”。错误统一 Toast，无刷新/“当前”/成功提示/后续轮次说明。浮窗使用 Popover + Portal，保留按钮键盘焦点。
- 开发检查：模型状态 14 个 node 测试及 API 编码/字段测试通过；2026-11-16 07:41 前端全套 177 tests（25 files）、typecheck、lint、format、build 通过。07:44 收尾修正浮窗高度变量为 Popover 对应变量，并加 320px fallback；由 T03 复验此样式变更。
- 主会话依据接口/状态逻辑、最终 CSS 规则及检查接受修订 5 交付（submitted → accepted）。没有 UI/浏览器测试；悬浮效果、布局体验及真实会话切换由用户确认。
