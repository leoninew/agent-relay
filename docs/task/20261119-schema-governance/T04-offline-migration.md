# Task / 子任务 T04：开发库离线转换与恢复指南
最后修改时间: 2026-11-19 18:21:06

## 审查状态

Accepted。依据总计划与 #592，执行状态以总计划登记为准。

## 父任务与权威记录

- [总意图](../../intent/20261119-schema-governance.md)；[权威总计划](../../plan/20261119-schema-governance.md)，任务 T04，方案修订 3。
- 交接依据：总计划登记 `SG-20261119-T04-01`，高级开发 `member-b53c76acb705`，用户 #592 授权 Implementation。协议为 SpecFlow 的 `SKILL.md` 和 `references/task-coordination.md`。代码与权威协调根均在 `D:/SourceCodes/mywork/conflua`，基线为 `develop` / `613f6a5c1b4292b95babfa57017004ace4538174`，直接输入是已接受的 T01＋T02 71 路径 `43234D6132B1FB30412AC5EAAB23D72AE9F20AF6A5322647DF0A1E692C2B681C`；同一工作区保留已接受的 T03，联合 107 路径 `21B5A7F9EDA259BE2B016C18480EC4DF51828554A7088E07231F055FA037D736`。T03 不新增技术依赖。执行者在本文写接收、进展和交付，在当前 Conflua 频道定向 @ 架构师回报。本文件不独立授予实施权。

## 目标与验收

交付独立 Python/SQL 离线换库脚本、报告和恢复指南，覆盖 A06。

- 仅接受已知源 revision，要求显式源/目标，目标不覆盖。源数据库和图片只读；复制、转换或校验失败不替换现有数据。成功产出可审查的行数、映射、回填和资产统计及错误说明。
- 迁移后外键通过，结构化引用均按原作用域重挂，软删与归档分类正确，旧消息、队列和事件顺序不变；受管历史图片可读，已保存的 worktree 和外部会话、回执值未改变。

## 输入与可开始条件

- 使用已接受且可访问的 T02 版本，内含 T01 最终 Schema，并提供可复用 TSID 工具及图片路径/链接。旧库 fixture 从 `613f6a5` 的 `member_roles_20261118` 版本构造；不以任何在用数据库为输入。

## 范围与局部方案

1. 在 `scripts/` 实现独立入口，预检目标为空、源路径与目标不同、源 revision 与完整性符合预期。旧库及图片使用明确路径，不根据当前 profile 隐式选中真实库。
2. 使用新基线初始化新库，按原键空间生成映射，再写关联、自引用、事件和查阅记录。处理默认频道/固定用户在不同作用域的同名旧键，区分事件实体类型，保留 `seq`、`event_id` 及其高水位、依赖的相对插入顺序。只迁移应用可识别的受管图片 URL，复制对应目录；不对消息普通正文做全局替换。
3. 用旧状态与时间分类归档/软删，历史审计只采可信来源；缺失的 `created_at` 统一回填、报告，未记录过的普通 `updated_at` 保持空。旧 `deliveries.updated_at` 是非空业务时间，须显式写入等价 UTC；缺失则报告并拒绝，不能以 `created_at` 填补。带显式偏移的历史时间转换为等价 UTC，保留时刻、精度和顺序；无显式偏移的非空历史值报告表、列及记录位置并拒绝，不猜测本地时区，也不静默按 UTC 处理。旧路径、外部标识和回执不改；目标必须经完整性和引用检查才可供切换。
4. 更新 `migrations/README.md` 的停机、SQLite 一致性快照、图片备份、检查、切换与恢复流程。明确备份后切换由人执行，不自动接管旧库，不对现有会话或 Git worktree 作操作。与 T03 分开写入；不改目标 DDL 或运行时。

## 检查与交付

- 临时样本覆盖同名旧默认键、归档与删除、消息回复、位置、事件、队列回执、内联图片、意外 source revision 与缺失资产等失败路径。报告源未修改、目标行数与映射完整度、`integrity_check`/`foreign_key_check` 结果，以及切换前可恢复性。
- 用非零偏移的旧房间删除时间、历史投递 `updated_at` 和已为 UTC 的值验证转换前后时刻相同。直接查询目标 `deliveries.updated_at IS NULL` 的行数为零，不以 DTO 值代替；覆盖可空列的空值保持及无偏移非空值的报告、失败退出。当前不运行集成/反向测试；相关场景记录为后续获准验证的门槛。
- 风险：迁移的 DB 与图片是两个资产，不能假定单个 SQLite 事务覆盖两者；失败只保留隔离输出或明确清理目标，不进行实际替换。停机时仍在外部队列的回执需另行确认，不由脚本处理。

