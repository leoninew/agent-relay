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

当前迁移链为 `0001_baseline` → `0002_capabilities_json` → `0003_delivery_steering` → `0004_message_soft_delete` → `0005_channels` → `0006_channel_description`，当前 revision 为 `channel_description_20261114`。

`0002` 直接增加 `messages.capabilities` JSON 数组列，旧消息默认为空数组。此前未发布的能力引用中间迁移已合并，不创建中间关系表。

`0003` 增加投递的 `submission_method` 与 `steered_turn_id`，区分原生队列与当前轮次输入。旧非 pending 投递标记为 queue，旧 pending 在实际发送时自动选择；不重放或移动已有队列消息。使用前按原入口升级到新 head，不修改旧 revision 或手工更改版本记录。新旧服务不能混跑，新服务的 steer 事实不得交给旧代码重写。

`0004` 增加消息的 `deleted_at`，旧消息默认未删除。聊天室清空使用软删除，同时标记投递记录并沿用成员软删除；消息关联、上下文查阅记录和消息序号保留，后续发布不复用原序号或发布标识。

`0005` 新增频道及房间归档时间，重建关联表的频道复合键。每个旧房间回填 `channel-default`，保留原目录、ID、seq、软删除、订阅、引用、上下文、投递状态和回执；事件自增高水位也保留。迁移只执行 SQL，不调用 Git/Codex，不创建 worktree。SQLite 外键保持开启，DDL、数据及 revision 在同一事务内提交；失败完整回滚。可以通过 `uv run --locked alembic upgrade message_deleted_20261112:head --sql` 预先审查 SQL。

升级前停止服务及 dispatcher，备份 SQLite 数据库和图片目录，新旧服务不能混跑。频道及房间删除改为软归档；归档保留目录、分支和历史，不撤回已进入 Codex 的输入。新 worktree 位于数据根的 `worktrees/<room-id>/<channel-id>`。

`0006` 增加频道描述并移除频道状态、创建错误和核验专用仓库字段。旧频道描述初始化为空，名称、目录、归档时间及全部关联保留；重建频道表时延迟外键检查，核对完整性后恢复即时检查。频道创建使用现有请求事务切面，失败回滚数据库写入，不自动删除外部 Git 目录或分支。

不支持自动降级频道结构，优先前滚修复。确需恢复旧备份时保持服务和投递停止，先核对外部输入及回执，不能直接把可能已执行的消息按旧 pending 状态重新投递。

旧 revision（包括 `baseline_20261110`）不在合并后的迁移链上，不提供自动升级、旧数据转换或降级。需重建时，先停止相关服务、核对路径并按需保留数据，再对空库执行迁移。迁移命令不会自动删除或重建旧库。
