# Verification / 验证：中英多语言与用户偏好设置
最后修改时间: 2026-11-13 10:11:08

## Review status / 审查状态

Accepted

用户于 2026-11-13 确认 i18n 实现验证通过，并要求暂存工作、准备提交及补充验证文档；本轮据此执行整体 Verification 与暂存，提交未执行。真实 GUI、WebView 布局及冻结制品未运行，相关验收保持明确限定，不把自动化检查写成运行验收。

## Intent alignment / 意图对齐

依据 [Intent](../intent/20261112-i18n-preferences.md) A01–A09 及 [Plan 修订 4](../plan/20261112-i18n-preferences.md) 核对配置、系统判定、用户偏好、菜单语言切换与关于、全界面迁移、错误语义及桌面原生提示。

- 首期策略为 `system | zh-CN | en`，已保存策略优先于配置；页面消费服务端 `resolvedLanguage`，不另判浏览器语言。
- 设置入口为用户最终要求的右上角齿轮菜单，独立 `/settings` 重定向首页；未恢复已延期的设置页。
- 固定用户仅显示层按 `id === "user"` 本地化，业务名称、聊天正文、历史诊断和默认话题保留原文。
- 未新增启动参数、数据库表或迁移，未改变 CLI／MCP 协议与投递语义。

## Plan alignment / 计划对齐

- D01／D02：typed config、配置默认、用户文件原子写、系统语言适配及应用服务。
- D03：GET／PATCH `/api/preferences`，503 稳定 code、422 校验、401／404 等既有结构及 requestId 保留。
- D04／D05：Vue I18n、偏好 store、日期、MessageDescriptor、单 RoomPage 缓存及齿轮菜单。
- D06：业务错误 code、会话原因码、`deliveryStage` 语义状态、固定用户展示。
- D07：桌面共享偏好服务、原生提示与离线通知正文。

计划与实现存在一处交付前缺口：T05 进行期间 T06 尚未实施。本轮审查发现后补做桌面语言接线，归属 T06，未改变计划修订或验收边界。

## Task deliveries and integration / 子任务交付与集成

交付基线为 HEAD `e57ede19377476aec41317ac00a04aa02e9b5778` 上的当前工作区；未创建提交。T01–T07 均已在总计划登记为 accepted。

| ID | 当前有效交付版本 / 位置 | 必要检查与审查证据 | 集成与基线核对 | 验收归属与结果 |
| --- | --- | --- | --- | --- |
| T01 | 配置、偏好 DTO／服务／端口、文件存储与系统语言适配 | 34 项定向 pytest、mypy、Ruff | T02 使用同一 DTO／工厂；无数据库耦合 | A01–A03 通过（替身） |
| T02 | 偏好 HTTP 路由、依赖、异常映射及应用装配 | 17 项定向 pytest、mypy、Ruff | T03／T04／T06 共用 `app.state.preferences` 注入契约 | A03、A04、A08 通过（替身） |
| T03 | `web/src/i18n/`、偏好 API／store、启动装配、日期工具 | 6 项定向 Vitest、typecheck、build、lint | T05 消费同一词典与 store，无重复语言源 | A02、A05 基础通过（单元） |
| T04 | 领域／应用稳定 code、会话原因码、HTTP handler | 41 项定向 pytest、mypy、Ruff；本轮修正测试类型注解 | T05／T06 使用同一 code 与 DTO | A08 通过（替身） |
| T05 | 齿轮菜单、关于、公共与聊天室组件翻译、生命周期处理 | 前端全量 76 项、typecheck、lint、format、production build | 保留 T03／T04 已接受部分；未改语言契约 | A04、A05、A08 通过（单元）；A06 运行保真未验证 |
| T06 | `bootstrap/desktop.py`、新增 `desktop_messages.py`、离线正文参数 | 16 项定向 pytest；全量后端 327 项、mypy、Ruff | 与 HTTP 共享同一偏好服务；未绕过既有通知路径 | A02、A07 通过（替身）；真实 WebView 未验证 |
| T07 | 集成 diff、检查矩阵、此验证文档 | 后端 327 项、前端 76 项、静态检查、构建 | 所有前置版本在同一工作区集成交付 | A09 通过（自动化与文档） |

