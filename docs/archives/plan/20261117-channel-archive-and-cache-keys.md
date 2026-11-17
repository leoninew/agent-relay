# Plan / 计划：频道归档
最后修改时间: 2026-11-17 14:59:37

## Review status / 审查状态

Accepted

## Intent basis / 意图依据

依据 [频道归档意图](../intent/20261117-channel-archive.md) 的 A01–A07。用户已授权记录后实施；本计划接受后直接开发并运行必要的开发检查。

## Technical decisions / 技术设计与决策

- Domain Channel 增加 `ChannelStatus` 枚举类型和默认 `active` 的 `status` 字段；TypeScript 使用对应联合类型。
- 新建 `0005_channel_status` 增量迁移，衔接合并后的 `0004_simplify_paths` / `simplify_paths_20261117`。只新增默认 `active` 的状态列，不增加 CHECK、外键等约束；枚举和默认频道规则在业务代码校验，不改原数据或删除列。
- 默认频道列表查询同时要求 `archived_at IS NULL` 和 `status = active`；按 ID 查询保留归档对象用于历史访问。前端 store 同样过滤状态，避免缓存、查询创建结果等入口重新把归档频道加入可选列表。
- 新增 `POST /api/room/{room_id}/channel/{channel_id}/archive`，返回更新后的 Channel。应用层沿用房间操作锁和短写事务；Repository 拒绝默认/已删除频道，只写状态、UTC 归档时间及必要变更事件，不调用删除逻辑。重复归档保留首次时间；对旧的已归档但时间缺失记录，在再次归档时补写。
- `archived_at` 同时用于历史删除标记。资源读取、worktree 目录占用判断和投递筛选结合 `status` 区分归档与历史删除，保留已归档频道历史和现有投递能力；活动频道带历史删除时间时仍然不可用。
- `openRoom` 调用 `channelsStore.load(roomId, true)`：每次进入项目都向服务端刷新频道列表，仍复用同一项目正在进行的请求，不取消频道选择和排序的本地保存。合并房间与频道路由参数监听，避免同次项目切换在新列表到达前使用旧列表打开频道。
- 既有 CLI/MCP `channel_archive` 客户端方法切换到 POST 归档接口；保留 DELETE 的原删除用途。
- ChannelBar 只为非当前、非默认的 active 频道渲染“归档”文字按钮，hover 或 focus-visible 时显示，不改变拖拽手柄和链接职责。
- 新增归档确认框和控制 composable，复用 AppDialog、AppButton。执行前重新核对房间、当前频道、目标状态和 busy；成功更新 store 并关闭确认框，失败显示归一化错误。切换房间/频道时关闭旧确认。

## Implementation steps / 实现步骤

1. 补齐状态模型、迁移、默认过滤与独立归档方法，检查归档不调用删除或资源清理逻辑，并通过业务测试覆盖默认频道限制；不编写迁移单元测试。
2. 接通 HTTP 与已有 CLI/MCP 客户端，补齐接口委派和请求路径测试。
3. 接入前端状态、store、hover 入口与确认交互，补齐状态过滤、资格复查、取消/成功/失败测试。
4. 运行项目现有检查，记录实际改动、结果和偏差；保持共享暂存区不变。

## Files to change / 需修改文件

- `src/conflua/domain/rooms/models/rooms.py`、`models/__init__.py`。
- `src/conflua/application/channels/ports.py`、`service.py`。
- `src/conflua/infrastructure/persistence/models.py`、`repositories/channels.py`、`migrations.py`。
- `src/conflua/infrastructure/persistence/repositories/_room_reads.py`、`repositories/deliveries.py`、`delivery_store.py`：补写归档时间后的历史读取、目录保留与投递可用性判断。
- `migrations/sqlite/versions/0005_channel_status.py`、对应 SQL、`migrations/README.md`。
- `src/conflua/interfaces/http/channels/routes.py`、`interfaces/client.py` 及仓库内 Conflua 使用说明。
- `web/src/services/channelApi.ts`、`stores/channels.ts`、频道列表/归档确认组件与 composable、`RoomPage.vue`、相关 CSS 和 i18n。
- 对应频道应用、接口、客户端和前端单元测试；不新增迁移单元测试，不恢复已删除的持久化测试目录。

## Tasks and coordination / 子任务与协调

不适用，不创建 task。高级开发在主会话串行负责实现和集成；已通知架构师避免并行修改频道文件。基线为 `56e4aa5` 加共享工作树中已完成的路径精简变更。既有暂存内容不变，本次不执行 Git 暂存或提交。

## Verification plan / 验证计划

- 后端：使用 `uv run --locked pytest tests/unit` 运行当前保留的业务测试，覆盖频道应用、HTTP、CLI/MCP；迁移单元测试不在运行范围。归档保留成员、消息、投递和目录的行为通过实际代码检查确认。
- 前端：使用 `corepack pnpm test` 运行频道归档、状态 store、API、排序和创建相关用例。
- 静态检查：项目已配置的 Mypy、Ruff/check-format、前端类型检查、受影响文件 ESLint/Prettier，以及 `git diff --check`。
- 按用户要求，不编写或运行数据迁移单元测试；不为测试归档真实业务频道。
- 整体 Verification 待用户授权；实施阶段记录上述开发检查的实际结果。

