# Plan / 计划：聊天室 Skill 与 MCP 引用

最后修改时间: 2026-11-12 08:16:13

## Review status / 审查状态

Accepted

用户已接受本计划及 task 方案，授权 Implementation。最新指令取消聊天室协作，开发任务全部收回本窗口；保留已有代码和历史交付，不再向聊天室派发或发送交叉确认。

执行状态：T01–T04 完成并接受，用户界面验收通过；最终验证及修复记录见 `docs/verification/20261111-chat-skill-mcp.md`。

## Intent basis / 意图依据

- 依据 [意图](../intent/20261111-chat-skill-mcp.md) A01–A07 及用户消息 `room-94f73433cde7-msg-0098`：Skill 候选由 `$` 触发，非 `/`。
- 不复用 `20261110-mcp-skill-alignment` 任务状态；该计划已处理 CLI/MCP 队列、上下文 Skill 和投递头部，未包含聊天室能力选择。
- 记录基线为 `cf901ed`；派发时重新核对 HEAD、实际工作区及修改文件，不据此覆盖已有未提交修改。

## Technical decisions / 技术设计与决策

### 1. 目录发现与 HTTP 边界

- 新增 application 能力查询用例及窄端口，Codex driver 负责 `skills/list` 与 `mcpServerStatus/list` 协议解码；HTTP route 只调用 application 契约。
- `GET /api/room/{room_id}/skills?force_reload=false` 读取聊天室项目目录 Skill。`Room.project_path` 为作用域；`MemberService.add` 已要求目标 session CWD 与此目录一致。查询 RPC 放在任何数据库事务之外。可缓存同一规范化项目目录的并发查询；用户手动刷新才请求 `forceReload=true`。
- `GET /api/room/{room_id}/member/{member_id}/mcp` 保留已有后端契约；按最新要求，聊天前端移除该请求和对应候选展示。
- 对 web 仅返回稳定 opaque ID、类型、显示名、摘要、来源/服务器和可用状态；绝不返回绝对 Skill path、access token、环境变量或原始认证数据。MCP 工具清单可用于列表描述，但引用首期为 MCP server。
- 前端 Skill 目录具有加载中/就绪/部分失败/失败状态。`$` 输入只在缓存目录就绪后本地过滤；提供明确刷新，RPC/daemon 失败不阻断正文和不含能力的消息。

### 2. `$` 候选与接收对象

- RoomComposer 监听当前 textarea 选择范围，按光标所在词识别 `$query`；跳过 IME composing；避免全局搜索/普通 `$` 正文误触发。正文与引用通过一次草稿更新写入，`AppInput` 只读取和恢复 selection。
- Skill 目录在成员共用项目 CWD 中按房间预加载；切换话题、成员或绑定会话不触发 MCP 查询，刷新也只加载 Skill。
- 候选仅含 Skill，键盘上下移动；Enter/Tab 选择，Esc 关闭。弹层打开时拦截 Enter，避免同时触发表单 submit。IME Enter、Shift+Enter 保持既有行为。
- 选择将正在编辑的 `$query` 替换成可移除的消息引用标签，不把查询字符串伪装为普通正文或调用结果；可连续选择多个能力。`@` 成员路由、`#` 话题路由原样保留。
- 不加入自由格式 `/` command、不改模型命令或现有 markdown 渲染，不新增前端依赖；按钮/标签图标从 `@lucide/vue` 中选择。

### 3. 消息引用、持久化与兼容

