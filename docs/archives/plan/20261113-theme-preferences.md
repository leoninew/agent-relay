# Plan / 计划：系统、明亮与暗色外观切换
最后修改时间: 2026-11-13 10:41:13

## Review status / 审查状态

Accepted

方案修订 1。依据 [Intent](../intent/20261113-theme-preferences.md) A01–A08，用户已要求开始实施。方案保持单任务，不建立 task/DAG；实现完成后单独汇报检查结果，整体 Verification 仍按后续授权处理。

## Intent basis / 意图依据

- 主题策略为 `system | light | dark`，默认 `system`；用户保存值按字段优先于配置。
- 系统主题由当前浏览器／WebView 的媒体查询解析，后端只保存策略。
- 主题入口为齿轮左侧的独立按钮，语言与关于保留在齿轮菜单；不启用独立设置页。
- 不引入数据库、迁移、新依赖或原生窗口主题驱动。

## Technical decisions / 技术设计与决策

### D01 偏好契约与兼容

- `Preferences` 增加 `theme` 策略，GET 返回语言、解析语言和主题，不返回后端解析主题。
- 将持久化模型与 PATCH 请求分离：
  - `StoredPreferences` 允许 `language`、`theme` 各自缺省，用于读取旧文件和表达“未覆盖”。
  - `UpdatePreferences` 至少包含一个字段；拒绝空对象、显式 null、未知字段和非法枚举。
- 服务在锁内完成读取、字段合并和写入，只更新请求中的字段；未覆盖的配置默认值不写回用户文件。
- 文件保存使用 `exclude_none`，旧 `{"language":"en"}` 文件不主动重写；含未知字段或非法值的文件仍整体忽略。
- typed config 增加 `preferences.theme = "system"`，两个 YAML 同步；非法值由现有集中加载入口拒绝。

### D02 前端状态与保存

- `preferencesApi` 增加 `ThemePreference`、`theme` 和部分 PATCH 类型。
- Pinia store 增加 `theme`；语言与主题共用 `saving`，避免并发写入互相覆盖。
- 保存成功应用服务端完整结果；明确失败保持当前值；超时／断连先 GET，按本次字段核对，不重复 PATCH。
- 现有 `save(language)` 保持兼容，新增 `saveTheme(theme)`，二者共享内部保存流程。

### D03 主题运行时

- 新增独立 `web/src/theme/index.ts`：
  - `resolveTheme(theme, prefersDark)` 只负责策略解析。
  - `createThemeRuntime(root, mediaQuery)` 负责根节点 class、`color-scheme`、`data-theme` 和媒体监听；支持注入 fake 与 `stop()`。
- 有效主题施加在 `document.documentElement`，覆盖 Teleport 的菜单、Toast、Dialog 与原生表单控件。
- `main.ts` 在偏好加载前创建运行时并启动，watch `preferences.theme` 同步策略；固定 light／dark 不受系统变化影响。
- `index.html` 在样式前用内联脚本按系统主题初始化根节点，避免系统为暗色时首次绘制使用亮色；保存策略仍以 API／文件为权威，不使用 localStorage 作为偏好源。
- 系统自动变化只切根主题，不写偏好、不弹成功 Toast、不刷新页面或重建路由组件。

### D04 菜单与视觉

- 顶栏右侧按“主题 / 齿轮”顺序紧凑并排，齿轮菜单为“语言 / 关于”，无小标题。
- 顶栏两个按钮使用 20×20 px 图标、32×32 px 按钮区域，以组件局部样式覆盖共用的 16×16 px 图标和 28×28 px 按钮尺寸。
- 点击主题按钮直接展开 radio 项：“跟随系统 / 明亮 / 暗色”；勾选表示策略值。主题菜单与语言菜单共用偏好读取、保存状态及反馈逻辑。
- 使用 `monitor`／`sun`／`moon` 图标分别表示 system／light／dark，按钮随已确认策略切换，菜单选项使用对应图标；悬停提示和无障碍名称包含当前策略。复用 `settings.appearance|system|light|dark` 与 `appMenu.themeSaved` 中英词条。
- `style.css` 补充成功、话题、引用、滚动条等配对 token；`room.css` 和偏好告警改用语义变量，保留话题颜色区分。
- 暗色 token 与 `color-scheme` 同步；阴影、遮罩等固定深色按用途保留。

## Implementation steps / 实现步骤

1. 扩展后端主题配置、DTO、存储端口、文件适配、服务、HTTP 路由及测试。
2. 扩展前端偏好 API／store、主题运行时、启动装配和 Node 单元测试。
3. 增加齿轮左侧独立主题菜单与中英词条。
4. 调整全局与聊天室暗色语义色，补首次绘制初始化。
5. 运行定向测试、全量单元、静态检查和 production build，记录未验证的真实 GUI 项。

## Files to change / 需修改文件