## 接收与进展

- 2026-11-19 17:35:02：高级开发 `member-b53c76acb705` 按 #592/#623 接收 `SG-20261119-T04-01`（修订 3）。核对共享 `D:/SourceCodes/mywork/conflua`、`develop` / `613f6a5c1b4292b95babfa57017004ace4538174`；复算 T01＋T02 71 路径 `43234D6132B1FB30412AC5EAAB23D72AE9F20AF6A5322647DF0A1E692C2B681C`、联合 107 路径 `21B5A7F9EDA259BE2B016C18480EC4DF51828554A7088E07231F055FA037D736` 均一致。无开工阻塞。不处理工作区内其他成员留下的未跟踪文件。只写离线转换脚本、对应测试/合成材料、迁移指南与本记录；仅允许静态、定向正向和隔离临时 SQLite/合成图片演练，不接触实际资产、服务、会话或 Git 持久状态。
- 2026-11-19 17:46:40：实现与定向正向演练完成。目标库及图片由独立命令生成，切换和恢复由操作人另行执行；冻结交付差异，待主会话登记并安排同版复验。

## 交付与审查

### 冻结范围

- `SG-20261119-T04-01`，方案修订 3，`develop` / `613f6a5c1b4292b95babfa57017004ace4538174`。保留 T01＋T02 的 71 路径 `43234D6132B1FB30412AC5EAAB23D72AE9F20AF6A5322647DF0A1E692C2B681C` 和 T01–T03 的 107 路径 `21B5A7F9EDA259BE2B016C18480EC4DF51828554A7088E07231F055FA037D736`，交付前复算一致。
- T04 的 3 路径指纹 `5725A5732ECED2B49C8CEC3CD055ACA2F60D4AECBDE050680DCF2B42524B5261`：`scripts/migrate-schema-governance.py`（新增）、`tests/unit/infrastructure/test_offline_schema_migration.py`（新增，内含合成样本）、`migrations/README.md`（未暂存差异）。本过程记录不计入指纹。与冻结 107 路径合并的 110 路径指纹 `05A737EB8FD77D5E32BA195F46B5DE3F2A0BA96478D506074CE71498AEEC5CA7`。
- 按 T03 交付定义取得上游路径并集，排除本次新增的 `tests/unit/infrastructure/test_offline_schema_migration.py` 后是冻结 107 路径，再排除 T03 路径即前置 71 路径。全部指纹采用路径 ordinal 排序、逐行 `大写 SHA256 文件路径` 或 `DELETED 文件路径`、UTF-8 无 BOM、LF 且无尾 LF。指南用 `git diff HEAD -- migrations/README.md` 查看，两个新增文件分别只读审阅；无暂存。

### 实现与证据

- 只读校验显式源 SQLite 快照及 revision。按原房间/频道作用域重挂自有 ID、关系、回复、事件及查阅记录；保留消息 `seq`、行顺序、事件 `event_id` 和高水位。外部 session、publication/client 标识、投递回执、房间与 worktree 路径不改。转换结果置于独立新目录，数据库和图片校验完成后才原子发布 `report.json`；失败不接管现用资产。
- 样本按 `git ls-tree` / `git show` 读取基线旧版 SQL 生成 `member_roles_20261118`，脚本在 `pytest` 的临时目录初始化 `schema_governance_20261119`，报告和两张合成图在同一输出内。源库及源图字节未变；两端 `integrity_check` 均为 `ok`、`foreign_key_check` 均无行。目标逐表行数与源一致：`rooms=2`、`channels=3`、`sessions=1`、`topics=2`、`members=4`、`member_topics=1`、`messages=4`、`message_topics=2`、`message_mentions=1`、`message_recipients=1`、`deliveries=2`、`room_events=9`、`member_context_queries=1`、`member_context_messages=2`、`member_topic_positions=1`、`member_roles=3`。
- 正向样本核对跨房间的同名默认键、同房间两频道复用的旧消息/人类键、关联位置、回复、投递目标与回执、查阅关系、原 `rowid` 顺序和事件高水位 `21`。旧房间删除、频道删除、频道独立归档、话题删除各 1 条。图片复制和受管链接重写各 2；同一旧图片 ID 在两个频道分别按原作用域迁移，通过新 `FileImageStore` 读回并核对图像像素与 SHA-256；普通正文、代码及跨作用域链接保持原样。
- 非零偏移的旧房间删除时间和首条 `deliveries.updated_at` 从 `2026-11-19T00:01:02.123456+08:00` 转为等价的 `2026-11-18T16:01:02.123456+00:00`，第二条原 UTC 投递时间保留 `.123457`，空的可空历史/普通审计字段保持空。测试直接执行 `SELECT count(*) FROM deliveries WHERE updated_at IS NULL` 返回 `0`。缺失的 `created_at` 统一回填，共 35 行并逐表报告。非空无偏移历史值按 `table[rowid=…].column` 报告并拒绝，不猜时区；旧投递更新时间为 NULL 时也拒绝，不回填。
- 指南包含停机、SQLite 一致性快照和图片备份、复核、人工配对切换和配对恢复。报告含旧键、路径相关标识和校验和，只放在受控的离线输出目录，不作为公共日志。

