# Task / 子任务 T02：消息能力引用

最后修改时间: 2026-11-12 08:16:13

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：`docs/intent/20261111-chat-skill-mcp.md`。
- 权威总计划：`D:\SourceCodes\mywork\agent-relay\docs\plan\20261111-chat-skill-mcp.md`；任务 ID：T02；方案修订：4（合并未发布迁移）。

## Goal and acceptance / 目标与验收

- 将 Skill 和 MCP server 选择作为可验证、可重放、持久化的消息事实完整贯通 contract、domain、database、response 和 agent context，对应意图 A04。
- `capabilities` 按 discriminator 区分 skill / mcp_server，各引用用稳定 opaque ID 加 UI 展示快照；客户端不能提交 native Skill 路径、server wire payload 或凭据。
- CreateMessage、Message、MessagePage、RoomSnapshot、ContextMessage、message history 与未决请求恢复均往返同一引用。旧客户端/旧消息缺失字段时等效空集合。
- 重复 publication ID 对内容、topic、recipients、reply 和规范化 capability ID 集逐项比较；不同引用的重放必须 conflict，同一集合顺序差异不误判为不同意图。
- SQL-first Alembic 增量迁移在 `messages` 增加受约束的 `capabilities` JSON 数组列；ORM type、mapper 和 message/context 查询直接读写该列。refs 随消息同行并在原有写事务保存，不建单独关系表；旧消息默认为 `[]`。

## Scope and files / 范围与文件

- 修改 `src/agent_relay/application/messages/`、`application/context/`、`domain/rooms/models.py`、`domain/rooms/rules.py`。
- 修改 `src/agent_relay/infrastructure/persistence/` models/types/mappers/repositories/queries 和 `migrations/versions/`。
- 更新 `src/agent_relay/interfaces/http/` 的 message/context Pydantic contract 和相邻单测；更新 `web/src/services/roomApi.ts` 的共享发布类型。迁移只作离线 SQL 核对，不运行真实 SQLite 或跨层测试。
- 独占 message refs 及持久化 schema；不实现 Capability catalog query service、UI picker 样式、Codex native queue translation 或 README。

## Inputs / 输入

- 无前置 task；ID discriminator、缺省兼容和 replay 集合等同性按总计划第 3 节。
- T03 依赖本 task 接受后的 TS CreateMessage/Message/Draft refs 类型；T04 依赖 Python domain `Message.capabilities` 和原子仓储 contract。
- 当前 MessageRecord 将 topics/mentions/recipients 分成关系表；迁移必须沿现有 SQL-first Alembic/ORM patterns 实现。

## Technical decisions / 技术设计

- refs 为独立消息字段，不从正文 `$name` 反向推断；UI display text 可更新但 ID 表示执行身份。任意绝对路径只由 server-side query/driver resolver 持有。
- 发布时以稳定顺序规范化去重；domain replay比较无序ID集合，保存/显示稳定选择顺序。不得使用跨平台本地路径暴露 identity。
- refs 是消息内的有序 JSON 数组，由现有领域类型校验及规范化；不把外部能力目录快照建模为数据库实体或外键。
- 在 `messages` 增加非空 JSON 数组列并为旧行提供 `[]` 默认值；SQLAlchemy 类型负责 JSON 序列化/反序列化为强类型 refs。message 与 refs 在现有 repository insert/事务中一次提交。
- Message/context/history/read views 从 MessageRecord 直接获得 refs；不为该字段增加 join、额外查询、关系表主键、position 列或 room-delete 清理项。
- 新 migration 约束 JSON 为合法数组；通过 Alembic history/heads 和离线 SQL 核对连接关系、默认值及约束。
- 用户明确授权就地合并未发布的 0002/0003，现仅保留 `0002_capabilities_json`，直接从 `queue_deleted_20261110` 增加消息 JSON 列；最终 revision 仍为 `capabilities_json_20261111`，已到该 head 的开发库无需改版本或重跑迁移。

## Implementation outline / 实施安排

1. 定义强类型 capability discriminator、Skill 与 MCP server ref、消息 read/write/context contract 和缺省空列表。
2. domain builder 冻结 references；发布 replay equality 对 references 进行严格类型/ID/归一化校验。
3. 新建增量 Alembic revision 增加 `messages.capabilities` JSON 列；message insert、mapper、history 和 context projection 同行读写 refs。
4. 为 history/publish/publication lookup/context 所有入口序列化字段，保证 sessionStorage pending request 原样回放。
5. 完成消息契约、规范化、publication replay 等单层单测及离线迁移核对，并提供契约给 T03/T04。