跨任务核对：语言策略、解析值、用户文件、复数错误 code、菜单保存反馈和桌面关闭确认使用同一契约；未发现 T05 的菜单改动改变路由缓存 key 或触发额外发布。T06 补做后重新执行后端全量测试与前端构建，未发现上游过时结果。

## Actual diff summary / 实际差异摘要

- 后端新增偏好配置、系统语言识别、用户 JSON 原子存储、应用服务、HTTP GET／PATCH 及应用信息接口；现有业务异常补稳定 code，会话候选补可空原因码。
- 桌面新增共享偏好实例和原生中英词条；关闭确认读取当前偏好，启动错误摘要与日志标签本地化，离线通知支持显式语言正文。
- 前端新增 Vue I18n 双语词典、偏好 API／store、齿轮菜单与关于、日期本地化、`MessageDescriptor` 错误与 Toast；迁移公共组件和房间界面文案，固定用户按身份显示。
- 设置页面代码保留但入口重定向首页；新增面板折叠浏览器偏好为并行工作的一部分，已在全量检查中覆盖，未被本功能文档单独验收。
- 本轮补遗为桌面语言部分、T04 测试类型注解、过程记录及本验证文档。i18n 交付已进入 Git 索引；并行的面板偏好、局部布局未暂存。

## Expected vs actual changed files / 预期与实际修改文件对比

| 预期范围 | 实际文件 / 说明 | 差异结论 |
| --- | --- | --- |
| 配置与偏好基础 | 两个 YAML、`bootstrap/settings.py`、偏好 DTO／服务／端口、存储与系统适配、配置测试 | 一致 |
| HTTP 与错误语义 | 偏好路由／依赖、`bootstrap/http.py`、`app_info.py`、异常 handler、业务 code 抛出点及测试 | 一致 |
| Web i18n 与菜单 | 依赖／锁、`main.ts`、i18n、偏好 store／API、`AppMenu.vue`、公共与 room 组件、日期、样式、测试 | 一致 |
| 桌面语言 | `bootstrap/desktop.py`、`desktop_messages.py`、桌面应用服务与测试 | 本轮补齐 |
| 文档与检查 | README、桌面指南、术语说明、Intent／Plan／T05–T07、本验证文档 | 本轮补齐 |

未发现应修改而未改的功能文件。出现的非 i18n 面板折叠浏览器偏好改动保留原归属，不纳入本功能验收。

## Acceptance criteria checklist / 验收标准检查清单

| 验收 | 结果 | 证据与边界 |
| --- | --- | --- |
| A01 | 通过 | 配置三值、默认 system 与非法值集中报错由 pytest 覆盖；无新增语言启动参数 |
| A02 | 通过（替身） | 中文变体、非中文、Linux 环境优先级、Windows UI 语言与读取失败回退由单测覆盖；未在真实 Windows 显示语言下运行 |
| A03 | 通过（替身） | 缺文件、损坏／未知字段、读 I/O 失败、原子替换失败、服务重建读回均有测试；仅用临时目录 |
| A04 | 通过（代码与单元） | 菜单读取／保存／失败／未知结果重读与重复提交由 store 测试，关于版本走应用包元数据；没有真实菜单布局证据 |
| A05 | 通过（代码与单元） | 两词典 key／参数一致性、插值、切换已有错误／Toast 与日期由 Vitest；真实英文布局未观察 |
| A06 | 部分通过 | 单 RoomPage KeepAlive、停用取消、激活恢复与旧响应失效有测试；草稿／引用／发布 ID 的真实菜单往返未在浏览器执行 |
| A07 | 通过（替身） | fake WebView／通知覆盖当前语言、取消、确认一次、通知失败仍退出及离线正文；未运行真实 WebView |
| A08 | 通过（代码与单元） | 业务 code、HTTP 状态、requestId、安全 5xx、未知 code 回退、固定用户及原文边界有测试与源码核对 |
| A09 | 通过（自动化与文档） | 全量单元、类型、lint、格式、production build 与 diff 空白检查通过；GUI／冻结制品另列未验证 |

## Test / command results / 测试 / 命令结果

项目提供 `make check` 与 `make test`，但当前 Windows 环境未安装 `make`；按 Makefile 中的等效命令逐项执行：