## Risks / blockers / assumptions / 风险 / 阻塞项 / 假设

- `archived_at` 历史字段原本代表删除，按本次补充也记录归档时间；结合 `status` 区分归档与历史删除，不把填写归档时间当作删除或停止现有投递。
- 当前选择只能在浏览器端确定，后端不虚构全局当前频道。窗口之间的选择可以不同。
- 共享暂存区已有路径改造，本次不能整文件暂存或回退共享文件。

## Rollback / recovery / 回滚 / 恢复

- 本次不提供降级迁移；新增列向前兼容。回退功能代码前应确保应用不会忽略已归档状态。
- 失败请求保留频道及确认目标，可取消或按幂等接口重试。

## User review notes / 用户审查记录

- 2026-11-17：按“记录后实施”授权接受本计划并进入 Implementation，无需重复阶段确认。
- 2026-11-17 14:01：按用户“不搞复杂的数据库约束”补充，移除新增 CHECK，只保留简单状态列与业务校验。
- 2026-11-17：按用户“不对数据迁移搞单元测试”补充，取消迁移专项测试安排；确认持久化测试目录已删除，保留删除现状。
- 2026-11-17：按用户反馈修复归档时间缺失和项目切换不请求频道；同时核对现有缓存与刷新策略，不扩大为全站缓存改造。

## Implementation progress / 实施进展

- 2026-11-17 13:56:45：完成仓库调查及意图、计划记录，进入实现；尚未变更产品代码。
- 2026-11-17 14:27:25：完成频道状态、默认列表过滤、独立 POST 归档接口及 CLI/MCP 接入。迁移为 `0005_channel_status`，只执行 `ALTER TABLE channels ADD COLUMN status TEXT NOT NULL DEFAULT 'active'`，不新增 CHECK、外键或关联约束。
- 前端已实现非当前、非默认频道的 hover/focus 归档入口、确认框、资格复查、取消、成功隐藏和失败反馈；切换房间或频道时关闭旧确认。
- 按最新要求，不保留数据迁移单元测试；确认 `tests/unit/infrastructure/persistence` 已删除，未恢复目录或新增替代测试。归档保留资源的检查限于代码检查：归档方法只更新状态和必要事件，不调用删除或清理逻辑。
- 本次重新运行 `uv run --locked pytest tests/unit`：431 项通过，不含迁移单元测试；`git diff --check` 通过。
- 此前前端全量 `corepack pnpm test`：205 项通过；Mypy、Ruff/格式、前端 app/node 类型检查及改动范围 ESLint/Prettier 均通过。本次仅同步测试范围和文档，未重复这些检查。
- 未在真实频道执行归档，未完成浏览器中的 hover/确认交互实操；交互行为已有前端单元测试。当前仍处于 Implementation，未进入整体 Verification，未暂存或提交本次变更。
- 2026-11-17 14:59:37：补写归档时间及重复归档保护，资源可用性结合状态判断；项目切换强制刷新频道并合并路由监听，补充前端缓存刷新与失效选择回归用例。
- 本轮开发检查：后端 `uv run --locked pytest tests/unit` 431 项通过；前端 `corepack pnpm test` 30 个文件、206 项通过；`uv run --locked mypy src tests` 206 个源文件通过；改动范围 Ruff/format、前端 app 类型检查、ESLint、Prettier 和 `git diff --check` 通过。
- 使用内存 SQLite 和当前 ORM schema 进行一次归档业务检查：UTC 时间写入、重复请求保留时间且不新增事件、缺失时间记录补写、默认列表过滤、成员和消息保留、归档后投递认领和激活、默认/历史删除频道限制均通过。未执行迁移，不新增迁移单元测试，不恢复持久化测试目录，不归档真实业务频道。
- 已按追加要求核对现有缓存业务、键名与刷新方式，交付中列明：项目/频道列表、频道快照、技能目录、KeepAlive、排序/选择/面板本地保存、草稿及待确认请求、后端配置和图片 HTTP 缓存。项目列表仍保留原有首次加载后复用策略，本次未扩大其刷新范围。

---

# Plan / 计划：统一频道缓存键
最后修改时间: 2026-11-17 17:24:34

## Review status / 审查状态

Accepted

## Intent basis / 意图依据

依据 [统一频道缓存键](../intent/20261117-channel-cache-keys.md)，按用户授权记录后继续实施。

## Technical decisions / 技术设计

