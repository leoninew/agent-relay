# Task / 子任务 T02：服务端资源 ID 与查找契约
最后修改时间: 2026-11-19 16:48:20

## 审查状态

Accepted。依据总计划与 #592，执行状态以总计划登记为准。

## 父任务与权威记录

- [总意图](../../intent/20261119-schema-governance.md)；[权威总计划](../../plan/20261119-schema-governance.md)，任务 T02，方案修订 3。
- 交接依据：总计划登记 `SG-20261119-T02-01`，高级开发 `member-b53c76acb705`，用户 #592 授权 Implementation。协议为 SpecFlow 的 `SKILL.md` 和 `references/task-coordination.md`。代码和权威协调根均在 `D:/SourceCodes/mywork/conflua`，基线为 `develop` / `613f6a5c1b4292b95babfa57017004ace4538174` 加上总计划所列已接受的 T01 34 路径差异。执行者仅在本文写接收、进展、交付，并在当前 Conflua 频道定向 @ 架构师回报。本文件不独立授予实施权。

## 目标与验收

交付服务端统一资源 ID、默认身份发现和频道创建恢复契约，覆盖 A04。

- 所有自有实体生成规范 TSID，服务端校验与 T01 DDL 一致；默认频道及固定人类成员按属性和作用域定位，不从旧 ID 常量推断。SQL 查询和 API 仍隔离不同房间、不同频道。
- 首个交付须证明两条创建路径使用新 Schema：创建房间同时建立默认频道及该频道的固定人类成员；独立创建频道也建立各自的固定人类成员。核对 ID 规范、作用域、按 `is_default` / `kind='human'` 的发现结果及原有事务边界；不以削弱 TSID 约束通过验收。
- 同一既知频道 ID 支持创建后找回，领号不创建频道或 Git worktree。资源 ID 换格式后，消息与事件游标、投递顺序、受管图片上传/读取及 Markdown 解析仍按原语义工作。

## 输入与可开始条件

- 以总计划登记的、已接受且可访问的 T01 DDL、ORM 及逐表作用域/状态清单为基线。方案、权限、版本或交付物不符时回报，不自行变更上游契约。

## 范围与局部方案

- 负责 `pyproject.toml`、`uv.lock`、`src/conflua/` 中的 TSID 生成与验证、领域造号、默认频道/人类成员查找及服务端 HTTP/MCP 和图片实现；不改 `web/`、CLI 客户端、插件文档、离线脚本。持久化共享文件在 T01 接受后修改，任何 DDL 接口偏差先回报仲裁。
- 固定 `tsidpy` 的实际依赖版本，统一使用规范字符串而非数值；规定多进程发号的 node 策略。提供下游可复用的生成/验证接口及样例；检查消息复合 ID、上下文请求 UUID、角色及默认资源的旧生成点和识别点。
- 冻结领号、默认资源发现、创建结果未知及冲突的服务端契约。保留显式频道作用域和既有写入原子性；不同请求碰撞不能误作合法重放，不因创建结果未知自动改变 Git 状态。
- 图片存储和受管链接统一按新房间/频道 ID 校验，保留 `img-*` 外部于关系表的图片文件标识；向 T04 提供目标存储路径和链接规范，不在产品运行时保留旧前缀解析。

## 检查与交付

- 提供 TSID 规范向量、位宽与拒绝用例，覆盖生成实例配置、跨作用域固定身份、频道领号/创建/查询、图片路径及消息与投递业务顺序。现阶段只执行定向正向单测（两条创建路径可用隔离临时 SQLite）、静态检查和离线 SQL；不运行集成/反向测试或启动后端，不触碰运行服务、真实库、备份或会话。交付新 API 示例、对应版本、实际检查与未验证部署假设。
- 风险：只替换造号未改硬编码身份会造成串频道或隐蔽 404；多个未协调实例即使通过格式验证仍可能碰撞。提交时说明发号部署约束与冲突行为。

## 接收与进展

