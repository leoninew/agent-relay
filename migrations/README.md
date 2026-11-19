# 数据库迁移指南

使用 SQL-first Alembic，配置入口为仓库根目录的 `alembic.ini`。

## 初始化空库

在仓库根目录运行，默认使用 `dev`，可追加 `profile=<名称>` 覆盖。目标数据库取自对应环境的 `database.path`：

```bash
make migrate
```

PowerShell 等价命令：

```powershell
$env:CONFLUA_PROFILE = 'dev'
uv run --locked python -m conflua.migrate
```

默认数据库为 `data/conflua.db`。服务启动时也会初始化空库；该命令不会自动转换旧版数据库。不要用 `alembic stamp` 绕过版本检查。

## 修改结构

1. 在 `sqlite/sql/<批次>/` 编写 `.up.sql`，显式定义表、约束和索引。
2. 在 `sqlite/versions/` 添加 revision，以 `down_revision` 连接当前 head，并在 `upgrade()` 中通过 `execute_sql_file()` 显式调用 SQL 文件。
3. 同步更新 `src/conflua/infrastructure/persistence/migrations.py` 中的 `MIGRATION_HEAD`，以及对应持久化读写实现。

主外键、查询和索引字段使用列或关联表；消息能力引用等附属值数组使用 JSON。不从业务模型自动生成 DDL。

数据库负责列类型、非空、默认值、主外键、唯一性，以及简单的单列布尔、枚举和数值范围。频道作用域外键和发布幂等唯一索引不能用应用层先查后写替代。TSID 编码、JSON 内容、成员身份、删除或归档与时间的配对、投递状态与回执字段的组合由应用写入路径负责，不在 SQL 或 ORM 里再实现一遍。离线工具直接写 SQL 时也须遵守这些规则。

## 离线核对 SQL

查看迁移链及从当前基线升级的 SQL，不连接数据库：

```bash
uv run --locked alembic history
uv run --locked alembic heads
uv run --locked alembic upgrade head --sql
```

## 基线与旧库

当前新库的 `0001_baseline` 对应 `schema_governance_20261119`，包含当前完整建库 SQL 和种子。开发库的离线转换只接收旧版 `member_roles_20261118`；更早的 revision 须先在停机副本上用兼容的旧版迁移链升级并复核到这个 revision。当前版本不提供原地更新或降级，新旧版本不能混用同一套数据。

不保留历史数据时，单独备份原资产，再把当前版本配置到新的空数据库及图片目录。迁移命令不会自动清理旧文件。

实体表先定义自身 `id`（事件表为 `event_id`），随后是外键。物理列序不改变复合主键的既有顺序。内置角色的 TSID 由 `tests/unit/domain/test_identifiers.py::test_generate_offline_role_seed_batch` 在离线节点一次性生成并固定到种子 SQL，建库不重新发号。

## 离线转换与切换

1. 获得切换授权后，核对实际 `database.path` 及其同级 `rooms/`。停止在用服务、dispatcher 和所有写入者，保持停机直到两项资产都已切换或恢复。记录旧应用版本和配置；对留在外部队列中的投递另行确认，转换脚本不查询、取消或重发。
2. 用 SQLite Backup API 或 `sqlite3` 的 `.backup` 命令生成一致的数据库快照，关闭并核对快照没有 `-wal`、`-shm`、`-journal` 伴随文件；不要通过单独复制活库主文件或删除伴随文件来生成快照。同一停机窗口完整备份 `rooms/`，保留目录结构；没有历史图片时准备一个空目录。将数据库和图片备份作为一对保存，并用它们生成独立的转换输入副本。
3. 在仓库根目录执行以下命令，替换为副本和新输出目录的显式路径。输出目录的父目录必须已存在，输出目录本身不得存在；脚本不读取 profile，不覆盖源或已有目录。

   ```powershell
   uv run --locked python scripts/migrate-schema-governance.py --source-db 'D:/staging/source/conflua.db' --source-images 'D:/staging/source/rooms' --output 'D:/staging/converted'
   ```

   如果曾手动合并频道且只移动了事件的频道列，可在核实历史记录后追加 `--merged-event-channel ROOM DESTINATION ORIGIN`。仅该房间、该目标频道的历史事件可以从显式来源解析缺失的选题、成员、位置实体或原频道本身。事件仍属于目标频道，普通外键和其他事件继续严格校验；报告包含来源和各类型数量。

4. 只有命令退出码为 `0` 且 `report.json` 已写入，才复核同一输出目录内的 `conflua.db` 与 `rooms/`。检查两端 revision、逐表行数、键映射、历史时间及回填数、生命周期状态与图片校验和，并对输出库独立执行 `PRAGMA integrity_check;`（应仅有 `ok`）、`PRAGMA foreign_key_check;`（应无行）及 `SELECT count(*) FROM deliveries WHERE updated_at IS NULL;`（应为 `0`）。核对旧外部会话标识、回执、路径、事件高水位及业务顺序。脚本只转换应用识别且位于原消息作用域的受管图片链接，不迁移其他目录、外部链接或工作树。空值以外的历史时间若无显式时区偏移，脚本按表、记录和列报告并停止；不要猜测时区。任何失败都不使用输出；保留错误信息，排除原因后在另一个全新目录重试。
5. 停机状态下由操作人从**同一输出**同时准备数据库和同级 `rooms/`，切换两项资产及对应新版本配置，复核放置路径、校验和及旧备份仍可恢复。不要把新图片与旧图片目录合并，也不要混用新旧版本；两项资产都就位后才启用新版本。

## 失败恢复

- 转换或复核失败且未切换：保持现有磁盘资产不变；需要恢复服务时继续使用旧版本和原本配对的数据。
- 已切换后回滚：再次停止服务和 dispatcher，隔离保留新库和新图片，避免丢失切换后写入。将旧数据库快照与同一停机点的完整旧 `rooms/` 一起恢复到核对过的路径，使用旧版本和旧配置；不要复用新库的 SQLite 伴随文件。核对旧 revision、完整性及图片后再恢复旧服务。切换后产生的业务或外部队列变化不能靠还原 SQLite 自动撤销，须单独核对。
