# T03：接入帮助站并保留聊天室上下文
最后修改时间: 2026-11-20 20:31:32

审查状态：Accepted。修订 3；[意图](../../intent/20261120-github-pages-help.md)；[权威计划与分配](../../plan/20261120-github-pages-help.md)。

## 实施与检查

1. 在 README 添加线上入口；在 `web/src/components/AppMenu.vue` 的“关于”附近加入可用键盘访问的帮助链接，中英文随现有 i18n 切换。固定 HTTPS 目标；Web 用新标签页和 `rel="noopener noreferrer"`，不改变 Vue 路由。
2. 根据锁定的 `pywebview==6.2.1` 在 Windows WebView2 与 macOS WKWebView 验证同一链接能否打开系统浏览器；优先复用已有行为。若实测不支持，再评估 `src/conflua/bootstrap/desktop.py` 的固定帮助地址动作，不向页面暴露可任意打开 URL 或执行命令的桥接接口。需要扩大桌面接口范围时先回报仲裁。
3. 在 `docs/guide/releases.md` 增加发布核对：本版本是否改变安装、菜单、首次回复流程，指南版本是否需要更新。不要重复安装正文。
4. 运行 `corepack pnpm --dir web test`、`corepack pnpm --dir web build`；若变动桌面代码则运行对应 bootstrap 测试。以包含入口的候选包分别在 Windows、macOS 操作，核对外部浏览器地址、窗口中原聊天室、未发草稿，以及中英文入口标签；Web 验证新标签与键盘操作。记录站点和候选包版本。A05 不以单测代替桌面实测。

## 接收、进展与交付

2026-11-20 20:31:32：主责人接收 T03-668-01。seq 668 授权按修订 3 进入本地实施，基线 9aa1d69（v0.57.2）及 T02 已审查本地配置。范围限 README、应用菜单及发布清单。目标 https://leoninew.github.io/conflua/ 未作线上验证；部署、真机测试由用户负责。
## 本地交付（T03-668-01）

基线 9aa1d69 上的工作区 diff：README 文档区和 AppMenu 的“使用帮助 / Help”指向同一固定地址；菜单使用 Reka 菜单项与原生新标签链接，不调用路由。发布指南已加入文档同步核对项。未修改桌面桥接：锁定版 pywebview 6.2.1 默认启用 OPEN_EXTERNAL_LINKS_IN_BROWSER，EdgeChromium 与 Cocoa 后端均有 webbrowser.open 外链处理。

本地检查：pnpm 10.34.9，Web 39 个测试文件、256 项通过；类型检查及生产构建通过（Vite 有 chunk 大小提示）；git diff --check 通过。未提交、推送或部署。A04 待用户提供实际部署 SHA、URL、首页/深链/资源结果；A05 待用户用含入口的候选包记录版本，在 Windows、macOS 有草稿的聊天室打开帮助并返回，核对系统浏览器地址、原聊天室和草稿；Web 核对键盘打开新标签与中英文标签。