- 2026-11-19 16:03:13：高级开发 `member-b53c76acb705` 接收 `SG-20261119-T02-01`，依据 #592 与 #602，方案修订 3。已核对 `D:/SourceCodes/mywork/conflua` 的 `develop` / `613f6a5c1b4292b95babfa57017004ace4538174` 和已接受的 T01；复算 34 路径 SHA-256 `79895982982AC63FCA9AAEF87BC5A36FF526E7329A808D71855E937F4A3A4707`（UTF-8、LF、无尾 LF）一致。无开工阻塞；仅作正向定向检查、静态检查和离线 SQL，不启动后端或操作真实库、会话与 Git 持久状态。
- 2026-11-19 16:18：两条创建路径在新建临时 SQLite 上通过；房间、频道、固定人类成员、默认话题与初始事件在请求提交后可见。领号不插入记录、不访问 Git。T01 DDL 无修改。以下契约与证据已冻结，等待架构师审查。

## 交付与审查

`SG-20261119-T02-01`，方案修订 3，实施范围 A04。交付为共享工作区 `D:/SourceCodes/mywork/conflua` 的 `develop` / `613f6a5c1b4292b95babfa57017004ace4538174` 上的未暂存差异和未跟踪文件，承接已接受的 T01（34 路径输入指纹见接收记录）。未暂存、提交或推送。本记录不更新总登记。

### 稳定范围与版本

- T01＋T02 代码联合指纹为 `C636F185AB9471B8517C77777C0BE52DB6CA730F1006770EBB5E23C841137827`（70 路径）。范围是 `git diff --name-only --no-renames -- migrations/sqlite src/conflua tests/unit pyproject.toml uv.lock` 与同路径下 `git ls-files --others --exclude-standard` 的并集。按相对路径作 ordinal 排序，逐行 `SHA256 文件路径`（大写）或 `DELETED 文件路径`，UTF-8 无 BOM、LF 分隔且无末尾换行后计算 SHA-256，不含过程文档。用 `git diff -- <范围>` 查看跟踪差异；并集中的未跟踪文件须单独读取。
- T02 改动触点为上述集合排除 `migrations/sqlite/`、持久化 `database.py`、`mappers.py`、`migration_sql.py`、`migrations.py`、`models.py`、`types.py`、`repositories/context.py` 及 `test_member_roles.py`、`test_schema_audit.py`（这些仅属 T01）。44 路径子集指纹为 `3B6249C68E6962A4E81689AB6E13EF8E684A68BFD1BAE447A89007F81E78E161`；共有触点保留 T01 行为后接续修改。T02 新增 `domain/identifiers.py`、`repositories/_channel_scope.py`、`test_identifiers.py`、`test_server_identifiers.py`。
- `pyproject.toml` / `uv.lock` 固定 `tsidpy==1.1.5`。应用层负责房间、频道、话题、成员、角色、查阅请求造号，领域层负责消息和投递造号。持久化按 `is_default`（房间内）、`kind='human'`（房间和频道内）定位，不认旧字面 ID。房间写入和频道初始化使用原事务；消息头、关停通知按发布者类型，投递领取、延期、完成按复合键限定。消息页仍按 `seq`，事件仍按 `event_id`，投递仍按 `rowid` 及既有重试顺序，不使用 TSID 排业务顺序。

### T03/T04 接口

