# 数据库迁移指南

使用 SQL-first Alembic，配置入口为仓库根目录的 `alembic.ini`。

## 执行迁移

在仓库根目录运行，目标数据库取自对应环境的 `database.path`：

```bash
make migrate profile=dev
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

## 基线与旧库

当前基线为 `baseline_20261110`，不兼容旧版整模型 JSON 存储，不提供旧数据转换或降级。

当前 head 为 `queue_deleted_20261110`，在上述基线之后为投递记录增加可空 `deleted_at`，用于队列业务记录的逻辑删除；已有消息、投递状态和回执保持不变。基线数据库可直接执行迁移命令升级，无需重建。

不兼容的更早基线数据库需先停止相关服务、核对路径并按需保留数据，再使用空库重新执行迁移。迁移命令不会自动删除或重建旧库。