- 后端：`config/config.yaml`、`config/app.yaml`、`application/dto/preferences.py`、`application/preferences/{ports,service}.py`、`infrastructure/preferences/store.py`、`bootstrap/{settings,preferences}.py`、`interfaces/http/preferences/routes.py`、`tests/unit/{bootstrap,interfaces}/...`。
- 前端：`services/preferencesApi.ts`、`stores/preferences.ts`、`main.ts`、新 `theme/index.ts`、`components/{AppMenu,AppIcon}.vue`、`i18n/{zh-CN,en}.ts`、`index.html`、`style.css`、`domains/room/room.css`、`App.vue`、`web/tests/stores/preferences.test.ts`、新 `web/tests/theme.test.ts`。
- 文档：本文与 Intent；不修改已暂存的 i18n 交付内容，仅在必要时补主题词条。

## Tasks and coordination / 子任务与协调

不适用。功能围绕同一偏好契约和菜单入口，单会话串行实施更易保证兼容与检查一致性。

## Verification plan / 验证计划

- pytest：旧语言文件、字段合并、空 PATCH／null／未知字段、配置默认与非法主题、原子替换失败。
- Vitest：主题解析、系统变化、固定策略、监听清理、保存成功／失败／未知结果、语言与主题互不重置。
- 静态与构建：`uv run --locked mypy src tests`、Ruff、`corepack.cmd pnpm exec vue-tsc --noEmit`、ESLint、Prettier、`corepack.cmd pnpm build`。
- 未运行项：真实浏览器、WebView2、900×600 窗口、系统动态切换、冻结制品的视觉与首次绘制观察；不以自动化替代。

## Risks / blockers / assumptions / 风险 / 阻塞项 / 假设

- 旧版本可能拒绝含 theme 的新偏好文件；新版本必须兼容旧文件。回退时保留语言并移除 theme 即可。
- 内联初始化只按系统起始，已保存固定策略会在 API 返回后应用；若保存值不同于系统，仍可能短暂切换一次。
- 既有暗色 token 未经过视觉验收，固定颜色替换后仍需真实窗口检查对比度。
- 当前工作区有未暂存的面板布局与 i18n 词典并行修改；只做必要交集，避免整体暂存。

## Rollback / recovery / 回滚 / 恢复

- 产品回滚不删除用户文件；旧代码遇到 theme 字段会忽略整份偏好并回退配置。
- 恢复固定主题可在菜单重新选择；无需数据库或迁移回滚。

## User review notes / 用户审查记录

- 2026-11-13 10:18:00：用户要求开始实施；采用评估推荐方向并保持单任务。
- 2026-11-13 10:25:00：实施完成。后端偏好契约、持久化合并、配置与 HTTP 路由已扩展；前端主题运行时、首屏初始化、齿轮外观子菜单、中英词条与暗色语义色已接入。系统主题检测不可用时回退明亮，固定明亮／暗色仍可用。
- 自动化结果：`pytest` 342 passed；`mypy` 178 files；Ruff lint／format 通过；Vitest 85 passed；`vue-tsc` 通过；ESLint 0 error（既有 23 warning）；Prettier 通过；production build 通过（仅有既有 500 kB chunk 提示）；`git diff --check` 通过。
- 对比度抽查：暗色正文、弱化文字、成功／警告、话题及引用样式最低约 6.96:1；明亮正文、成功、警告及话题最低 4.63:1，达到 WCAG AA 正文阈值。
- 实测补充：用户已确认主题切换实际有效。真实浏览器与 WebView2 动态主题、900×600 窗口布局、菜单 hover／键盘实际表现、首次绘制闪烁及原生窗口标题栏仍保持未单独记录。
- 提交准备：按主题相关文件与 hunk 暂存，不纳入并行的面板布局、发送提示及 Codex 会话 ID 改动；未提交、未发布。
- 2026-11-13 10:30:20：按用户要求将外观子菜单移为齿轮左侧独立主题按钮，直接展开三项主题选项，复用原有偏好持久化与 Toast 反馈。
- 入口调整检查：主题及偏好 Vitest 13 passed；`AppMenu.vue` 的 ESLint／Prettier 通过；`vue-tsc` 及 production build 通过（保留 chunk 体积提示）。本次入口位置与菜单交互尚未另行 GUI 实测。
- 2026-11-13 10:38:54：根据用户要求，将固定主题图标替换为跟随已确认策略的系统显示器／太阳／月亮图标，同时为三项菜单补充对应图标及按钮的当前策略提示。
- 图标调整检查：`AppMenu.vue` 和 `AppIcon.vue` 的 ESLint／Prettier 通过；`vue-tsc` 及 production build 通过（保留 chunk 体积提示）。
- 2026-11-13 10:41:13：回应用户的右上角图标尺寸反馈，将主题和齿轮按钮的实际图标从 16×16 px 调至 20×20 px，按钮区域从 28×28 px 调至 32×32 px。
- 尺寸调整后再次检查：两个组件的 ESLint／Prettier、`vue-tsc` 和 production build 均通过；未新增单元测试或进行 GUI 实测。
