# Task / 子任务 T01：Schema 与审计写入
最后修改时间: 2026-11-19 16:00:55

## 审查状态

Accepted。依据总计划与 #592，执行进度以总计划登记为准。

## 父任务与权威记录

- [总意图](../../intent/20261119-schema-governance.md)；[权威总计划](../../plan/20261119-schema-governance.md)，任务 T01，方案修订 1。
- 交接依据：总计划中的 `SG-20261119-T01-01`，高级开发 `member-b53c76acb705`，授权来源为当前频道用户消息 #592。协议为 SpecFlow 的 `SKILL.md` 及 `references/task-coordination.md`。代码和权威记录同在 `D:/SourceCodes/mywork/conflua`，代码基线 `develop` / `613f6a5c1b4292b95babfa57017004ace4538174`，无前置交付。开发在本文的接收、进展与交付章节写入事实，并在当前 Conflua 频道定向 @ 架构师回报。本文件不独立授予实施权。

## 目标与验收

交付新 SQLite 基线及一致的审计、软删写入，覆盖 A01–A03。

- 新建库 DDL、种子与 ORM 的数据契约一致；旧 revision 在任何 DDL 前被拒绝，且不新增自动转换路径。
- 逐表证明 INSERT 默认写入 `created_at`，业务更新刷新 `updated_at`；已有软删表的活动筛选、部分唯一约束和历史读取按语义区分，频道归档不当作删除。

## 输入与可开始条件

- 无前置任务；输入是总意图、本计划及 `613f6a5` 当前 DDL、ORM 和仓储。开始前核对计划审查状态、有效分配和实际工作基线。

## 范围与局部方案

- 负责 `migrations/sqlite/`、`src/conflua/infrastructure/persistence/` 的新库入口、模型、类型、读写筛选和对应测试；涉及状态 DTO/映射时仅调整删除与归档所需范围。后续与 T02 串行。`migrations/README.md` 由 T04 整理。
- 先盘点 16 张业务表：交付列与默认值、主外键作用域、软删与归档状态表、活动索引、业务时间合同、每类写入入口的清单。新基线清理硬编码频道 ID 和固定人类 ID 约束，以作用域唯一约束取代；保留 SQLite 依赖的复合作用域与现有顺序键。
- 再修改 DDL 与仓储：创建和修改时间只表达各自含义；盘点 ORM 属性/merge、Core 批量更新和 upsert，不把仅覆盖一种写法的默认钩子当成全覆盖。软删同事务写状态、首次删除时间及修改时间。
- 本节点用符合新契约的显式测试 ID 验证持久化；不提前调整各业务发号、默认身份发现、客户端或旧库转换。不部署持久化过渡状态。

## 检查与交付

- 检查 Alembic `heads` 与离线 DDL、目标临时空库、旧 revision 拒绝路径、对应仓储用例及 Ruff/Mypy。提供逐表清单、覆盖写路径说明和检查版本；失败项注明原因。该清单作为 T02、T04 的可审查输入。
- 风险：批量更新绕过审计、归档和软删的筛选混用导致可见性或名称复用回归、已有投递或查阅时间语义被误作可空化。检查时必须分别覆盖。

## 接收与进展

- 2026-11-19 15:15:28：高级开发 `member-b53c76acb705` 接收 `SG-20261119-T01-01`，方案修订 1，依据用户 #592 和架构师 #594。已核对共享工作区 `D:/SourceCodes/mywork/conflua`、`develop` / `613f6a5c1b4292b95babfa57017004ace4538174`，现有非跟踪变更均为规划文档；无前置交付，无开工阻塞。仅实施 A01–A03，不操作真实库、外部会话或 Git 写入。
- 用户随后确认开发服务器当前停用，等实现到可用阶段再就地修复开发库；不进行集成测试或反向测试。T01 仍仅交付基线，不改真实开发库；完整的代码和离线迁移可用后再处理原路径，不能用 T01 过渡版本迁库。

## 交付与审查

`SG-20261119-T01-01`，按分派方案修订 1 实现完毕，待架构师审查。无前置交付。工作区 `D:/SourceCodes/mywork/conflua`，`develop` / `613f6a5c1b4292b95babfa57017004ace4538174` 上的未暂存差异与新增文件，范围为 `migrations/sqlite/`、`src/conflua/infrastructure/persistence/`、`tests/unit/infrastructure/test_schema_audit.py`、`tests/unit/infrastructure/test_query_scoping.py`、`tests/unit/interfaces/test_member_roles.py` 及本记录。新增 SQL 种子和单元测试均未跟踪。对上述代码路径内 34 个变更路径按相对路径排序，以 `SHA256 文件路径` 或 `DELETED 文件路径` 逐行（LF）构成清单，UTF-8 清单 SHA-256 为 `79895982982AC63FCA9AAEF87BC5A36FF526E7329A808D71855E937F4A3A4707`（路径是 `git diff --name-only` 与 `git ls-files --others --exclude-standard` 的并集，不含过程文档）。未暂存、提交、推送或操作真实数据库。