- T03：`POST /api/room/{roomId}/channel/issue-id` 返回 `200 {"channelId":"0000000000124"}`。领号只确认房间存在，不预占记录、不绑定持有人、无 Git 副作用。`POST /api/room/{roomId}/channel` 携带 `{"channelId":"0000000000124","name":"开发","useWorktree":false,"description":""}`，成功 `201` 返回 `Channel`。`channelId` 必填且必须规范；无效输入 `422 validation_error`。同房间已有相同 ID（含软删和归档）返回 `409 channel_id_conflict`，不按名称或参数重放。活动名称冲突仍是 `409 channel_name_conflict`。
- T03：仅发送一次创建；结果未知用 `GET /api/room/{roomId}/channel/{channelId}` 查询同一 ID，未创建为 `404 channel_not_found`，软删记录不可用。查不到不授权自动重试、占用或清理 Git worktree/分支；已明确返回 `409 channel_id_conflict` 不可解释为该请求成功。`GET /api/room/{roomId}/channel` 从 `isDefault: true` 找默认频道；从该频道成员数据按 `kind: "human"` 找固定用户，不沿用旧值。MCP `channel_issue_id(room_id)`、`channel_create(room_id, channel_id, name, use_worktree=False, description="")`、`channel_get(room_id, channel_id)` 同义；MCP 创建错误保留 `error.channelId` 供定位。CLI 和 Web 由 T03 适配。
- T04：`conflua.domain.identifiers` 导出 `TsidSource(node=...)`、`new_tsid()`、`is_tsid()`、`require_tsid()`。T01 接受的范围为 `0000000000000` 至 `7ZZZZZZZZZZZZ`（数值 `0..2^63-1`），使用大写 Crockford 字母表 `0123456789ABCDEFGHJKMNPQRSTVWXYZ`，首位 `0–7`；`0C04Q2BR40003` 是有效示例。库自身可编码更宽的无符号值，如 `FZZZZZZZZZZZZ`，本项目不接收。服务端全进程共享一个线程安全生成器，节点 `0`；现版本只支持单一活跃发号进程。多进程方案须先为每个活跃实例分配独占 `0..1023` 节点并接入集中配置，不使用随机选节点；离线转换使用独立的显式节点（例如 `1023`），并单独检查目标 ID 唯一性。
- T04：图片文件 `rooms/{roomId}/channels/{channelId}/images/{imageId}.{ext}`，`ext` 为 `png`、`jpg`、`webp`。HTTP `/api/room/{roomId}/channel/{channelId}/image/{imageId}`，Markdown `![image](/api/room/{roomId}/channel/{channelId}/image/{imageId})`；只匹配当前房间/频道的规范 TSID 路径。`img-[a-f0-9]{32}` 不变。不改外部会话和客户端输入 UUID、发布编号、消息序号或事件游标。

### 实际检查

| 命令 | 结果 |
| --- | --- |
| `uv lock` | 成功，锁文件仅新增 `tsidpy` 及其引用。 |
| `uv run --locked mypy src tests` | 239 个源文件，无问题。 |
| `uv run --locked ruff check src tests migrations` | 通过。 |
| `uv run --locked ruff format --check src tests migrations` | 242 个文件符合格式。 |
| `uv run --locked alembic heads` | 单一 head `schema_governance_20261119`。 |
| `uv run --locked alembic upgrade head --sql` | 只生成 SQL；259 行、16 张业务表加版本表，写入预期 revision。 |
| `git diff --check` | 通过。 |

实际定向命令如下（PowerShell），19 个通过、93 个未选中。最早一次边界向量误用了 `2^64-1`，经对照 T01 DDL 改用 `2^63-1`，未放宽约束。

```powershell
uv run --locked pytest -q tests/unit/infrastructure/test_server_identifiers.py tests/unit/domain/test_identifiers.py tests/unit/application/test_room_service.py tests/unit/application/test_channel_service.py tests/unit/domain/test_resources.py tests/unit/domain/test_room_rules.py tests/unit/interfaces/test_channels.py tests/unit/interfaces/test_mcp_catalog.py tests/unit/infrastructure/test_query_scoping.py tests/unit/application/test_delivery_actions.py -k 'room_and_independent_channel or image_round_trip or canonical_tsid_vectors or tsid_source_shares or room_creation or channel_creation_supplies or initial_resources_are or routing_freezes or channel_routes_ or channel_creation_defaults or tool_catalog_exposes or navigation_heads_only or test_steer_receipt_is_saved'
```

`test_server_identifiers.py` 通过 Alembic 建立 pytest 临时目录内的 `new-schema.sqlite`。从独立连接确认未提交的房间和频道不可见，提交后验证默认频道与另一房间的默认频道不混用、独立频道取回为创建记录、各频道内 SQL `kind='human'` 与默认发布者解析结果相同。用例验证作用域、ID 唯一性、话题和事件，并以临时目录验证受管图片写入、读取和 Markdown。其他正向用例覆盖边界向量、线程间共享发号、节点位、路由/MCP 参数、消息和投递造号、接收人顺序、消息头和通知过滤；队列行顺序及事件游标按现存 SQL 核对，未做分派集成验证。