- `web/src/services/cacheKeys.ts` 是唯一键生成入口，统一 app、room 和 channel 范围及资源后缀；内存快照和草稿上下文共享频道范围，持久化资源使用明确后缀。
- 频道列表的值、加载标记、错误和请求合并使用同一个房间频道列表键；最近选择使用房间导航键。
- 频道创建确认显式接收发起频道；技能目录只用频道资源键，路径变化通过缓存上下文失效，不把路径拼进缓存键。
- KeepAlive 使用频道范围作页面键；项目列表取消已加载提前返回，保留进行中的请求合并。
- `cacheStorageUpgrade.ts` 在应用挂载前一次性转存旧浏览器键；业务调用方只读写统一新键。不涉及数据库迁移。
- 删除项目成功后，使用统一房间前缀清理所有频道快照、版本、localStorage/sessionStorage 业务缓存和房间导航状态，重置频道列表及请求；项目更新同步各频道快照中的房间信息。
- 频道列表请求以其 AbortController 身份确认有效性，失效请求不写回响应、错误和加载状态，也不移除后来发起的请求。

## Steps and checks / 实施与检查

1. 集中键生成并接通内存、localStorage、sessionStorage 和页面实例。
2. 保留旧浏览器数据，修正调用方及测试中的旧键。
3. 使用项目现有前端测试、app/node 类型检查、ESLint/Prettier 和差异检查。
4. 记录实际结果和统一键清单；不编写迁移单元测试，不暂存或提交。

## Coordination / 协调

高级开发串行实施。基线为 `1e01946`，共享文件中的路径编辑及精确查询已提交并保留。本轮只改缓存范围的存储清理、rooms/channels store 和必要单测，不修改 roomApi.ts。架构师按 0427 整理其他过程文档，只读取本任务的意图与计划。

## Risks and recovery / 风险与恢复

- 浏览器存储不可用时，不阻止应用启动；转存成功前不删除旧数据。
- 旧创建确认记录缺少发起频道，使用该房间最近频道，缺少最近选择时衔接默认频道。
- 不回退已转存的键格式；回退代码前需保留浏览器存储，避免丢失未确认请求。
- 删除接口失败时保留全部缓存；成功后浏览器存储不可用不阻断内存清理及项目移除。清理严格使用带冒号边界的房间前缀，保留其他房间和 app 偏好。
- Implementation 已完成，整体 Verification 未单独启动。

## Implementation progress / 实施进展

### 已提交基线与本轮交付

- `1e01946` 已包含集中键入口、全部调用方、启动转存、频道 KeepAlive、项目列表重新查询、创建确认来源频道和技能缓存失效逻辑。文档仍留在工作区，依据 0424 继续实施，核对后复用这些实现。
- 本轮新增 `web/src/services/cacheStorage.ts`，按统一房间前缀清理浏览器存储，不再依赖内存快照枚举已打开频道；因此未打开频道的草稿、待确认发送/创建和排序也能清理。
- `stores/rooms.ts` 删除成功后重置房间的频道列表及请求、内存快照和版本，并执行持久化清理；失败时保留原状态。
- `stores/channels.ts` 对响应、错误和 finally 都增加请求身份检查，避免 reset 后恢复缓存或修改新请求状态。
- 将 rooms 单测中旧的草稿删除 mock 改为真实存储替身；新增删除完整范围的轻量用例，覆盖未打开频道、相似房间 ID、其他房间及全局偏好保留；失败删除用例检查草稿仍在。
- 开发检查：相关 5 文件 45 项通过；`corepack pnpm test --silent=false` 全量 31 文件 216 项通过，输出无警告；app/node 显式 `vue-tsc --project ... --noEmit`、全量 `corepack pnpm lint`、4 个受影响实现/测试文件 Prettier 及 `git diff --check` 通过。
- 旧前缀扫描确认业务代码仅在启动转存入口识别旧键。未增加或执行迁移单元测试、复杂竞态测试、浏览器操作或后端检查；本轮无后端修改。
- 本轮交付为 4 个实现/测试文件和本任务的意图、计划；频道归档两份文档未改，未暂存或提交，暂存区保持为空。Implementation 已完成，整体 Verification 未另行启动。

## Cache key inventory / 缓存键清单

`R = conflua:room:{roomId}`，`C = {R}:channel:{channelId}`；ID 由生成入口分段编码。

| 业务 | 键 | 存储与范围 |
| --- | --- | --- |
| 频道快照、编辑上下文、页面实例 | `C` | 独立内存容器按同一频道范围定位；页面最多保留一个实例 |
| 消息草稿 | `C:draft` | sessionStorage |
| 待确认发送 | `C:publication` | sessionStorage |
| 待确认频道创建 | `C:channel-creation` | sessionStorage；C 是发起创建的频道 |
| 技能目录 | `C:skills` | 内存；60 秒复用，路径变化失效 |
| 话题排序 | `C:topics-order` | localStorage |
| 成员排序 | `C:members-order` | localStorage |
| 频道列表及其请求状态 | `R:channels` | 内存；切回项目强制刷新 |
| 频道列表顺序 | `R:channels-order` | localStorage，房间导航偏好 |
| 最近选中频道 | `R:selected-channel` | localStorage 与内存，房间导航偏好 |
| 项目排序 | `conflua:app:rooms-order` | localStorage，全局偏好 |
| 面板折叠 | `conflua:app:panels` | localStorage，全局偏好 |

项目列表不再使用已加载响应缓存。后端配置缓存和图片 HTTP 缓存沿用原有机制，不由前端键生成器管理。
