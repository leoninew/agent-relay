# Task / 子任务 T03：Web、CLI 与 MCP 使用契约适配
最后修改时间: 2026-11-19 17:33:13

## 审查状态

Accepted。依据总计划与 #592，执行状态以总计划登记为准。

## 父任务与权威记录

- [总意图](../../intent/20261119-schema-governance.md)；[权威总计划](../../plan/20261119-schema-governance.md)，任务 T03，方案修订 4。
- 交接依据：总计划登记 `SG-20261119-T03-01`，高级开发 `member-b53c76acb705`，用户 #592 授权 Implementation。协议为 SpecFlow 的 `SKILL.md` 和 `references/task-coordination.md`。代码与权威协调根均在 `D:/SourceCodes/mywork/conflua`，基线为 `develop` / `613f6a5c1b4292b95babfa57017004ace4538174` 加已接受的 T01＋T02 联合 71 路径快照 `43234D6132B1FB30412AC5EAAB23D72AE9F20AF6A5322647DF0A1E692C2B681C`；见 [T02 接口及仲裁](T02-server-identifiers.md#返工版仲裁)。执行者在本文写接收、进展与交付，在当前 Conflua 频道定向 @ 架构师回报。本文件不独立授予实施权。

## 目标与验收

交付新服务端契约的客户端接入，覆盖 A05。

- Web 和 CLI 领取、传递并保留同一个频道 ID；创建响应未知时仅查询，不重发创建、领新号重做或清理 worktree。MCP 使用示例说明如何获得实际 `channel_id` 和人类成员 ID。
- 房间切换、默认频道导航、固定人类成员显示、消息回复及图片粘贴/上传/回显使用真实 ID；不把 `channel-default`、`user` 或前缀当成业务语义，不恢复旧链接或草稿。
- 复用现有 Web 本地时间格式化与按本地日分组；CLI 仅当现有文本模式显示时间时才转换，现有 JSON 保持 UTC，不增加显示入口。用非 UTC 时区和跨本地午夜的同一时间戳验证。
- 消息发送失败时按请求错误显示 toast，保留正文为可编辑草稿；不显示“核对发布结果”按钮或待确认横幅，不锁定编辑器，不因恢复缓存而自动 POST。若对同一房间、频道和 `publicationId` 做只读查询，且服务端明确返回 `404 publication_not_found`，显示“未发现消息”；其他查询错误按实际错误提示。查无消息后由用户决定清理草稿或显式再次发送；发送成功收到响应后清理该发布缓存。浏览器草稿状态不代表服务端消息或后台 Codex 投递状态；不改变发布请求事务、后台投递或队列清理契约。

## 输入与可开始条件

- 以总计划登记的、已接受且可访问的 T02 服务端版本为准，包括实际 API/MCP 样例、DTO、图片语法和不确定结果契约。无前置版本或接口未冻结时不开始接入。

## 范围与局部方案

- 负责 `web/src/`、`web/tests/`、`src/conflua/interfaces/client.py`、关联 CLI 命令及定向测试，以及仓库 `plugins/conflua/skills/conflua/SKILL.md` 的频道、成员与创建示例。不编辑 MCP 服务端、迁移脚本或数据；不安装/发布本地插件。
- 改频道创建、默认路由和资源选择，相关 ID 类型继续是 `string`；复核图片编辑器编码、草稿和缓存作用域、固定成员展示、消息回复和已知 ID 恢复。保留原频道隔离和拒绝省略频道的既有接口语义。
- 清理当前使用指引中的旧 ID 假设，不改档案证据或引入生成算法。与 T04 可并行；服务端契约变动先报主会话。

## 检查与交付

