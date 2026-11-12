# Task / 子任务 T05：设置页面与中英界面迁移
最后修改时间: 2026-11-12 21:36:25

## Review status / 审查状态

Draft

局部方案属于父级 Plan 修订 1。未接受、未分配，未授权实施。

## Parent and authority / 父任务与权威记录

- 总意图：[中英多语言与用户偏好设置](../../intent/20261112-i18n-preferences.md)。
- 权威总计划：[Plan](../../plan/20261112-i18n-preferences.md)；任务 ID：T05；方案修订：1。
- 权威协调根：`D:\SourceCodes\mywork\agent-relay`。

## Goal and acceptance / 目标与验收

交付可保存选择的设置页面和完整中英 Web 界面，对应 A04、A05、A06、A08。

- 全局设置入口不依赖聊天室加载或存在，保存后立即生效且反馈准确。
- 迁移所有产品文案，包括公共组件、校验、Toast、Tooltip 和 aria 文本。
- 设置往返保留同一聊天室实例、草稿、引用、路由目标、在途和待确认发布；不自动发消息。
- 显示固定用户为“你 / You”，不翻译普通业务数据；已知系统原因按 code 翻译。

## Scope and files / 范围与文件

- `web/src/App.vue`、`router/index.ts`、新 `domains/settings/SettingsPage.vue` 及局部样式。
- `web/src/components/`、`domains/room/` 中的产品文案／状态／生命周期，`stores/rooms.ts`、`stores/toasts.ts`。
- `web/src/services/api.ts`、`roomApi.ts`、必要的消息渲染／身份显示 helper。
- 接续 T03 的两个词典，补全全部 UI 与 T04 系统码；对应组件／router 单元测试。
- 不修改后端、桌面 Python 词典、数据库、前端依赖或测试框架；依赖／i18n 基础问题先回报 T03 交付复核。

## Inputs / 输入

- 直接前置 T03：已接受的 i18n 工厂、MessageDescriptor、偏好 store／API、日期工具和测试挂载约定。
- 直接前置 T04：已接受的业务／会话原因码及 Candidate DTO 字段。
- 派发使用包含二者的实际集成版本，不只读取各自任务的完成声明；共享词典在 T03 接受后交给本任务维护。

## Technical decisions / 局部技术设计

- 新路由 `/settings`，App 全局导航中保留固定入口。页面三选项使用现有 Reka／表单控件和原语言名称，显示 resolvedLanguage，先编辑再显式保存。
- 页面进入时重读偏好；保存中防重复提交，成功才应用 store 已确认值。确定失败保留生效语言；未知结果按 T03 的 GET 核对状态展示重新读取入口，不直接再次写入。
- 配置／偏好加载错误在 App 提供可重试非阻断反馈；没有聊天室仍可使用设置。最近有效 room ID 由 rooms store 记录，返回时房间已删除则回首页。
- App 的 RouterView 仅对一个 `RoomPage` 使用 KeepAlive，不以 room ID 建多个缓存页；settings 本身不缓存。语言变化不改变缓存 key 或强制 remount。
- `RoomPage` 停用时取消只读查询／搜索计时器并暂停事件订阅，激活时恢复订阅并补取数据；避免与首次 onMounted 重复初始化，最终卸载仍完整清理。
- 缓存页面继续承接原在途 publish Promise，沿用原 ID、写请求及 sessionStorage 结果待确认记录；不得把打开设置、激活页面或切换语言当成恢复／重新发布动作。
- `deliveryStage` 改为 D06 的语义聚合状态，MessageTimeline／Queue／Details 在渲染时翻译；SessionStatus 分支比较事实，不比较“不可用”等显示值。
- `describeApiError` 生成 MessageDescriptor，字段错误、业务提示和 Toast 保存 key／params／requestId，显示时响应当前 locale。未知原因码使用场景摘要，不显示裸 key 或不可信 5xx 内容。
- 集中提供按固定 ID 本地化的 member 显示名，覆盖 MemberIdentity、作者、引用、筛选／排序／删除等 aria 文字；普通成员和 Session.name 原文不动。
- `unavailableReasonCode` 与 CatalogIssue.code 映射词条；投递使用本地化摘要和有标签的原始诊断，不猜测或翻译历史 error/note。
- 句子使用参数插值而非片段拼接，保留业务名称和编号。日期使用 T03 工具，分组按事实而非译文。

## Implementation outline / 实施安排

1. 建立设置页面、全局入口、最近聊天室返回路径和保存反馈，消费既有偏好 store。
2. 为 RoomPage 增加 KeepAlive 激活／停用安排，先验证草稿和发布身份保留，再迁移页面文案。
3. 完成公共组件与所有 room 组件／composable／store 的词条、语义状态和消息描述迁移。
4. 接入 T04 错误／会话原因、固定用户显示 helper，补全两份词典和原始诊断边界。
5. 更新现有测试挂载与受影响断言，补充英文／运行中切换／设置往返行为证据，记录布局待验项目。

## Checks and risks / 检查与风险

- 设置：空房间、读取失败、三种选择、保存中、成功／确定失败、结果未知后重读和返回路径。
- 同一 Router／组件单元内从聊天室进入设置再返回，检查草稿正文、话题／成员目标、引用和 publication ID 不变；分别覆盖普通草稿、正在发布和待确认发布，断言没有额外 POST。
- 检查停用后只读订阅／计时器释放、激活后补取并恢复，不清空筛选或产生重复订阅。
- 英文代表场景：表单必填、未知／失败投递、不可用会话、固定用户与日期。运行中切换已显示错误／Toast，普通业务数据仍保留原文。
- 词典 key／参数检查及有针对性的源码检索，剔除内容数据／测试 fixture 后核对未抽取的产品中文，不机械改写所有中文。
- 运行定向 Vitest、typecheck、lint、format 和 production build；真实 GUI 布局在实施后环境具备时观察并记录，不以 jsdom 代替布局证据。
- 英文布局核对桌面最小 `900×600`、设置表单、侧栏状态、按钮和较窄浏览器宽度，允许合理换行而不改写业务语义。
- 本任务的重点风险是只保留 draft 而丢失在途 Promise 状态，以及缓存后遗留后台订阅；两者都须检查。

## Handoff basis / 交接依据

- 未分配；无有效分配编号或 Implementation 授权。
- 协议入口与主会话权限见总计划“协调信息”和 SpecFlow 协作契约。
- 工作区：`D:\SourceCodes\mywork\agent-relay`；派发时记录包含 T03／T04 的已接受版本与词典写入移交。
- 可写回报位置：本文“接收与进展”“交付与审查”；默认输出摘要由用户转交主会话。

## Reception and progress / 接收与进展

尚无接收记录。

| 时间 | 分配编号 / 执行者 | 接收、进展或阻塞 | 证据 / 回报位置 |
| --- | --- | --- | --- |
| 2026-11-12 21:36:25 | 无 / 无 | 已记录方案，等待 T03／T04 集成版本和授权 | 本文与总计划 |

## Delivery and review / 交付与审查

- 未实施、未交付；未产生实际版本或检查证据。
- 正式交付填写 A04／A05／A06／A08 逐项结果、实际界面范围、前置版本、检查与修复、布局观察及未验证项目。
- 主会话尚未接受交付，不满足 T07 的该项前置条件。
