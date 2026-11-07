# 数据库迁移
最后修改时间: 2026-11-07 20:10:13

沿用 K12 的 SQL-first Alembic 组织方式，迁移文件统一放在仓库根目录的 `migrations/`，配置为根目录 `alembic.ini`。

```text
alembic.ini
migrations/
  sqlite/
    env.py
    versions/                  # 薄 revision，显式列出 SQL
    sql/<批次>/                # 实际 .up.sql
```

执行顺序由 revision 的 `down_revision` 声明，不依赖目录扫描排序，也不从模型生成 DDL。当前链为 `room_resources → remove_member_role → sidebar_node_actions`：分别创建七张资源表和约束、清除成员 JSON 中的角色字段、为话题和成员增加删除标记及活动名称/会话的唯一索引。第三个 revision 在外键保持启用的事务内复制资源和关联记录，按先子后父删除旧表、先父后子重命名新表的顺序完成结构替换。只支持升级，downgrade 明确报错。

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

迁移使用集中配置的 `database.path`。新库按完整链初始化，已有 Alembic 库只执行尚未应用的 revision。`make webapi` 前置执行迁移，失败则停止启动；容器复制根目录 `migrations/` 和 `alembic.ini`，默认命令也是先迁移再启动服务。

直接运行 API 前须先执行迁移。与 `config/` 一样，迁移文件是部署目录中的资源，运行目录为项目根目录；不放入 `src/agent_relay/`，不根据源码或安装包路径回退查找。

## 数据访问边界

`SQLiteRoomStore` 使用现有 `sqlite3` 管理资源读写、外键和事务，不执行建表、历史修补或迁移。Alembic 使用 SQLAlchemy 管理迁移连接，revision 通过 `migration_sql.execute_sql_file` 执行显式 SQL；业务访问未改成 ORM。

新增变更以新 revision 连接当前 head，并显式列出 SQL 文件。应用和迁移入口都不探测旧结构、自动 stamp 或选择兼容分支。迁移框架切换前的本地开发库已单独核对并转入 Alembic，保留原房间和话题；这项离线操作不作为产品兼容功能。