未验证：反向/碰撞 HTTP 请求、并发进程、真实 Git worktree、外部 Codex 投递、客户端适配、旧库离线迁移和换库。碰撞与非法 ID 回归用例已补但未运行。未启动或切换后端，未触碰真实库、备份或外部会话。当前在用服务继续是独立的 `613f6a5` 快照；本次交付不可据此部署，须经独立复验和架构师确认才能放行下游。

### #607 复验退回与限定返工

- 2026-11-19 16:40：架构师 #607 将 `SG-20261119-T02-01` 退回 `running`，沿用执行者、编号和方案修订 3；只解除 `tests/unit/interfaces/test_member_role_binding.py` 与本记录的冻结。保留原 70 路径指纹及测试已报告的全量结果（3 失败、535 通过）；失败受旧频道创建/默认频道请求阻断，`senderId == "user"` 旧断言尚未执行，不能据此归为产品回归。本次没有改动其他文件或产品代码。
- 指定测试文件现按 GET 频道列表的 `isDefault` 找默认频道；独立频道先 POST `issue-id`，再将返回的 `channelId` 带入 POST 创建。发布者 ID 从同一 room/channel 的 `MemberRecord.kind == 'human'` 查询并断言。新增独立纯正向用例覆盖创建房间默认频道的发现、领号不写入频道列表、独立频道创建、两频道各自固定人类成员、按默认频道身份发布角色提示消息及频道隔离。原角色校验、重复绑定隔离、投递及事务回滚断言均保留；不运行这些反向场景。
- 返工后联合路径范围 71，指纹 `43234D6132B1FB30412AC5EAAB23D72AE9F20AF6A5322647DF0A1E692C2B681C`；定义沿用上文 T01+T02 联合范围与哈希规范，仅增加 `tests/unit/interfaces/test_member_role_binding.py`。T02 路径范围 45，指纹 `12AC139459BB4D01244FD75A4DFD37D7F58A4967B71B965EB3C77BBEB713175B`；沿用上文排除的 T01 路径集合。唯一新增差异路径为 `tests/unit/interfaces/test_member_role_binding.py`，本次仅此文件和本记录有编辑。

| 实际命令 | 结果 |
| --- | --- |
| `uv run --locked pytest -q tests/unit/interfaces/test_member_role_binding.py::test_issued_channel_and_human_role_message_use_discovered_ids` | 1 通过；测试应用使用 pytest 临时 SQLite，未启动服务。 |
| `uv run --locked ruff check tests/unit/interfaces/test_member_role_binding.py` | 通过。 |
| `uv run --locked ruff format --check tests/unit/interfaces/test_member_role_binding.py` | 通过，文件已格式化。 |
| `uv run --locked mypy tests/unit/interfaces/test_member_role_binding.py` | 无问题。 |
| `git diff --check` | 通过。 |

依架构师 #607 要求，未整文件重跑、未跑先前全量套件或反向场景；未重跑产品路径的离线 SQL/临时库检查，因为本次无产品代码或 DDL 变化。未访问真实库、备份、Git worktree、外部会话；未启动或切换服务，未暂存、提交、推送。当前返工证据待架构师复审，不自报 accepted。

### 返工版仲裁

- 2026-11-19 16:48:20：架构师按方案修订 3 将 `SG-20261119-T02-01` 的返工版登记为 `accepted`。主会话复算联合 71 路径与 T02 45 路径指纹一致；排除补测文件后仍匹配原 70/44 路径指纹。实际差异已改用语义发现和服务端领号，保留原角色校验、隔离、投递与回滚断言；产品代码及 DDL 未变化，`git diff --check` 通过。
- 独立复验 #611 同版复算一致：新增正向用例 1 通过、原定向 19 通过，Mypy、Ruff、离线 SQL 和 Alembic 单 head 均通过。#612 为开发方补充的正向证据，不替代独立复验。
- #606 的 535 通过、3 失败是返工前结果。返工后原三例、整文件、全量及反向/集成未运行；这些不作为本次下游接入门槛，仍须在后续获授权的整体验证中确认，不能宣称全量通过。进程间发号、真实 worktree、外部投递、客户端和旧库转换仍不在本节点验收范围。
- 下游使用本次已接受的 71 路径基线与上文接口契约。当前阶段不授权部署、换库或替换运行中的 `613f6a5` 服务快照，也未进入整体 Verification。