### 实际检查

均从共享仓库根目录运行，未安装依赖。四条 `uv` 命令均使用已锁定环境；首次静态检查发现新文件行长、未用导入及夹具变量类型问题，已限定修复并复跑同一冻结版：

```powershell
uv run --locked --no-sync pytest -q -s tests/unit/infrastructure/test_offline_schema_migration.py::test_converts_closed_legacy_snapshot_and_images
uv run --locked --no-sync ruff check scripts/migrate-schema-governance.py tests/unit/infrastructure/test_offline_schema_migration.py
uv run --locked --no-sync ruff format --check scripts/migrate-schema-governance.py tests/unit/infrastructure/test_offline_schema_migration.py
uv run --locked --no-sync mypy scripts/migrate-schema-governance.py tests/unit/infrastructure/test_offline_schema_migration.py
git diff --check HEAD
```

- 正向隔离演练 `1 passed in 1.29s`；Ruff lint 通过，格式检查两文件已符合，mypy 两文件无问题（现有 `dynaconf` 配置节提示），`git diff --check HEAD` 通过。曾使用 `uv run --locked --no-sync ruff format scripts/migrate-schema-governance.py tests/unit/infrastructure/test_offline_schema_migration.py` 仅格式化两份新增 Python 文件。指纹用只读 `git diff --name-only --no-renames HEAD`、`git ls-files --others --exclude-standard` 与 PowerShell SHA-256 复算。
- 未执行未知 revision、无偏移历史时间、缺图的反向参数化用例，也未执行全量、应用集成或现场切换/恢复。真实数据异常、超出样本规模的转换与外部队列状态未经验证。未接触实际开发库、备份、图片、服务、外部会话、worktree 或 Git 持久状态。本交付仅供独立复验，不代表已接受、可部署或已恢复开发库。

### 同版复验与限定返工

