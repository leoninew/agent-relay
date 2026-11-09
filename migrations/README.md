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

新增 revision 通过 `down_revision` 连接当前 head，并显式列出 SQL 文件，不从模型生成 DDL。只支持升级；在线迁移和离线 SQL 均启用事务与外键。

当前 head 为 `user_member`：在 `member_api` 后引入不绑定会话的固定用户成员，并将历史用户消息转换为成员引用。

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

迁移使用 `database.path`。新库按完整链初始化，已有库只执行尚未应用的 revision。

`database.migrate_on_startup` 默认 `false`；设置 `AGENT_RELAY_DATABASE__MIGRATE_ON_STARTUP=true` 后，应用在初始化存储前执行迁移，失败则停止启动。`.env.dev` 已开启，`make webapi` 和容器入口均使用此开关。关闭时须先手动迁移。

运行目录为项目根目录，需包含 `alembic.ini`、`migrations/` 和 `config/`。

`SQLiteRoomStore` 只负责业务读写，迁移由 Alembic 和 `migration_sql.execute_sql_file` 执行。