| 命令 / 检查 | 实际结果 | 未运行原因 |
| --- | --- | --- |
| `uv run --locked pytest tests/unit -q` | 327 passed，5.29 秒 | 不适用 |
| `uv run --locked mypy src tests` | 178 files，无错误 | 不适用 |
| `uv run --locked ruff check .` | All checks passed | 不适用 |
| `uv run --locked ruff format --check .` | 285 files already formatted | 不适用 |
| `uv run --locked pytest tests/unit/bootstrap/test_desktop.py tests/unit/application/test_desktop_exit.py -q` | 16 passed | 不适用 |
| `corepack.cmd pnpm exec vue-tsc --noEmit` | 通过 | 不适用 |
| 工作区 `corepack.cmd pnpm test` | 12 files、76 tests 通过 | 工作区含并行面板偏好测试 |
| 暂存快照 `corepack.cmd pnpm test` | 11 files、74 tests 通过 | 未包含并行面板偏好 2 项；暂存版本身通过 |
| `corepack.cmd pnpm lint` | 0 error、23 warning | 警告为既有模板格式与 `v-html`，不是本轮新增错误 |
| `corepack.cmd pnpm format` | All matched files use Prettier code style | 不适用 |
| 暂存快照 `corepack.cmd pnpm build` | 2869 modules，构建成功；JS 696.42 kB、CSS 58.48 kB | 保留既有大 chunk 警告 |
| 暂存快照 `corepack.cmd pnpm lint` | 0 error、23 warning | 警告与工作区相同，均为既有模板格式与 `v-html` |
| `git diff --check` | 通过 | 不适用 |
| 真实源码桌面、WebView2、Windows 系统语言、冻结制品、真实 Codex／聊天室 | 未运行 | 按验证边界不启动正式桌面或真实服务，避免测试数据与外部副作用 |

本轮初次 mypy 失败为 T04 测试参数注解过窄，已修正并全量复验；Ruff 首轮发现导入排序与长行，均已修复。前端 lint 无新增 error；T03 记录过的 `v-html` 警告仍存在。

## Missed or expanded scope / 遗漏或扩大的范围

- 未发现产品契约外的扩大范围；T06 补遗属于原已接受方案，而非新增目标。
- 独立设置页保持延期，`SettingsPage.vue` 仅保留代码，不作为可达功能验收。
- 面板折叠偏好 store、RoomWorkbench 布局调整及 `room.css` 相关修改是并行工作内容，保留并纳入全量回归，但未归入 i18n 的 A01–A09 证据。
- 未提交、未发布、未安装到用户环境，也未向真实 Agent 发送消息。

## Risks / 风险

- 真实浏览器与 WebView2 的菜单悬停、英文换行、关于弹窗布局、输入焦点和 900×600 最小窗口尚未肉眼验证；构建通过不能证明视觉正确。
- Windows 实际 UI 语言、系统 MessageBox 按钮语言及冻结包中的 Python 原生词典收集尚未运行验证。
- A06 的草稿／引用／在途发布身份保真仅由单元与既有实现审查支持，真实路由往返仍需桌面实测。
- 全局用户偏好为本地单用户模型，多个窗口不实时推送；其他窗口重新读取后生效。
- 既有 ESLint 模板格式警告与前端大 chunk 提示仍存在，不阻塞本功能，但会在全量检查中反复出现。

## Incomplete items / 未完成事项

- 真实源码桌面／WebView2 的交互、布局和语言观察。
- 冻结 Windows 制品的构建与运行验证，包括 `/api/app` 版本在打包环境中的返回值。
- A06 的真实浏览器菜单往返保真；A09 的 GUI 部分。

## Conclusion / 结论

自动化范围内，配置、偏好持久化、HTTP 契约、Web 双语、菜单保存、业务错误本地化及桌面原生提示均已完成并通过全量单元与静态检查；未发现会阻止提交的产品缺口。整体 Verification 对真实 GUI 与冻结制品保持限定，相关项已在本文列明，不标为运行通过。

工作区中的 i18n 相关改动已暂存并准备提交；本轮不创建 commit。不再跟踪的并行 `panelPreferences` 文件、`AppCheckboxGroup.vue`、`room.css` 及 `RoomWorkbench.vue` 面板状态改动不属于本功能交付，未混入暂存；独立主题切换评估文档同样未暂存。

## Suggested commit message / 建议提交信息

```text
feat: add bilingual UI and language preferences

- add persisted system/Chinese/English language preferences with config defaults
- localize the web UI, API errors, dates, and desktop native messages
- add the app menu, about dialog, and stable business error codes
```