- 2026-11-19 18:13:49：#629 的冻结版独立复验与主会话复算均匹配 3/110/107/71 路径指纹，`git diff --check HEAD` 通过。指定正向演练 1 通过，静态检查通过；两轮独立临时样本验证了源库和图片不变、两端完整性与外键检查、按作用域重挂、事件高水位及投递时间等价，直接 SQL 确认投递更新时间无 NULL。这些证据保留为 #627 冻结版结果。
- 裁决：`TsidSource()` 的默认节点 `0` 与 [T02 交付约定](T02-server-identifiers.md#t03t04-接口)的独立显式离线节点不符。样本内唯一性通过，没有观察到数据损坏；本次不豁免该契约，退回 `running`，沿用 `SG-20261119-T04-01` 和修订 3。离线转换显式使用 `TsidSource(node=1023)`，服务端节点 `0`、固定角色种子 ID 和目标唯一性检查不变。单次演练不据此承诺多个离线实例之间的全局唯一性。
- 仅解除 `scripts/migrate-schema-governance.py`、`tests/unit/infrastructure/test_offline_schema_migration.py` 和本 task 的冻结。`migrations/README.md` 的单路径指纹 `461D174116990CD83BA9622E06974D604C2D314055DCE8447078159567C91731` 及上游 107/71 路径保持不变。补现有隔离正向用例，断言新生成的 ID 的节点位为 `1023`，固定种子 ID 单独断言不变，保留规范格式与唯一性校验。重跑该正向用例、对应静态和差异检查；重提前登记新 3/110 路径指纹与实际结果，冻结后由测试同版复验。
- 验证授权不变：反向分支仅审阅，不运行反向、全量、应用集成或现场切换/回滚。只使用隔离临时库和合成图片，不触碰实际开发库、备份、图片、运行服务、会话、worktree 或 Git 持久状态。
- 2026-11-19 18:16:02：高级开发 `member-b53c76acb705` 按 #592/#630 接续 `SG-20261119-T04-01`（修订 3）。共享 `develop` / `613f6a5c1b4292b95babfa57017004ace4538174` 上复算返工前的 3/110/107/71 路径及冻结指南单路径指纹，均与上文一致。仅按本节解冻边界返工，无开工阻塞。

### 返工交付

- 2026-11-19 18:17:38：`SG-20261119-T04-01`（修订 3）返工差异已冻结，待架构师重新登记并安排同版独立复验。基线仍为共享 `develop` / `613f6a5c1b4292b95babfa57017004ace4538174`。本轮仅改 `scripts/migrate-schema-governance.py`、`tests/unit/infrastructure/test_offline_schema_migration.py` 和本记录，无新增路径。
- 沿用上文的路径集合与哈希算法：T04 **3 路径** `2D5B7B9CBD2B887070B88DB3E8F40C79489EEC85EA0FDAB004EB90B3074BF94F`；联合 **110 路径** `EEEC6FF8DF509959CD0C370CC3A722F2668DDA878ED6666BBBA0A1608FECDAB5`。上游 **107 路径** `21B5A7F9EDA259BE2B016C18480EC4DF51828554A7088E07231F055FA037D736`、**71 路径** `43234D6132B1FB30412AC5EAAB23D72AE9F20AF6A5322647DF0A1E692C2B681C` 和指南单路径 `461D174116990CD83BA9622E06974D604C2D314055DCE8447078159567C91731` 复算均不变。
- 转换器显式调用 `TsidSource(node=1023)`；未改在线默认节点 `0`、固定角色 ID 或 `used` 去重。原正向用例解析报告中实际新生成的 TSID，断言节点位均为 `1023`、全部映射 ID 规范且唯一，精确核对旧固定角色到目标 `0000000000001`、`0000000000002`、`0000000000003` 的映射，并直接查询目标库确认这三个 ID。既有行数、顺序、图片与时间断言保留；单次转换不证明多个离线实例间的全局唯一性。
- 从仓库根目录重跑上节原五条命令：指定 `pytest` 正向用例 `1 passed in 1.31s`，`ruff check` 通过、`ruff format --check` 两文件已符合、`mypy` 两文件无问题（现有 `dynaconf` 配置节提示），`git diff --check HEAD` 通过。首轮新增断言因集合与字典值视图直接相减报错，`mypy` 同样报该类型错误；改用 `set.difference` 后复跑通过。未安装依赖。
- 未运行反向、全量、应用集成或现场切换/回滚；未操作真实库、备份、图片、运行服务、外部会话、worktree 或 Git 持久状态。等待独立复验和裁决，本交付不授权换库。

### 返工版仲裁

- 2026-11-19 18:21:06：主会话复算返工 3 路径及联合 110 路径，与 #632/#633 一致；冻结的上游 107/71、T03 36 路径和指南单路径均未变，`git diff --check HEAD` 通过。审阅确认转换器显式使用节点 `1023`，在线默认 `0`、三条固定角色种子及转换内去重均保留。
- 测试 #633 在同一冻结版独立运行指定正向用例（1 通过）、Ruff lint/格式、mypy 与差异检查，并用两轮自建临时样本核对：新生成的 6 个及 11 个 ID 均为节点 `1023` 且各次转换内唯一；固定种子不变，源库及图片哈希未变，两端完整性与外键检查均通过，投递历史更新时间无 NULL，时刻及微秒精度保留。
- 裁决：解除 #630 的发号契约阻塞，按修订 3 接受 T04 返工交付，总计划登记 `accepted`。不承诺多离线实例全局唯一；未知 revision、无偏移时间、缺图的反向用例、全量、应用集成、真实规模转换及现场切换/回滚未验证。此裁决不启动整体 Verification，不授权更改运行服务或实际资产。
