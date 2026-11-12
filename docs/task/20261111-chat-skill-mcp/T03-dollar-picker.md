# Task / 子任务 T03：$ 候选选择器

最后修改时间: 2026-11-12 08:16:13

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：`docs/intent/20261111-chat-skill-mcp.md`。
- 权威总计划：`D:\SourceCodes\mywork\agent-relay\docs\plan\20261111-chat-skill-mcp.md`；任务 ID：T03；方案修订：3（`$` 仅展示 Skill）。

## Goal and acceptance / 目标与验收

- 在当前聊天 textarea 内实现 `$` Skill picker；Skills 在房间打开时自动后台加载，不查询或展示 MCP，对应意图 A01–A04、A06。
- 只有用户正在输入的 `$query` 调出候选；输入 `/` 不打开 Skill 菜单。名称/description 本地过滤、区分同名；加载/空/部分失败/失败状态有区别。
- 完整 keyboard/IME 行为：上/下循环或边界移动预期一致，Enter/Tab 选中而非提交，Esc 关闭，Shift+Enter 换行，IME Enter 不触发选择或提交。
- 选中时仅替换光标所在 query 范围，展示可移除的稳定 typed ref，继续输入/多次选择可用；查询命令不出现在正文，现有 `@` 和 `#` 路由行为保持。
- `RoomPage.openRoom` 发起非阻塞 Skill 预加载；同 project cache/single-flight 减少重复请求；独立请求版本/AbortSignal 防止旧房间响应覆盖；`loadRoom` 翻页/筛选不触发预载；failure不影响普通发送。
- pending publication、retry锁定态、reset、clear/remove tag 符合 T02 API refs 与总计划接收对象语义。

## Scope and files / 范围与文件

- 修改 `web/src/services/roomApi.ts` 以增加 Skill 目录 API、T02引用类型，移除前端 MCP 目录请求。
- 修改 `web/src/domains/room/RoomPage.vue` 房间打开预加载及过期请求管理。
- 修改 `web/src/domains/room/RoomComposer.vue` 光标 `$query` 提取、候选和标签、键盘优先权及消息 draft。
- 修改 `web/src/components/AppInput.vue` 读取/设置光标 selection 的最小稳定接口，并添加 composer scoped CSS/局部组件以满足 accessible listbox。
- 测试只保留轻量目录逻辑和 API 请求契约。按用户最新要求移除本轮新增 UI 测试，不增加整页、集成、端到端或秒级前端测试；界面由用户自行验收。不修改导航排序文件、全局导航样式或 RoomSwitcher tests。

## Inputs / 输入

- 依赖 T01 的 HTTP 目录 JSON shape、refresh/error状态和 T02 的 `CreateMessage`、message capability ref 类型及顺序。
- 用户输入 `$` 筛选 Skill，可用候选一经选择就成为结构化消息引用，不由自由正文猜测引用身份。
- Skill 按房间 project 目录加载；目标成员变化不触发 MCP 查询。

## Technical decisions / 技术设计

- 不引入重型 contenteditable/rich-text editor。读取 textarea.selectionStart/End，识别 `$` 当前 token 边界；正文和引用通过一次 draft 更新写入，再通过 `AppInput.setSelection` 等待 `nextTick` 恢复焦点和光标，避免受控 v-model 连续更新丢失引用。
- 选择将 query 替换为空白/指定正文分隔，typed tag 独立显示、稳定引用进 draft。正文光标前后文本保留；删除标签只删除引用不意外删正文。
- `$` query filter 纯本地；只有首次 room open、缓存失效或用户显式刷新才 fetch skill；旧 response discard。
- 对 Arrow keys/Enter/Escape/Tab 在输入框处理器中先识别 IME、候选弹层及发送态，再决定 preventDefault；保持 submit form 的错误和 lock 语义。
- 使用 `@lucide/vue` 可用图标，不以文字构造图标。候选 popup 语义、active option、屏幕阅读器状态和焦点返回需可操作。
- 页面中固定 `forceReload=false`，手动刷新才true；网络错误给候选区可重试，不 toast spam 或清掉用户正文。

## Implementation outline / 实施安排