- 现阶段只运行定向正向测试与类型、lint、format 等静态检查；覆盖正常频道领号与创建顺序、默认频道进入、固定人类成员渲染、图片语法及时间展示。报告改动版本与消费的 T02 契约版本；不启动或切换服务、不操作真实库、备份、会话或 Git 持久状态。
- 补充隔离用例覆盖频道丢失响应后的同 ID 查找，以及消息请求未到服务端或响应丢失时的 toast 与可编辑草稿、缓存恢复后无核对控件或锁定、明确 `publication_not_found` 时只显示“未发现消息”而不发送 POST、其他查询错误不冒充“未发现消息”、用户显式发送与清理、收到成功响应后清理缓存。交付逐项说明实现和已有证据；反向用例纳入验收，不在当前授权下执行，留待另行安排。
- 风险：只改前端创建入口仍会遗留 `RoomPage`、`RoomSwitcher`、消息/草稿或 CLI 假定旧 ID。交付应列出已审阅入口及保留旧缓存清理逻辑的理由（若存在）。

## 接收与进展

- 2026-11-19 16:50:15：高级开发 `member-b53c76acb705` 按 #592/#613 接收 `SG-20261119-T03-01`，方案修订 4。共享 `D:/SourceCodes/mywork/conflua` 的 `develop` / `613f6a5c1b4292b95babfa57017004ace4538174`；复算已接受 T01＋T02 的 71 路径联合指纹 `43234D6132B1FB30412AC5EAAB23D72AE9F20AF6A5322647DF0A1E692C2B681C` 一致。无开工阻塞。只改 Web、CLI 客户端、对应测试及仓库插件使用指引；服务端和 DDL 冻结，不部署或换库。消息失败恢复纳入本次交付；只运行定向正向和静态检查。
- 2026-11-19 17:03:47：完成 A05 客户端差异并复算 T01＋T02 输入指纹不变；冻结以下交付，候架构师登记及独立复核。

## 交付与审查

### 版本与实际差异

- `SG-20261119-T03-01`，方案修订 4；工作区 `D:/SourceCodes/mywork/conflua`，`develop` / `613f6a5c1b4292b95babfa57017004ace4538174` 的未暂存差异和未跟踪文件。T03 **36 路径**：`871CB3D7D6834F7A28C7B3DA643ECF924B794AECCA5EC97DC9B34F9AE6514F82`；T01＋T02＋T03 **107 路径**：`5A807188409428C9D285B1007C207F880F6E3B2EE5F5611ECAB5FBB167F629D9`。不含过程文档；总登记由主会话维护。
- T03 路径以 `git diff --name-only --no-renames HEAD -- web/src web/tests src/conflua/interfaces/client.py tests/unit/interfaces/test_cli_client.py plugins/conflua/skills/conflua/SKILL.md` 和同范围 `git ls-files --others --exclude-standard --` 的并集为准。联合路径再纳入 T02 记录的 `migrations/sqlite src/conflua tests/unit pyproject.toml uv.lock` 范围，去重后依 T02 规则计算：ordinal 排序，逐行 `SHA256 文件路径`（大写）或 `DELETED 文件路径`，UTF-8 无 BOM、LF 分隔且无末尾换行。联合范围排除 T03 后为原 71 路径 `43234D6132B1FB30412AC5EAAB23D72AE9F20AF6A5322647DF0A1E692C2B681C`。
- 跟踪文件用上述范围的 `git diff HEAD --` 审查，另读四个新文件 `web/src/domains/room/memberDisplayName.ts`、`web/src/domains/room/messagePublication.ts` 及 `web/tests/domains/room/` 下对应的两份 `.test.ts`。

