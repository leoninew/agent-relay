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

主外键、查询和索引字段使用列或关联表；消息能力引用等附属值数组使用 JSON。不从业务模型自动生成 DDL。

## 离线核对 SQL

查看迁移链及从当前基线升级的 SQL，不连接数据库：

```bash
uv run --locked alembic history
uv run --locked alembic heads
uv run --locked alembic upgrade queue_deleted_20261110:head --sql
```

## 基线与旧库

当前迁移链为 `0001_baseline` → `0002_capabilities_json`，对应 revision 为 `queue_deleted_20261110` → `capabilities_json_20261111`。未发布的原 `0002`、`0003` 已合并，直接增加 `messages.capabilities` JSON 数组列，旧消息默认为空数组，不创建中间关系表。

最终 head 保持不变，已升级到 `capabilities_json_20261111` 的开发库无需重复迁移或修改版本记录。

旧 revision（包括 `baseline_20261110`）不在合并后的迁移链上，不提供自动升级、旧数据转换或降级。需重建时，先停止相关服务、核对路径并按需保留数据，再对空库执行迁移。迁移命令不会自动删除或重建旧库。