1. 扩展 Room API TS types/fetch methods 以与已接受 T01/T02 接口对齐。
2. 在 RoomPage room identity change/open 处加独立异步 preload、skill 缓存及 stale-result 防护。
3. 在 AppInput 暴露 selection / setSelection，保证textarea可访问标签和键盘焦点。
4. 在 RoomComposer `$` 触发当前 query、过滤/select、替换 token、加入稳定 Skill ref tag。
5. 仅保留轻量目录逻辑/API 单测，运行前端 typecheck/lint/format；界面由用户验收。

## Checks and risks / 检查与风险

- 界面由用户自行验收，2026-11-12 已反馈“界面测试无问题”；本窗口不新增或运行 UI 测试。
- 按用户调用的 frontend-unit-testing 技能保留轻量单元边界：检查 project 缓存、目录部分失败、请求序列化与草稿 refs；不编写竞态、整页集成或端到端测试。旧响应保护和请求取消按生产调用方代码审查，界面另行手动检查。
- 仅运行轻量目录/API 单测、typecheck、lint、变更文件格式和生产 build；不运行浏览器或整页 UI 测试。
- 保持其他工作区变更不动；picker 失败或候选关闭不能吞正文、误发送或清空当前草稿。

## Handoff basis / 交接依据

- 协议入口：用户可见的 SpecFlow skill 及其 `references/task-coordination.md`。
- 分配与授权：总计划 Coordination/Execution registry 与用户接受记录；本任务尚未分配。
- 工作区与基线：`D:\SourceCodes\mywork\agent-relay`；派发时核对实际 HEAD/worktree；已有未提交导航工作区改动必须保留。
- 可写回报位置：本文 Reception/progress 和 Delivery/review；主会话读取 task 和实际 diff。
- 回报渠道：未分配；收到有效编号后回主会话提供可复制摘要。

## Reception and progress / 接收与进展

- 接收：用户“推进实现”授权本窗口实施；T01/T02 已接受，已读取当前组件/API 与任务范围，开始本地 T03，不使用聊天室协作。

| 时间 | 分配编号 / 执行者 | 接收、进展或阻塞 | 证据 / 回报位置 |
| ---- | ----------------- | ---------------- | --------------- |

## Delivery and review / 交付与审查

- 交付：实现完成，本窗口代码审查接受；2026-11-12 用户确认界面测试无问题。
- 实际变更：房间 Skill 非阻塞预载、同项目 60 秒缓存及进行中请求复用；独立请求版本防止旧响应覆盖，卸载取消请求。普通消息分页/筛选不触发目录预载；前端无 MCP 目录查询、缓存和候选。
- 交互：`$` 当前词查询、名称/描述过滤、上下/Enter/Tab/Escape、IME 与 Shift+Enter；选择后仅移除当前查询词，以可移除 typed 标签保存 Skill 引用，随发布、未决请求和时间线往返。新增图标使用现有 @lucide/vue。
- 当前检查：目录逻辑 3 项和 roomApi 10 项单测通过（17ms 测试耗时，总运行 841ms），显式开启日志后无测试警告；typecheck、格式与变更文件 ESLint 通过。
- 测试调整：按用户指令删除本轮新增 RoomComposerCapabilities UI 测试与专用 fixture helper，不编写整页、竞态或跨层测试。未运行浏览器或真实发送。
- 2026-11-11 22:51：修复 Tab/Enter 选中后引用被后续正文更新覆盖的问题。选中路径统一为一次 draft 更新，仅删除当前 `$query`、保留正文和已有引用；AppInput 只恢复选区，不再二次写入正文。前端 typecheck、两份变更组件 ESLint/Prettier 及 diff 检查通过，未新增或运行 UI 测试。
- 2026-11-11 22:55：按用户要求将候选收紧为 Skill，删除 MCP 请求方法、加载/交集/缓存及提示；刷新只加载 Skill。移除两项 MCP 逻辑测试及专用 fixture，剩余目录测试改用 effectScope，不挂载组件。
- 最终检查：用户界面验收通过；当前生产 build、前端全仓格式通过，ESLint 无错误，保留既有 Markdown v-html 警告及大包提示。未提交 Git。
- 版本：当前工作区 AppInput/AppIcon、RoomComposer/RoomPage、useRoomCapabilities、CapabilityTags、MessageTimeline、roomApi；最终证据见 `docs/verification/20261111-chat-skill-mcp.md`。
