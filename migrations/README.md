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

`0001_baseline` 创建频道结构，revision 为 `channel_description_20261114`；当前 head 为 `channel_status_20261117`。增量 `0002_delivery_retry` 增加投递尝试计数（旧行默认 0）与下次尝试时间（旧行默认空），保留原消息、回执和状态；历史 unknown 不自动重发或作为新机制的顺序屏障。`0003_member_channels` 将活动会话绑定的唯一范围改为频道；合并后的 `0004_simplify_paths` 删除冗余路径索引键，仅为独立 worktree 保留目录、普通频道从房间目录派生，并删除会话目录字段，保留会话与成员、消息和投递历史。`0005_channel_status` 增加 `active` / `archived` 状态，旧频道默认 `active`；归档只修改状态，不修改原有删除标记或清理成员、消息、投递和目录。已升级到频道基线的数据库可直接增量升级，无需重建。

更早的 revision 不在合并后的迁移链上，不提供自动升级、旧数据转换或降级。需要保留旧数据时，可先使用合并前的版本升级到 `channel_description_20261114`，并在升级前停止服务及 dispatcher、备份数据库和图片目录。新旧服务不能混跑。

`0004_simplify_paths` 同时保留房间的 `raw_project_path`（用户原始输入，仅展示与编辑）和 `project_path`（规范路径，用于业务执行）。创建和编辑从请求的 `projectPath` 原样保存前者，去除外围空白并规整分隔符及点路径后保存后者，保留大小写。API 房间响应同时返回 `rawProjectPath` 和 `projectPath`。历史房间以现存 `project_path` 回填原始路径，无法恢复已丢失的输入格式。已执行旧版 0004 的开发库需单独补齐这一列和回填，不重放原有删列操作，也不修改版本戳。

需要重建时，先停止相关服务、核对路径并按需保留数据，再对空库执行迁移。迁移命令不会自动删除或重建旧库。
