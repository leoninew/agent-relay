# T02：可重复部署的 Pages 项目站
最后修改时间: 2026-11-20 20:22:41

审查状态：Accepted。修订 2；[意图](../../intent/20261120-github-pages-help.md)；[权威计划与分配](../../plan/20261120-github-pages-help.md)。当前分配 `T02-658-01`，执行者协作人2。

### 本次分配与边界

- 用户授权来源：频道 seq 649，推进本 feature 实施；总计划明确不含 Git 推送或启用 Pages。
- 输入：基线 `9aa1d69`，已接受 T01 内容快照 SHA-256 `ccaa06e8761cb05c0a94000ce9cb62d52e419bbb3b5560e65f08e453d79abc46`。
- 允许范围：`help/` 站点工具链、构建/产物检查和 `.github/workflows/help-pages.yml` 本地实现与验证；不改 `help/content/`、T01/T03 内容、README 或应用。
- 禁止操作：不推送、不触发远程部署、不调用 GitHub API 修改 Pages 配置、不公开发布。线上部署仍待单独授权；若任务验收因此未完成，应如实记录阻塞。
- SpecFlow 协议入口：`C:/Users/wangm25/.codex/plugins/cache/specflow-local/specflow/0.2.1/skills/specflow/references/task-coordination.md`。执行者先在本 task 记录接收、基线和授权，再开始产品修改；交付后由主责审查。

## 实施与检查

1. 在 `help/` 建独立包、锁文件和 VitePress 配置，建立独立于正文的输出目录，固定 `base: '/conflua/'`；禁止指向内容根以外的包含、符号链接或未经审核的静态资源。保留死链检查。核对生成 HTML 路径与 T01 清单，仅允许文章、框架必需页和审过的资源；不要上传整个工作区。
2. `corepack pnpm --dir help install --frozen-lockfile` 后执行 `corepack pnpm --dir help build`；本地在真实子路径预览，检查首页、深链刷新、导航、静态资源及错误 URL。至少保留一次负例：额外的未列名文章必须使产物检查失败。
3. 新增 `.github/workflows/help-pages.yml`；PR 只安装、构建、检查，无部署权限；GitHub `develop` 上影响站点的 push 或明确限定该分支的手动触发才能部署。覆盖内容、锁文件、Node 版本、工作流变更。只上传验证过的 dist；单独部署 job 使用 `github-pages` environment、`pages: write`、`id-token: write`，构建仅 `contents: read`。串行部署；不使用 PAT，不修改现有桌面发布流程。
4. 获得上线授权后，在仓库 Pages 选择 GitHub Actions 来源，可用 `gh api --method POST repos/leoninew/conflua/pages -f build_type=workflow` 首次启用；先复查现态，已启用时不盲目创建。核对环境分支限制与审批。记录工作流运行 URL、部署 SHA、Pages 返回站址；验证文章直接访问、刷新与资源响应，不把首页 200 作为全部验收。

验收 A03、A04；本地通过不等于线上部署。临时无发布授权时可提交构建证据，但保持线上验收未完成，不放行产品入口。

## 接收、进展与交付

2026-11-20 18:46:24 +08:00 接收分配 `T02-658-01`；执行者协作人2（`0S9KXJ4SR005T`），任务修订 2。基线为 `9aa1d69` 加已接受 T01 内容快照 SHA-256 `ccaa06e8761cb05c0a94000ce9cb62d52e419bbb3b5560e65f08e453d79abc46`；实施授权来自频道 seq 649。范围仅限 `help/` 站点工具链、构建/产物检查和 `.github/workflows/help-pages.yml` 本地实现与验证；不改 `help/content/`、README、应用或其他任务内容，不推送、不触发远程部署、不调用 GitHub API 修改 Pages 配置或公开发布。线上部署及相关验收待后续单独授权。

交付填写实际版本、检查结果、线上证据、偏差、遗漏与风险，并回报主会话；写完 T02 后等待主责审查，不开始 T03。

### 本地交付待主责审查

2026-11-20 19:08:05：当前分配 `T02-658-01`，方案修订 2，前置为已接受 T01 快照 `ccaa06e8761cb05c0a94000ce9cb62d52e419bbb3b5560e65f08e453d79abc46`。新增独立 VitePress 包及 pnpm 锁文件、固定 `/conflua/` base 与 `help/content/` 源目录配置、明确导航、禁用公共目录复制；新增站点源文件/17 文件 T01 快照/HTML 路径/框架输出/审查图片校验，以及拒绝未列文章的负例。新增 `.github/workflows/help-pages.yml`：PR 仅构建与检查；只有 `develop` 的 push 或 `develop` 上手动触发才上传 Pages 产物并进入独立部署 job，构建权限为 `contents: read`，部署权限限于 `pages: write`、`id-token: write`，部署使用 `github-pages` environment 并串行执行。上传路径仅为 `help/.vitepress/dist`。