| 验收项 | 实现与复验定位 |
| --- | --- |
| 发号及创建结果未知 | `channelApi.ts` 请求 `issue-id`；`useChannelCreation.ts` 和 `interfaces/client.py` 先领号再用原 ID 创建一次。领号失败不创建；创建结果未知保留原 ID，Web 查找按钮和 CLI `channel get` 只做 GET，不重建、不清理 worktree。仓库插件 `SKILL.md` 说明 MCP 的 `channel_issue_id`、`channel_create` 及按目录发现 ID。Web、CLI 正向 mocks 验证顺序和原 ID；未知结果测试已更新但未运行。 |
| 默认进入、固定人类与缓存 | `RoomSwitcher.vue` 和 `RoomPage.vue` 房间入口先加载频道列表，再选有效最近频道或 `isDefault`；频道删除后同样走房间入口。显式频道链接仍检查列表，不对旧链接做别名。`MemberPanel.vue`、`MemberIdentity.vue`、`MessageTimeline.vue` 和 `RoomComposer.vue` 的固定人类与引用显示基于 `kind`；测试覆盖不同房间默认 ID、有效最近频道和人类标签。`cacheStorageUpgrade.ts` 只迁移非资源的 UI 偏好键；旧草稿、旧频道选择、旧创建缓存不读、不改、不重新映射。 |
| 图片与时间 | `messageEditorCodec.ts` 识别规范 TSID 路径且校验当前房间/频道，图片文件标识不变；既有 `messageImageUploads.ts`、`roomApi.ts` 已用实际作用域。mock adapter 校验 multipart 路径和字节，编辑器单测验证 Markdown 标记解码与回显。`utils/time.ts` 未改，以 `Asia/Shanghai` 定向验证展示跨本地午夜及等价偏移；CLI 不新增时间文本入口、不转换现有 JSON。 |
| 消息失败及只读恢复 | `RoomPage.vue`、`RoomComposer.vue` 移除待确认横幅、核对控件、请求错误内联和恢复锁定；仅保留请求进行中防重复。`useRoomDraft.ts` 以独立键同步保存编辑内容，清空不会从发布快照复活正文。`messagePublication.ts` 按实际房间/频道/原发布编号 GET；发布请求失败用 toast，只有 GET 明确 `404 publication_not_found` 显示“未发现消息”，其余走查询错误。恢复不发 POST；用户可清空或显式发送，相同请求载荷复用编号、修改后才分配新发布编号。成功响应只清对应发布缓存，查到已保存记录会清该记录的缓存、不动草稿。正向单测验证 GET 不额外 POST、成功仅清对应频道缓存、草稿独立可编辑和清空不复活；故障分支留待另行运行。 |

### 实际检查

在 `web/` 执行以下定向正向命令，实际时区 `Asia/Shanghai`，最终 12 文件、21 通过、57 按名称跳过：

```powershell
$env:TZ = 'Asia/Shanghai'
node -p 'Intl.DateTimeFormat().resolvedOptions().timeZone'
corepack pnpm exec vitest run tests/domains/channel/channelRoutes.test.ts tests/domains/channel/useChannelCreation.test.ts tests/domains/channel/useChannelOrder.test.ts tests/domains/channel/useChannelArchive.test.ts tests/stores/channels.test.ts tests/domains/room/memberDisplayName.test.ts tests/domains/room/messagePublication.test.ts tests/domains/room/skillEditorModel.test.ts tests/domains/room/useRoomDraft.test.ts tests/services/channelApi.test.ts tests/services/roomApi.test.ts tests/i18n.test.ts -t 'uses explicit channel paths|separates non-default|issues the ID before|creates a worktree channel|discovers each room|uses the member kind|performs only a scoped read|clears only the matching|decodes and displays|restores an editable draft|clears sent content|groups equal instants|has matching keys|compiles every translation|issues a channel ID with|reads a publication using|uploads pasted image bytes|pins the default channel|restores each room.s order|confirms once, hides the archived'
```

- `web/`：`corepack pnpm typecheck` 通过；`corepack pnpm exec eslint @paths` 对变更 `.ts`/`.vue` 通过；`corepack pnpm exec prettier --check @paths` 对全部变更 Web 路径通过。`@paths` 取上述路径并集的 Web 子集，去掉 `web/` 前缀。早期类型检查的 Vitest 断言版本问题、格式差异及新增用例把查询 URL 写多 `/message` 已修正；修正后重新验证。
- 协调根：`uv run --locked --no-sync pytest -q tests/unit/interfaces/test_cli_client.py::test_channel_creation_issues_id_then_creates_with_same_id` 1 通过；`uv run --locked --no-sync mypy src/conflua/interfaces/client.py tests/unit/interfaces/test_cli_client.py` 通过（2 文件）；同两文件使用 `uv run --locked --no-sync ruff check`、`uv run --locked --no-sync ruff format --check` 均通过。`git diff --check` 通过。
- 未运行：频道创建丢失响应/拒绝、消息发布失败与错误查询分支、图片错误作用域的反向用例，以及全量、集成或浏览器端到端验证。默认频道路由转换及控件移除由源码和类型检查核对，页面运行时交互未实测。原 T02 全量三例未重跑。没有启动/切换服务或操作真实库、备份、外部会话及 Git 持久状态；未安装插件、未改 DDL 或后端发布事务、未开始 T04。当前交付不是部署，也不改变此前恢复的旧版开发服务。