- CreateMessage/Message/ContextMessage 与 TS draft 增加可选、带 discriminator 的 capability references，支持 `skill` 与 `mcp_server` 类型。字段保存稳定 ID 和展示快照，不接受调用方自带 native path 或凭据；旧请求默认为空。
- 领域 Message 冻结 refs，publication replay 等同性比较规范化能力 ID 集；相同 publicationId 更改 refs 必须 conflict。Room snapshot、message page、context 和 storage 映射完整往返。
- 在 SQL-first Alembic schema 的 `messages` 行增加 `capabilities` JSON 数组列，并同步 SQLAlchemy type/mapper/queries；消息与 refs 在原有写事务中一次提交。引用只依附单条消息，不建立独立关系表。增加可前滚迁移、旧消息空数组兼容和持久化往返验证，不改已有消息含义。
- 用户明确授权就地合并未发布的 0002/0003，现只保留 `0002_capabilities_json`，直接从基线增加消息 JSON 列，不创建中间关系表。最终 head 保持 `capabilities_json_20261111`，已修复至该版本的开发库不需重复迁移或修改版本记录。
- 原文文本与引用列表保持独立。Message 提交、重试、未知结果 publication lookup、sessionStorage pending request 保留完全一致的 references。CLI/MCP client 未传此可选字段仍向后兼容。

### 4. 投递与协议映射

- QueueDriver 使用 typed request（现有 envelope text + typed refs）而不是携带 native dict；`DeliveryService` 传递已保存 refs，application 不引入 FastAPI、SQLAlchemy 或 app-server 结构。
- 每个 frozen target session 的 adapter 单独解析 refs：以当前 cwd/skills/list 将稳定 Skill ID 解析成准确 `name/path`；解析缺失、禁用或歧义在 `thread/queue/add` 前形成确定的 QueueRejected，不能静默降级。强制 Relay Skill 仍每次按目标会话验证并仅注入一次。
- MCP server 必须在目标 `mcpServerStatus/list` 结果中确认可用，再以 `type=mention, path=mcp://<server>` 投递。MCP server 不转成指定 function call；Agent 是否调用工具仍依赖请求语义、目标会话策略与授权。
- 协议查询 RPC 和队列 RPC 均在本地数据库事务外执行。`queue/add` 确定拒绝仍存 rejected；发起后回执未知继续保持 unknown、复核原请求且禁止自动重投；输入接收与单次队列激活语义不变。

## Implementation steps / 实施步骤

1. T01：完成带类型的 Skill 与目标 MCP 能力发现 application contract、Codex adapter 查询以及 HTTP route，并验证 scope、错误、分页及敏感字段边界。
2. T02：完成消息引用领域/接口契约、replay 比较、持久化 Alembic 迁移及 context/history 映射。
3. T03：消费 T01/T02 接口，实现仅含 Skill 的 `$` 搜索/选择、房间 Skill 预加载、pending 草稿和弹层无障碍交互。
4. T04：扩展 delivery port 和 Codex adapter，将 refs 映射到原生 inputs；保留必需 Skill、分类确定拒绝/unknown 并验证原队列不重投。
5. 集成前置结果，运行针对测试、后端与前端质量门禁、迁移验证；形成各 task 交付后再审查并进入整体 Verification。

## Files to change / 修改范围

- 后端：`src/agent_relay/application/` 新能力查询用例和消息/投递契约；`src/agent_relay/domain/rooms/` 消息模型及 publication replay；`src/agent_relay/infrastructure/codex/driver.py`；`src/agent_relay/infrastructure/persistence/` models/mappers/queries/repositories；Alembic migrations；`src/agent_relay/interfaces/http/` 能力 routes/dependencies。
- 前端：`web/src/services/roomApi.ts`、`web/src/components/AppInput.vue`、`web/src/domains/room/RoomComposer.vue`、`web/src/domains/room/RoomPage.vue`、消息展示/局部样式及相邻测试。
- 测试：按用户最新要求只保留轻量单层单测及请求契约；不新增真实 SQLite、跨层集成或前端 UI 测试，不恢复用户删除的测试及支持目录。
- Scope 不包含修改其他 Agent 现有 RoomSwitcher 排序/拖拽实现、环境文件、现存共享导航变更、CLI/MCP 目录工具、安装器或用户 Codex 缓存。

## Tasks and coordination / 子任务与协调

