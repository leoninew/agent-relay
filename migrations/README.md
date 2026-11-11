# 数据库迁移指南

使用 SQL-first Alembic，配置入口为仓库根目录的 `alembic.ini`。

## 执行迁移

在仓库根目录运行，默认使用 `dev`，可追加 `profile=<名称>` 覆盖。目标数据库取自对应环境的 `database.path`：

```bash
make migrate
```

PowerShell 等价命令：

```powershell
$env:AGENT_RELAY_PROFILE = 'dev'
uv run --locked python -m agent_relay.migrate
```

默认数据库为 `data/agent-relay.sqlite3`。`.env.dev` 已启用启动迁移；其他环境可配置 `AGENT_RELAY_DATABASE__MIGRATE_ON_STARTUP=true`。

## 修改结构

1. 在 `sqlite/sql/<批次>/` 编写 `.up.sql`，显式定义表、约束和索引。
2. 在 `sqlite/versions/` 添加 revision，以 `down_revision` 连接当前 head，并在 `upgrade()` 中通过 `execute_sql_file()` 显式调用 SQL 文件。
3. 同步更新 `src/agent_relay/infrastructure/persistence/migrations.py` 中的 `MIGRATION_HEAD`，以及对应持久化读写实现。

主外键、查询和索引字段使用列或关联表，JSON 仅保存额外元数据。不从业务模型自动生成 DDL。

## 手动验证 SQL

SQL 执行检查使用通用的 `integration` 标记，默认 pytest 运行会排除带此标记的测试。手动运行：

```bash
uv run --locked pytest tests/integration/test_migration_sql.py -m integration
```

测试按路径顺序在临时 SQLite 数据库中执行 `sqlite/sql/` 下的全部 `.up.sql`，并检查数据库完整性和外键，不操作开发库。

## 基线与旧库

当前基线和 head 均为 `queue_deleted_20261110`。新库一次创建完整结构，包括投递记录的可空 `deleted_at`；已在此 revision 的数据库无需重建或重新标记。

旧 revision（包括 `baseline_20261110`）不在合并后的迁移链上，不提供自动升级、旧数据转换或降级。需重建时，先停止相关服务、核对路径并按需保留数据，再对空库执行迁移。迁移命令不会自动删除或重建旧库。