- A01：单一 SQL-first 基线 `schema_governance_20261119`，旧 revision 不再挂在活跃 Alembic 谱系。运行时和在线 Alembic 在任何 DDL 前共用只读 revision 预检，已初始化的旧库或非空未标记库提示备份并离线转换；旧基线可从 `613f6a5` 取得。离线 DDL 生成验证通过，未执行建库或从旧库启动。
- A02：16 张表共享 SQLite UTC 默认值及 ORM 审计映射。ORM flush、`merge` 和 SQLAlchemy `update` 使用 `onupdate`，显式业务时间可覆盖该默认（投递、查阅位置、软删）。查阅位置保留“首次插入，随后仅在序号推进时更新”的现有写法，无 `ON CONFLICT` 写路径；订阅仍按既有删旧加新写入，父成员的订阅变化也刷新审计。持久化时间写到 UTC，带偏移时间折算为原时刻；无时区的新写入按 UTC 解释，旧库的歧义处理由 T04 决定。正向单测覆盖列映射与 UTC 换算，真实 SQL 写入效果未验证。
- A03：房间删除时间、频道归档和频道删除分别存储；仓储用布尔状态筛选并按原作用域级联。频道归档保留历史，活动名称可复用；重复操作不改首次时间。清队列和级联不覆盖投递业务状态、会话标识、回执。正向单测覆盖归档字段映射；约束拒绝、级联和重复删除未运行数据库用例。
- 范围边界：T02 负责服务端 TSID 造号、查找及旧身份常量，本阶段 SQLite 已拒绝旧格式 ID，不能部署；调用仍使用旧 ID 的现有应用和完整回归套件不能作为本节点兼容证明。T04 负责转换，开发库尚未修复或切换。用户已要求不运行集成/反向测试；因此以源码审查、正向无数据库单测和静态检查交付，不将 A01–A03 标记为已完成集成验收。

### 实际检查

均在仓库根目录执行，不连接开发库。

| 命令 | 结果 |
| --- | --- |
| `uv run --locked --no-sync pytest tests/unit/infrastructure/test_schema_audit.py` | 3 个不连接数据库的正向测试通过。 |
| `uv run --locked --no-sync mypy src tests` | 235 个源文件，无问题。 |
| `uv run --locked --no-sync ruff check src/conflua/infrastructure/persistence migrations/sqlite tests/unit/infrastructure/test_schema_audit.py tests/unit/infrastructure/test_query_scoping.py tests/unit/interfaces/test_member_roles.py` | 通过。 |
| `uv run --locked --no-sync ruff format --check src/conflua/infrastructure/persistence migrations/sqlite tests/unit/infrastructure/test_schema_audit.py tests/unit/infrastructure/test_query_scoping.py tests/unit/interfaces/test_member_roles.py` | 29 个文件均符合格式。 |
| `uv run --locked --no-sync alembic heads` | 单一 head `schema_governance_20261119`。 |
| `uv run --locked --no-sync alembic upgrade head --sql` | 仅生成 SQL，包含 16 张业务表、16 个审计默认值、6 个软删一致性约束、角色种子及新 revision 标记。 |
| `git diff --check` | 通过。 |

### 逐表基线与写路径

16 张表均为 `created_at TEXT NOT NULL DEFAULT`（UTC ISO 8601，六位小数秒）和可空 `updated_at TEXT`；投递、查阅位置保留业务写入时初始化 `updated_at`。六张软删表额外保存 `is_deleted`（0/1、默认 0）和 `deleted_at`；状态与时间必须成对。房间、频道、话题、成员、消息、投递、角色及查阅请求的自有 `id` 为 13 位大写 Crockford Base32（首位 `0`–`7`），固定角色使用 `0000000000001` 至 `0000000000003`。下表的频道作用域为 `(room_id, channel_id)`，直接外键和历史关联的引用目标不换作用域。