### Coordination / 协调信息

- 方案修订：6。修订 2 简化存储，修订 3 修复开发库，修订 4 收紧测试边界，修订 5 将 `$` 候选收紧为 Skill；修订 6 合并未发布迁移，并清除依赖已删除 support 的集成脚手架，恢复全量类型检查。
- 权威协调根：`D:\SourceCodes\mywork\agent-relay`（任务及执行者必须可读取的共享工作区）。
- 执行与审查：全部收回当前窗口，外部执行分配停止；T01 复核及后续 T03/T04 由本窗口按依赖推进。
- 阶段授权：用户消息 `room-94f73433cde7-msg-0101` 授权高级开发协作、任务分配与交付审查，覆盖已接受意图/计划中的 Implementation；不授权 Git 暂存、提交、部署或真实 Codex 队列操作。主会话负责唯一分配、审查和依赖放行。
- 通信约定：按用户最新“取消聊天室协作，开发任务在本窗口收回，盘点任务进展”执行；进展仅在本窗口与开发记录中更新，不再使用聊天室协作。

### Task definitions / 任务定义表

| ID  | 任务文档                                                        | 直接前置任务与要求                                                    | 预期交付与验收                                                                                      | 意图验收归属            |
| --- | --------------------------------------------------------------- | --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | ----------------------- |
| T01 | `docs/task/20261111-chat-skill-mcp/T01-capability-discovery.md` | 无；按本计划固定 API、opaque ID 及每 session MCP scope                | Codex 目录 adapter + application/HTTP 查询；通过 RPC fixture/HTTP 边界与敏感信息检查                | A02、A03                |
| T02 | `docs/task/20261111-chat-skill-mcp/T02-message-references.md`   | 无；消息 discriminator、refs identity 与 JSON 表示按本计划固定         | API/domain/JSON persistence/context/replay 与 Alembic 往返；兼容旧客户端                              | A04                     |
| T03 | `docs/task/20261111-chat-skill-mcp/T03-dollar-picker.md`        | T01 接受目录 response API；T02 接受消息引用 contract                  | 房间 Skill 预加载、仅含 Skill 的 `$` picker、持久草稿 UI 与 targeted front-end checks | A01、A02、A03、A04、A06 |
| T04 | `docs/task/20261111-chat-skill-mcp/T04-native-delivery.md`      | T01 接受能力 adapter mapping；T02 接受 Message refs 与 replay/storage | QueueDriver typed request、Skill/MCP 原生 items、定拒绝与 unknown/no-resend 验证                    | A05、A06、A07           |

### Execution registry / 执行登记表

| ID  | 执行状态   | 执行者                           | 分配编号             | 工作基线 / 交付位置                                                                                                  | 仲裁结论 / 当前阻塞                                                               |
| --- | ---------- | -------------------------------- | -------------------- | -------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| T01 | accepted | 本窗口 | 原 `AR-20261111-T01-01` 仅作历史 | 当前工作区；catalog SHA-256 `759cae0abac7a1412507f59e0cccb200b097a77a8b1ac7a02b0be5107ab97875` | typed DTO、目录范围、分页、错误与 opaque ID 已复核，纳入最终后端单测和源码检查 |
| T02 | accepted | 本窗口 | `AR-20261111-T02-02` | `0002_capabilities_json`；head `capabilities_json_20261111` | JSON 存储、开发库修复及未发布迁移合并完成，离线 SQL 核对通过 |
| T03 | accepted | 本窗口 | 本地 T03 | 当前 RoomComposer/useRoomCapabilities/API/tags 工作区 | `$` 仅含 Skill，前端 MCP 查询已移除；轻量单测、build/lint/格式通过，用户界面验收通过 |
| T04 | accepted | 本窗口 | 本地 T04 | 当前 delivery ports/service、Codex driver 与单测工作区 | support 依赖和失效集成脚手架已清理；177 项后端单测、140 files 类型检查及全仓 lint/格式通过 |

