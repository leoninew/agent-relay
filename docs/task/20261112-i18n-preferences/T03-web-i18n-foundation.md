# Task / 子任务 T03：Web 多语言基础与偏好状态
最后修改时间: 2026-11-12 23:23:15

## Review status / 审查状态

Accepted

局部方案随父级 Plan 修订 2 接受；等待前置交付后分配，实施交付另行审查。测试沿用现有 Node 单元环境。

## Parent and authority / 父任务与权威记录

- 总意图：[中英多语言与用户偏好设置](../../intent/20261112-i18n-preferences.md)。
- 权威总计划：[Plan](../../plan/20261112-i18n-preferences.md)；任务 ID：T03；方案修订：1。
- 权威协调根：`D:\SourceCodes\mywork\agent-relay`。

## Goal and acceptance / 目标与验收

交付响应式翻译、偏好状态与日期能力，对应 A02、A05，供 T05 直接构建设置和迁移界面。

- Vue I18n 与偏好读取使用同一生效语言，文档 lang 同步；不另读 navigator 形成冲突规则。
- 初始化可控、失败可重试，不能因偏好请求无限等待而卡住页面。
- 语言切换后词条、已有消息描述及日期可重新渲染，保持现有时区和时间格式语义。

## Scope and files / 范围与文件

- `web/package.json`、`web/pnpm-lock.yaml`。
- `web/src/main.ts`、`web/index.html`、新增 `i18n/`、`services/preferencesApi.ts`、`stores/preferences.ts`。
- `web/src/utils/time.ts`、必要的 Vitest 测试装配及对应单元测试。
- 不修改 App 导航、RoomPage 生命周期或业务组件；不抢先完成 T05 的全量词条迁移。
- 不修改后端、T04 错误映射或 Python 依赖；本任务期间独占前端依赖与 i18n 基础文件。

## Inputs / 输入

- 直接前置 T02：已接受的 GET／PATCH 契约、503／422 错误、可访问版本。
- 总计划 D04 的 Vue I18n、消息描述和初始化规则，以及当前 Pinia／Axios／Vitest 惯例。
- T04 可并行，不依赖其尚未接受的产品改动；公开 code 列表已在总计划冻结，具体翻译由 T05 消费。

## Technical decisions / 局部技术设计

- 安装 Vue I18n 11，使用 Composition API，两个 TS 词典随包；pnpm 锁定实际版本，不新增格式或测试工具。
- 提供 i18n 工厂、强类型语言／词条及 `MessageDescriptor {key,params?,requestId?}`；消息描述在渲染时翻译，动态后缀使用词条插值。
- 偏好 API DTO 使用 `language` 策略和 `resolvedLanguage` 语言。store 提供 load、save 和重读动作，语言只由成功读取／保存并确认的响应更新，不用 localStorage 作为权威值。
- 偏好 GET／PATCH 设置 5 秒超时；初始读取失败用英文继续挂载，保留可重试错误状态供 T05 在全局展示，不主动写用户文件。
- 写超时／断连的结果属于未知，只允许后续 GET 核对，不自动再次 PATCH；核对确认后再应用保存结果。确定写失败保留既有策略与语言；核对也失败时提供重新读取入口状态。
- 绑定全局 locale 与 document.documentElement.lang，不重新挂载整个 App。T05 可通过服务获取翻译，不在模块常量内永久缓存译文。
- 时间 formatter 按生效语言缓存；formatDateTime 也走统一语言。保留本地时区及 24 小时制，提供独立日期事实比较供 T05 替换分组逻辑。
- 测试装配提供每例独立 i18n／Pinia，默认中文以兼容已有行为断言；词典完整性检查覆盖 key、插值参数和基本可解析性。

## Implementation outline / 实施安排

1. 接入并锁定依赖，创建语言类型、词典结构、消息描述和 i18n 工厂。
2. 实现偏好 API 与 store，覆盖读取、保存、失败和未知结果后重读。
3. 调整 main 启动及 lang 同步，完成 locale 关联的日期工具。
4. 完成词典／store／日期单元和测试挂载约定，向 T05 交付使用示例、文件所有权及实际版本。

## Checks and risks / 检查与风险

- fake Axios 检查已保存 system／固定语言、失败回退、并发／过期响应处理、5 秒超时参数、保存未知后 GET 而非重复 PATCH。
- 响应式检查 locale、html.lang、日期和同一 MessageDescriptor 在切换后的结果；日期分组不依赖显示字符串。
- key／参数一致性与运行实例隔离测试；不要求把每个现有组件测试复制成两种语言。
- 在 `web/` 定向运行 Vitest、typecheck、lint／format 和 production build，确认 Vue I18n 与当前 Vue／Vite／TypeScript 配合正常。
- 测试仅用 mock API，不写真实偏好或启动后端；记录依赖 diff，保留已有 Python 暂存修改。

## Handoff basis / 交接依据

- 未分配；无有效分配编号、执行者或实施授权。
- 协议入口及主会话权限见总计划“协调信息”和 SpecFlow 协作契约。
- 工作区：`D:\SourceCodes\mywork\agent-relay`；派发时记录 T02 已接受版本和当前前端基线。
- 可写回报位置：本文“接收与进展”“交付与审查”；默认由用户转交可复制摘要。

## Reception and progress / 接收与进展

2026-11-12 23:16:10：执行者 `independent-20261112-225606` 接收 `T03-20261112-231610`，方案修订 2，用户委托实施。基线为 HEAD `e57ede1` 加已接受 T01／T02 工作区文件，偏好 HTTP 契约与共享服务可访问；沿用现有 Node 单元测试环境。

| 时间 | 分配编号 / 执行者 | 接收、进展或阻塞 | 证据 / 回报位置 |
| --- | --- | --- | --- |
| 2026-11-12 21:32:46 | 无 / 无 | 已记录方案，等待 T02 交付接受和授权 | 本文与总计划 |

## Delivery and review / 交付与审查

- 2026-11-12 23:23:15，`T03-20261112-231610` 提交；前置为 T02 accepted 工作区版本，交付为 HEAD `e57ede1` 加当前 T01–T03 工作区文件。引入 Vue I18n 11、双词典、响应式消息描述、5 秒偏好 API、Pinia 状态、启动装配和语言感知日期工具。
- A02／A05 基础：服务端解析结果驱动 locale、html.lang 与日期；初次读取失败保留英文和可重试错误状态供 T05 展示。保存失败保持语言；超时／断连先 GET，未重试 PATCH；双词典 key 和插值参数由 Node 单元核对。页面文案迁移、错误展示入口和日期分组由 T05 完成。
- `corepack.cmd pnpm exec vitest run tests/stores/preferences.test.ts tests/i18n.test.ts --reporter=default --silent=false`：6 passed；`pnpm typecheck`、`pnpm build`、`pnpm lint` 通过。lint 有既有 `MessageTimeline.vue` 的 `v-html` 警告；构建有大 chunk 警告。首次构建因顶层 await 失败，改成异步启动函数后通过。
- 主协调者核对实际代码与检查后接受基础交付，T05 仍需等待 T04。真实浏览器和英文布局未观察，供 T07 记录；其他范围偏差及待仲裁事项无。
