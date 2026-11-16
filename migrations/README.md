# 数据库迁移指南

使用 SQL-first Alembic，配置入口为仓库根目录的 `alembic.ini`。

## 执行迁移

在仓库根目录运行，默认使用 `dev`，可追加 `profile=<名称>` 覆盖。目标数据库取自对应环境的 `database.path`：

```bash
make migrate
```

PowerShell 等价命令：

```powershell
$env:CONFLUA_PROFILE = 'dev'
uv run --locked python -m conflua.migrate
```

默认数据库为 `data/conflua.db`。服务启动时自动执行迁移。

## 修改结构

1. 在 `sqlite/sql/<批次>/` 编写 `.up.sql`，显式定义表、约束和索引。
2. 在 `sqlite/versions/` 添加 revision，以 `down_revision` 连接当前 head，并在 `upgrade()` 中通过 `execute_sql_file()` 显式调用 SQL 文件。
3. 同步更新 `src/conflua/infrastructure/persistence/migrations.py` 中的 `MIGRATION_HEAD`，以及对应持久化读写实现。

主外键、查询和索引字段使用列或关联表；消息能力引用等附属值数组使用 JSON。不从业务模型自动生成 DDL。

## 离线核对 SQL

查看迁移链及从当前基线升级的 SQL，不连接数据库：

```bash
uv run --locked alembic history
uv run --locked alembic heads
uv run --locked alembic upgrade head --sql
```

## 基线与旧库

当前 `0001_baseline` 直接创建完整结构，revision 保持为 `channel_description_20261114`。已经升级到该版本的数据库无需重建，执行迁移不会修改其数据。

更早的 revision 不在合并后的迁移链上，不提供自动升级、旧数据转换或降级。需要保留旧数据时，可先使用合并前的版本升级到 `channel_description_20261114`，并在升级前停止服务及 dispatcher、备份数据库和图片目录。新旧服务不能混跑。

需要重建时，先停止相关服务、核对路径并按需保留数据，再对空库执行迁移。迁移命令不会自动删除或重建旧库。