### DAG and integration / DAG 与集成

T01 与 T02 可并行；二者分别拥有 capability discovery/driver list 与 message domain/persistence/contracts 文件。T03、T04 均等待 T01、T02 接受且契约版本有效；T03 独占前端文件，T04 独占 delivery service/port 与 Codex enqueue 投递方法。T01 与 T04 都会编辑 `infrastructure/codex/driver.py`，必须在 T01 接受后才交付 T04，且 T04 按实际 T01 diff 增量修改。主会话负责协调不并行改写同一 driver 文件。

合法 DAG：`T01 → T03`、`T01 → T04`、`T02 → T03`、`T02 → T04`。首批并行 T01/T02；第二批并行 T03/T04（受 T01/T02 接受门槛）。两者验收后由主会话按 T03 UI wire format、T04 queue input 与实际 snapshot 统合。

### Assignment history / 分配历史

| 时间                | ID  | 分配编号             | 执行者                           | 动作与依据                                                              |
| ------------------- | --- | -------------------- | -------------------------------- | ----------------------------------------------------------------------- |
| 2026-11-11 21:04:30 | T01 | `AR-20261111-T01-01` | 高级开发 (`member-2e38db1d3525`) | 用户消息 `room-94f73433cde7-msg-0101` 授权；派发第一批能力目录发现      |
| 2026-11-11 21:04:30 | T02 | `AR-20261111-T02-01` | 高级开发 (`member-2e38db1d3525`) | 用户消息 `room-94f73433cde7-msg-0101` 授权；派发第一批消息引用与持久化  |
| 2026-11-11 21:46:18 | T02 | `AR-20261111-T02-02` | 架构师 (`member-7aa1d81461b2`)   | 用户追问确认现有存储需要纠正，原执行者已被用户打断；修订 2 改为消息 JSON 数组列，保持 message/API/domain 契约 |

## Verification plan / 检查与验证安排

- 后端：只新增目录转换、消息契约/重放、delivery service 与 Codex adapter 的单层单测，以替身代替 RPC/仓储；禁止真实 SQLite、跨层测试及能由单测覆盖的新增集成测试。不恢复用户删除的测试。
- 前端：只保留目录逻辑和 API 请求单测，不新增或运行浏览器、整页、集成、UI 或秒级测试；实际交互由用户验收。
- 源码检查：mypy、Ruff、前端类型、lint、变更文件格式与生产 build。测试结果仅记录当前实际执行事实；已有历史迁移/集成结果不作为当前仍存在的测试承诺。
- 开发库修复已经在先前明确授权下完成；本轮不再将开发库用于测试，不操作真实会话队列或用户插件缓存。

## Risks and recovery / 风险与恢复

- 保持每项 native queue write 与 DB transaction 解耦；新增能力查询不得持有 request-bound SQLAlchemy session。
- 消息写入包含 refs，任一步骤失败回滚；迁移仅增加消息列、不创建独立引用表，也不更改现存消息或投递状态。
- T01–T04 已交付并接受；最终审查基线为 HEAD `10cbb78045d0d7dd09cf197d36007af01df8fb11` 上的未提交工作区，保留用户已有删除和其他共享修改。
- API 目录预载失败时不影响非能力消息；存储引用的目录过期时各 recipient 清楚地呈现确定拒绝，不允许误标 unknown 或静默 fallback。

## User review notes / 用户审查记录