## Checks and risks / 检查与风险

- 消息应用与 domain 单测覆盖非法/重复 refs、保序去重、同 ID 不同类型冲突、引用集合无序重放及 publication lookup；仓储和驱动使用替身。
- 源码核对消息及引用沿原事务同行保存、旧消息默认空数组；迁移通过离线 SQL 核对，不恢复已删除的数据库或 HTTP 集成测试。
- 前端待提交正文和 sessionStorage pending publication 必须含 capability references；切换到错误 ref 不能复用原 publicationId。
- 不在 repository 内调用 Codex RPC；RPC resolver 与 queue 由 T01/T04 管理。

## Handoff basis / 交接依据

- 协议入口：`C:\Users\leon\.codex\plugins\cache\specflow-local\specflow\0.2.1\skills\specflow\SKILL.md` 与同目录下的 `references\task-coordination.md`。
- 分配与授权：用户消息 `room-94f73433cde7-msg-0101` 授权本计划范围内实施并审查；分配编号 `AR-20261111-T02-01`；总计划 registry 是权威记录。
- 工作区与基线：`D:\SourceCodes\mywork\agent-relay`，源基线 `cf901ed`，另有同一工作区的 SpecFlow 接受/分配记录及未提交导航修改。执行者接收时核对实际 HEAD/status 和 task 文档，不覆盖非本 task 文件。
- 可写回报位置：本文 Reception/progress 和 Delivery/review；主会话读取 task 和实际 diff。
- 回报渠道：Agent Relay 对架构师（主会话）直接回报，并更新本 task Reception/Delivery 章节。

## Reception and progress / 接收与进展

- 接收：高级开发已核对并接收 `AR-20261111-T02-01`，方案修订 1，父意图、计划及 task 均为 Accepted；无前置 task。有效代码基线为 `cf901ed6fa1fb02e6ebdffe2be57cb29ba6ae8ce`，叠加当前已接受 SpecFlow 文档工作区快照。
- 授权：主会话派发消息 `room-94f73433cde7-msg-0105` 及其引用的用户消息 `...msg-0101`；权限限于 T02 实施及必要开发检查。后者单条消息不在本成员查阅范围内，以主会话引用及权威计划授权记录为依据。
- 范围：仅消息/上下文引用契约、领域 replay、SQL-first 增量迁移及原子持久化、相邻测试和 `web/src/services/roomApi.ts` 共享类型。保留当前导航/侧栏排序与样式未提交修改；不启动 T03/T04、不提交 Git、不操作真实 Codex 队列/会话。

| 时间                | 分配编号 / 执行者               | 接收、进展或阻塞                                                                                                                                                    | 证据 / 回报位置                                                                                                   |
| ------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| 2026-11-11 21:05:22 | `AR-20261111-T02-01` / 高级开发 | 已核对 HEAD/status、修订 1、授权和无前置依赖，接收有效；开始实施                                                                                                    | 本节；权威计划 Execution registry；派发 `...msg-0105`                                                             |
| 2026-11-11 21:27:27 | `AR-20261111-T02-01` / 高级开发 | typed refs/domain replay/批量持久化/context/TS 类型及增量迁移已实现；首轮联合 93 项定向测试、mypy、前端类型检查通过，继续最终回归                                   | `message_capabilities_20261111`；`test_message_capabilities.py`、`test_message_capability_api.py`；本会话检查输出 |
| 2026-11-11 21:43:36 | `AR-20261111-T02-01` / 高级开发 | 按预审增加 `[A, B, A, C] -> [A, B, C]` 保序去重断言，并验证重放仍按 `(type,id)` 集合比较；放宽 MCP `_local` ref 首字符；联合 262 项回归及静态检查通过，待主会话审查 | 本 Delivery；`test_message_service.py`、`test_message_capability_api.py`；本会话检查输出                          |
| 2026-11-11 21:46:18 | `AR-20261111-T02-02` / 架构师 | 接管用户要求纠正的持久化设计，按修订 2 改为 `messages.capabilities` JSON 列；复用既有公开消息和 domain refs 契约 | 本方案及总计划 Execution registry；原执行者已被用户人工打断                          |