### 同版复验与限定返工

- 2026-11-19 17:17:15：测试 #617 对 #615 的冻结版独立复验，36/107/71 路径指纹一致；Web 定向 21 通过、57 跳过，CLI 定向 1 通过，相关静态和离线 SQL 通过。主会话复算三组指纹相同，`git diff --check HEAD` 通过。反向、全量、集成和页面运行仍未验证。
- 裁决：确认 `recover` 成功只删除原发布编号、不处理原样草稿；之后用户再点发送，客户端会分配新编号，服务端可按新发布保存。这不是自动重发，但「已发布」和「仍待发送」同时出现，可能导致重复消息。该差异阻塞 T03 接受，退回 `running`，仍用 `SG-20261119-T03-01`、修订 4；属于既定成功清理语义的修正，不改变任务范围或依赖。
- 返工验收：同一房间、频道和发布编号的 GET 确认已保存时，按发送成功处理；清理对应发布缓存，只有草稿仍与原提交对应且未改动时才按普通成功发送的方式清理，不清空已编辑的正文、选题、提及、引用或能力选择，不恢复已清空草稿，不处理其他频道或更新的发布。以原提交快照为准，不能只比正文；注意表单原值与提交规范化的差异。查无消息仍由用户决定清理或继续发送，其他查询错误仍走 toast；不恢复按钮、横幅或锁定，不自动 POST，不调整事务或后台投递。
- 只解除 `web/src/domains/room/` 下 `messagePublication.ts`、`RoomPage.vue`、`RoomComposer.vue`、`useRoomDraft.ts`，对应的 `web/tests/domains/room/messagePublication.test.ts`、`web/tests/domains/room/useRoomDraft.test.ts` 和本 task 的冻结。其余 T03 差异及已接受的 71 路径保持不变。补充只读 GET 成功的隔离用例，分别证明清理原样草稿、保留已编辑草稿以及不额外 POST；运行这些正向用例和相关静态检查。重提前记录实际范围、新指纹与未运行项，再交测试同版复核。不扩大故障分支、全量、集成或浏览器测试授权，不部署、不换库或改变 Git 持久状态。
- 2026-11-19 17:19:08：高级开发按 #618 接续原分配 `SG-20261119-T03-01`、修订 4。共享 `develop` / `613f6a5c1b4292b95babfa57017004ace4538174` 上复算退回前 36/107/71 路径指纹均一致；T03 排除六个解冻代码和测试路径后，30 路径指纹为 `5F1B669E16D124281D6BF3395FE355C66E19C6DB3E0445A0321C6E60A83A14BA`。按上述边界返工，无开工阻塞。

### 返工交付

