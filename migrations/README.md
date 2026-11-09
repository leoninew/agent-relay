# 数据库迁移

使用 SQL-first Alembic，配置为根目录 `alembic.ini`。

```text
alembic.ini
migrations/
  sqlite/
    env.py
    versions/                  # 薄 revision，显式列出 SQL
    sql/<批次>/                # 实际 .up.sql
```

## 执行

在项目根目录运行：

```bash
make migrate profile=dev
```

PowerShell 等价入口：

```powershell
$env:AGENT_RELAY_PROFILE = 'dev'
uv run --locked python -m agent_relay.migrate
```

迁移使用配置中的 `database.path`。`.env.dev` 已开启启动迁移，运行 `make webapi` 时自动执行；其他环境可设置 `AGENT_RELAY_DATABASE__MIGRATE_ON_STARTUP=true`，或使用上面的命令手动执行。

运行目录为项目根目录，需包含 `alembic.ini`、`migrations/` 和 `config/`。

## 修改结构

在 `versions/` 中添加 revision，通过 `down_revision` 连接当前 head，并在 `upgrade()` 中显式调用对应 SQL 文件。SQL 放在 `sql/<批次>/`，不从模型生成 DDL。