- 当前契约事实：`capabilities` 元素为 discriminator union `{type: "skill" | "mcp_server", id, name}`；`name` 是展示快照，执行身份仅取 `(type, id)`。额外 native path/token 字段和含路径的 ID 在请求校验时拒绝；冻结子模型及有序 tuple 构成领域消息事实。
- 存储修订：原关系表 delivery 为修订 1 历史记录，不接受为下游前置版本。修订 2 将有序 refs JSON 化并存于消息主记录，移除独立 relationship。下游 message API/domain/replay 契约不变。
- 规范化按首次出现保留引用及展示快照；publication replay 对 `(type, id)` 无序集合比较，不因选择顺序或展示名称变化误判，改变引用集合或类型返回既有 conflict。
- `web/src/services/roomApi.ts` 的 `CreateMessage/RoomMessage` 增加可选 refs，`MessageDraft` 自动继承。现有 `RoomPage` 已按完整 draft 构造并 JSON 保存/恢复 pending request，不需在 T02 改写 UI 文件；T03 再接入 picker 所选 refs。
- 修订 1 交付记录：新增 `message_capabilities` 关系表，在原有 message 事务写入，原执行者仅报告 fixture 验证；后续核对发现开发库已自动执行此 revision。用户审查后要求引用直接由消息携带，因此改用修订 3 前滚修复。

## Delivery and review / 交付与审查

- 交付状态：修订 4 实施并经本窗口审查接受；未提交 Git。用户已取消聊天室协作，后续开发全部收回本窗口。
- 实际变更：增加 typed Skill/MCP message refs 和旧客户端空列表兼容；message、history、publication lookup、room snapshot、queue snapshot、ContextMessage 与 web API 类型往返同一引用。`build_message` 用首次出现顺序去重；明确用 `[A, B, A, C]` 验证结果 `[A, B, C]`。publication replay 忽略顺序和展示快照差异，但对 `(type,id)` 引用集合变化返回 conflict。MCP ref ID 支持 `_local` 名称。范围内无偏差。
- 修订 1 持久化交付（被退回）：新增 `message_capabilities` 关系表，以 message 复合外键和唯一约束保存 refs。用户提出消息应直接携带 Skill，主会话复核后确认此表没有独立实体/查询需求，决定在修订 2 改为 `messages.capabilities` JSON 数组列。
- 原交付检查（历史）：旧关系表版本后端 262 passed；mypy、Ruff、Web API 类型/格式/ESLint 和 9 项 roomApi 测试通过。原指纹 `6873de89727077df006add34fd023bef7b0a3e2837a38a3dfe64000f615d8cd7` 已失效，不作为当前验收证据。
- 修订 3 变更：ORM/type/mapper/repository 直接读写 `messages.capabilities`；保留 `0002` 历史迁移，新增 `0003_capabilities_json` 按 position 转存引用并删除旧表，DDL、数据和 revision 在同一事务完成。公共 API、TS refs、领域 replay 契约不变。
- 历史检查（修订 3）：后端 265 passed、mypy 162 files、Ruff 246 files；当时的数据库/HTTP 集成测试及支持目录后续被用户删除，不作为当前保留测试的证明。
- 开发库：备份 `data/agent-relay.backup-20261111-215640.sqlite3`；备份副本完成独立迁移失败回滚演练和 15 张原表数据逐项核对。开发服务自动执行新增迁移后，原有 153 条消息及全部旧引用核对一致（期间正常新增消息不计为迁移差异）；完整性与外键检查通过，重复迁移与 Database 初始化通过，`GET /api/room/room-94f73433cde7/message?limit=1` 返回 200 且含 capabilities。
- 当前版本：HEAD `10cbb78045d0d7dd09cf197d36007af01df8fb11` 上的未提交工作区；`0002_capabilities_json.py` 及对应 SQL 为唯一能力迁移，删除原关系表迁移及转存逻辑。
- 当前检查：177 项后端单测通过（1.78s）；`mypy src tests migrations` 140 files、全仓 Ruff lint/format 220 files 通过；Alembic 只有一个 head，离线 SQL 仅增加消息列并更新版本，无中间表操作。本轮未连接数据库。
- 依赖交付：T01–T04 均已接受，用户已确认界面验收通过；最终证据见 `docs/verification/20261111-chat-skill-mcp.md`。