- 2026-11-19 17:25:16：`SG-20261119-T03-01`、修订 4，仍在共享 `develop` / `613f6a5c1b4292b95babfa57017004ace4538174`，返工差异冻结待复验。沿用上文路径与哈希规则：T03 36 路径 `8FB7A64690E4565B4C658B7A336D2221B72D5C1F31A47EA41DE0D4EC00906FB2`，联合 107 路径 `21B5A7F9EDA259BE2B016C18480EC4DF51828554A7088E07231F055FA037D736`。排除 T03 后上游 71 路径仍为 `43234D6132B1FB30412AC5EAAB23D72AE9F20AF6A5322647DF0A1E692C2B681C`；T03 排除解冻范围后的 30 路径仍为 `5F1B669E16D124281D6BF3395FE355C66E19C6DB3E0445A0321C6E60A83A14BA`。
- 实际返工仅涉及本记录及四个源码文件 `web/src/domains/room/{messagePublication.ts,RoomPage.vue,RoomComposer.vue,useRoomDraft.ts}`、两份测试 `web/tests/domains/room/{messagePublication.test.ts,useRoomDraft.test.ts}`；六路径子集指纹 `D5E1DDD70793BE0BA0DF8CCA7B0C48A5CF4FD336D5AB4DE341CC60547C407BC9`，无新增路径。
- 本段修正首版“查到已保存记录不动草稿”的行为：发送时单独保存未 trim 的表单快照，包含选题、接收人、内联提及、引用和能力选择，快照不进入 HTTP 载荷。GET 返回原发布编号、且原缓存仍匹配时，共用 POST 成功的清理逻辑：清对应发布缓存；仅原提交草稿仍匹配才清正文和引用等编辑内容，保留选题和接收路由。清理不重新提交或恢复正文；修改过的草稿、已清空草稿、其他频道草稿及更新的发布缓存均不被覆盖。旧缓存若没有原表单快照，不推断草稿仍匹配。编辑器重置只更新界面状态，不另写草稿。
- 查无与异常分支的 toast 语义、后台只读、无核对控件/横幅/恢复锁定保持不变。此次没有新增自动 POST，不改服务端事务、后台投递或 Schema。

在 `web/` 执行以下命令，定向 **12 通过、7 跳过**；覆盖原样草稿清理、正文/选题/提及/引用/能力和已清空草稿保留、原缓存被替换时不处理、其他频道不受影响、整个 GET 恢复流程不 POST，以及显式发送成功。

```powershell
$env:TZ = 'Asia/Shanghai'
corepack pnpm exec vitest run tests/domains/room/messagePublication.test.ts tests/domains/room/useRoomDraft.test.ts -t 'clears the unchanged original|preserves .* edited during successful lookup|leaves a replacement publication|clears only the matching publication|clears sent content|restores an editable draft'
$paths = @('src/domains/room/messagePublication.ts','src/domains/room/RoomPage.vue','src/domains/room/RoomComposer.vue','src/domains/room/useRoomDraft.ts','tests/domains/room/messagePublication.test.ts','tests/domains/room/useRoomDraft.test.ts')
corepack pnpm typecheck
corepack pnpm exec eslint @paths
corepack pnpm exec prettier --check @paths
```

- 类型检查、六路径 ESLint 与 Prettier 检查均通过；协调根 `git diff --check HEAD` 通过，索引无暂存。早期 lint 的未使用变量及格式检查提示已修正。
- 未重跑 #617 的原定向全组、CLI、离线 SQL；未执行反向、全量、集成、浏览器或真实会话测试，编辑器实际焦点及输入法交互未实测。未启动或切换服务、未操作真实库/备份、未暂存/提交/推送、未开始 T04。请主会话登记新版本并安排同版复验；本交付不代表验收通过或可部署。

### 返工版仲裁

- 2026-11-19 17:33:13：架构师依据 #622 的同版独立复验、主会话复算的五组指纹及实际差异，解除 #618 阻塞，登记 `SG-20261119-T03-01`（修订 4）为 `accepted`。GET 确认同一发布时，与 POST 成功共用按作用域和表单快照保护的清理；原样草稿清理，已编辑或已清空草稿、其他频道及更新的发布保持不变，无额外 POST。
- #622 实测 Web 正向 12 通过、7 跳过，类型与六路径 ESLint/Prettier 通过；主会话的 `git diff --check HEAD` 通过。#617 的 21 例、CLI 与离线 SQL 是首版复验记录，本次未重跑；404/查询错误仅审阅，反向、全量、集成、浏览器及真实会话均未执行。此次接受是客户端交付裁决，不构成整体 Verification、部署或换库授权。