| 表 | 主键、引用及业务不变量 | 写路径与旧列解释 |
| --- | --- | --- |
| `rooms` | `id`；活动 `workspace_path` 唯一。 | 创建、资料批量更新、删除；旧 `archived_at` 是删除时间。 |
| `channels` | `(room_id, id)` → 房间；每房间唯一默认频道；活动名称房间内唯一。 | 创建、ORM 编辑/归档、频道删除与房间级联。旧 `active` + `archived_at` 是软删，旧 `archived` + 时间是真归档，保留后者；旧默认频道不能独立删除或归档。 |
| `sessions` | `(room_id, id)` → 房间；外部会话 ID 原样。 | `merge`、观察状态批量更新；`observed_at` 不是审计时间。 |
| `topics` | 频道作用域 + `id` → 房间和频道；活动名称频道内唯一。 | 创建、资料更新、软删；保留已知创建及删除时间。 |
| `members` | 频道作用域 + `id` → 房间、频道、房间内会话；活动名称及会话频道内唯一，每频道唯一固定人类成员。 | 创建、`merge`、观察状态更新、主动退役和级联；固定人类成员不可软删，保留 `observed_at`。 |
| `member_topics` | 频道作用域 + `(member_id, topic_id)` → 同频道成员和话题。 | 订阅有序替换（删/增关联），不引入软删。 |
| `messages` | 频道作用域 + `id` → 房间、同频道发布者和可选同频道父消息；`(room_id, seq)`、频道作用域 + `(publisher_id, publication_id)` 唯一；发布者分页索引。 | 追加、频道消息清空；保留 `seq` 和消息时间。 |
| `message_topics` | 频道作用域 + `(message_id, topic_id)` → 同频道消息和话题；保留话题反查索引。 | 发布时追加有序快照。 |
| `message_mentions` | 频道作用域 + `(message_id, member_id)` → 同频道消息和成员；保留成员反查索引。 | 发布时追加有序快照。 |
| `message_recipients` | 频道作用域 + `(message_id, member_id)` → 同频道消息和成员；保留成员反查索引。 | 发布时追加有序快照。 |
| `deliveries` | 频道作用域 + `id` → 同频道消息和目标成员、房间内目标会话；同消息/成员及会话/客户端消息唯一，保留分派索引和 `rowid` 顺序。 | 发送、重试、激活、回执/说明、队列清空及级联；软删不改状态、会话标识或回执。 |
| `room_events` | `event_id INTEGER PRIMARY KEY AUTOINCREMENT`；引用房间和频道，实体为多态业务引用；保留房间/频道/游标索引。 | 只追加变更事件。 |
| `member_context_queries` | `id`；频道作用域 + `id` 唯一供关联引用；引用同频道成员、可选消息和话题；保留成员反查索引。 | 只追加查阅请求；保留 `provided_at`。 |
| `member_context_messages` | 频道作用域 + `(query_id, message_id)` → 同频道查询和消息。 | 只追加查阅结果的有序关联。 |
| `member_topic_positions` | 频道作用域 + `(member_id, topic_id)` → 同频道成员、话题。 | 插入或仅在序号向前时更新；保留既有时间初始化。 |
| `member_roles` | `id`；角色名全站唯一。 | 固定种子、创建、ORM 更新、物理删除。 |

### 仲裁记录

- 2026-11-19：接受 `SG-20261119-T01-01` 的持久化交付。架构师复核实际差异及 34 路径指纹；复算约定为路径按序号排序、文件 SHA-256 大写、单空格分隔、LF 拼接、UTF-8 无 BOM 且无末尾换行，删除行用 `DELETED 文件路径`。#600 是独立检查证据，#601 取代其初始分级和结论。测试报告 19 个定向用例、静态检查、离线 SQL 及临时库检查通过；投递 `attempt_count` 默认值 DDL/ORM 表达不同但 SQLite 数值语义一致。
- 创建路径：当前应用仍使用旧房间/频道造号和固定身份常量，新库会拒绝旧 ID（包括 `channel-default` 和 `user`）。这是 T01 不含业务造号的边界，不是回退 Schema 约束的理由；T01 不可部署，两条创建路径由 T02 首个交付验证。
- 投递审计：新库的 `updated_at` 可空，现有领域写入显式初始化，DTO 的 `created_at` 兜底不能作为落库证据。旧基线的投递 `updated_at` 为非空业务字段，T04 须显式迁移该值并直接查列；无偏移历史时间不得静默按 UTC 解释。
- 频道归档：活动名称唯一、归档名称可复用。按 ID 对已归档频道以原名或未指定名称重复归档，返回原记录、保留首次归档时间；同名活动频道不构成冲突，不允许借重复归档改名。
- 未完成集成验收：未启动后端、运行集成/反向测试或触碰真实库、备份及会话。带外键检查的完整业务事务与回滚、客户端及实际换库均未验证；在用服务保持独立的旧 Schema 快照。