- 变更范围：`help/package.json`、`help/pnpm-lock.yaml`、`help/.vitepress/config.mts`、`help/scripts/check-site.mjs`、`help/scripts/test-site-check.mjs`、`.github/workflows/help-pages.yml` 与本 task 记录。未改 `help/content/`、README、应用、桌面指南或其他 task 内容；工作区中 T01 已有的文件保持原样。无范围偏差。
- 输入核对：当前 HEAD 为 `9aa1d693146629c246fcc4cd6194a801d2db86f0`；本机复算 T01 17 文件摘要得到与接受值相同的 `ccaa06e8761cb05c0a94000ce9cb62d52e419bbb3b5560e65f08e453d79abc46`。
- 通过检查：`corepack pnpm@10.34.9 --dir help install --frozen-lockfile`；`corepack pnpm@10.34.9 --dir help build`（VitePress 1.6.4）；`corepack pnpm@10.34.9 --dir help check:site`（11 个 HTML：10 个清单页面及 VitePress 404 页；40 个框架/打包资源；所有本地链接目标存在；两张 PNG 与 T01 源哈希相同，三张 SVG 均以内嵌数据出现）；`corepack pnpm@10.34.9 --dir help test:site-check`（真实构建副本增加 `unlisted-article.html` 后校验器拒绝）；`go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7 .github/workflows/help-pages.yml`；`git diff --check`。本机 Node 为 `v24.22.2`，仓库 CI 按 `.node-version` 固定为 `22.23.4`。
- 本地子路径预览：`http://127.0.0.1:4179/conflua/` 首页、`/conflua/guide/first-handoff.html` 深链、CSS 与实拍图片均为 HTTP 200；未列 URL 为 HTTP 404。检查时使用 VitePress preview，检查后停止该进程。
- 未完成与风险：没有推送、调用 GitHub API、启用 Pages 或触发远程部署；`github-pages` 环境现态、分支限制及审批尚未查验，部署 URL 与线上刷新/资源检查未完成，需单独上线授权后再做。T01 记录的正式 Windows ZIP、macOS 真机和 MCP 写入未验证风险保持不变。无其他遗漏。
- 频道回报：已定向发布给主责，消息 seq 660、message ID `0S9MGKK4400QD`、publication ID `2fb24133-fd32-4f7f-ade5-a3506622693d`；保存成功，delivery 当前为 `pending`，尚无送达确认，不重发。

当前实现仅保留于本地工作区待审查；请主责核对 diff 和构建证据后更新权威计划状态。等待审查期间不开始 T03。

### 主责本地实现审查

2026-11-20 19:17:20：主责核对工作区范围、T01 输入快照、VitePress 配置、源内容和构建产物检查器，以及 workflow 的触发条件、分 job 权限、`github-pages` environment 与部署串行化。未发现超出 T02 范围或放宽部署权限的问题。

主责复跑 `corepack pnpm@10.34.9 --dir help install --frozen-lockfile`、`corepack pnpm@10.34.9 --dir help build`、`corepack pnpm@10.34.9 --dir help check:site`、`corepack pnpm@10.34.9 --dir help test:site-check`、`go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7 .github/workflows/help-pages.yml` 和 `git diff --check`，均通过。未带版本号的 `corepack pnpm` 在主责环境调用到了 pnpm 11.25.0 并按项目版本约束拒绝；明确使用锁定的 pnpm 10.34.9 后通过，不属于项目失败。

线上 Pages 未启用，GitHub 环境/分支审批、部署运行及实际 URL 尚未核验。因 A04 包含线上部署证据，而现有授权明确不含推送、启用 Pages 或部署，本地实现检查通过但任务整体不接受；执行登记保持 running，等待用户单独授权。未修改产品代码或远端配置，未开始 T03。

2026-11-20 20:22:41 更新：用户在频道 seq 662 表示自行部署。线上操作由用户执行；本任务代码保持在共享本地工作区，尚无 commit/push、Pages 配置变更或远程 workflow run。部署后需提供 GitHub `develop` 的 commit SHA、Actions run 和实际站址，主责核对首页、深层文章直达/刷新及图片/CSS 后再接受 A04。协作人2无需继续修改代码，T03 仍等待此验收。