- 2026-11-11：按用户消息 `room-94f73433cde7-msg-0101` 接受完整意图、计划及四项 task 方案，授权 Implementation、主会话管理分配与审查。高级开发已有效接收 T01/T02（回报 `room-94f73433cde7-msg-0106`），两项处于 running；T03/T04 等待前置交付并通过主会话审查后再放行。
- 2026-11-11 21:27：主会话预审发现并反馈引用去重顺序问题（`room-94f73433cde7-msg-0108`），修正已进入当前工作区。独立运行 39 项相关单测及 38 项 HTTP/persistence/Codex 集成测试全部通过（结果同步 `room-94f73433cde7-msg-0109`）；完整集成命令使用 `pytest -o addopts=`，避免仅按 `integration` marker 运行而漏查未标记的集成测试。本次为实施中预审，不代替正式交付接受。
- 2026-11-11 21:34：已读取高级开发进展 `room-94f73433cde7-msg-0110`，两项仍为 running，尚无完整交付记录。主会话另核对 mypy 162 files、web typecheck/roomApi 格式通过；Ruff 发现新增 HTTP 测试两处 E501，已反馈 `room-94f73433cde7-msg-0111`。独立本机 schema 导出及 `_local` 目录 fixture 复现了 MCP 名称首字符限制导致整页失败的问题，已反馈 `room-94f73433cde7-msg-0113`；修复及目录→ref 往返复查前不接受 T01/T02，不放行 T03/T04。未重复投递上述消息，后续按批次审查完整交付。
- 2026-11-11 21:46：用户追问确认现有过度拆表的持久化表示需要纠正，并已人工打断高级开发。主会话接管 T02 修订 2：消息 refs 改存在 `messages.capabilities` JSON 数组列；公共请求、domain typed refs、replay 语义、顺序和消息事务保持不变。修订 1 关系表方案不作为下游交付；迁移验证使用临时 SQLite，未操作真实数据库。
- 2026-11-11 22:06：按用户要求先修复开发库。新增前滚迁移并完成独立事务失败回滚演练、备份迁移和数据核对；开发服务自动迁移至 `capabilities_json_20261111`，迁移前 153 条消息及引用全部保留，完整性与外键检查通过，真实消息 GET 返回 200。最终 265 项后端测试、mypy（162 files）、Ruff lint/format（246 files）及 diff 检查通过。用户取消聊天室协作，所有后续任务由本窗口处理；T03/T04 尚未实施。
- 2026-11-11 22:43：T03/T04 功能接线完成。遵照最新测试限制，移除本轮新增 UI 测试和可由 adapter 单测覆盖的目录集成用例；保留用户删除结果。前端 15 项轻量单测、类型/build/格式通过；后端源码 mypy 105 files、Ruff 通过。测试支持目录被删除后，当前后端全量单测有 8 个模块因引用 support 无法收集，未恢复或绕过删除。界面由用户自行验收。
- 2026-11-11 22:51：修复 T03 受控草稿连续更新覆盖引用的问题，选择能力时将正文与引用一次性写入 draft，再恢复光标。前端类型、变更组件 lint/格式及 diff 检查通过；未新增或运行 UI 测试。
- 2026-11-11 22:55：按最新要求移除前端 MCP 查询、缓存、候选和提示，`$` 只展示 Skill。目录逻辑及 API 共 13 项轻量单测通过（17ms，总运行 841ms），类型/lint/格式通过；未运行 UI 测试。
- 2026-11-12 08:06：按用户要求清理单测，8 个模块移除失效 support 依赖，改用局部端口 Mock/fixture，拆开跨服务用例并将投递状态规则移至领域单测。后端 177 项单测通过（1.50s），mypy src tests/unit（137 files）、单测 Ruff lint/format（32 files）及 diff 检查通过；T04 接受。用户删除结果保持，未运行真实 SQLite、跨层或界面测试；界面由用户验收。
- 2026-11-12 08:16：用户确认界面无问题并要求合并未推送的 0002/0003，已改为单份 0002 JSON 列迁移，保持最终 head。清除剩余 4 份失效集成脚手架及 marker，原 `mypy src tests` 范围恢复有效；含迁移的 140 files 类型检查、177 项单测、全仓 Ruff、前端 lint/格式/build 及 Alembic 离线核对通过。完成整体 Verification，未连接数据库或操作真实会话队列。
