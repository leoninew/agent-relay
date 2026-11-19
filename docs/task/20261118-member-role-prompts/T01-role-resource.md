# Task / 子任务 T01：角色持久化与 API
最后修改时间: 2026-11-18 21:32:21

## 审查状态

Accepted。方案接受与交付接受分别记录。

## 父任务与权威记录

- [总意图](../../intent/20261118-member-role-prompts.md)；[权威总计划](../../plan/20261118-member-role-prompts.md)；方案修订 1。

## 目标与验收

A01：提供站点级角色资源、无分页 CRUD API 和可与加成员共用请求事务的按 ID 读取能力。旧库升级不改写已有数据，角色在重开数据库后仍可读取。

## 范围与输入

- 无前置任务，使用总计划中的 `MemberRole` 和 `/api/member-role` 契约。
- 修改范围：角色应用 DTO、服务和持久化端口，SQLAlchemy 角色表与存储，SQL-first Alembic 增量、迁移 head、HTTP 路由和 bootstrap 依赖，以及相关测试。不改成员用例、投递或前端。

## 技术设计与实施

1. 在 `workspace_paths_20261117` 后新增增量迁移，建站点级 `member_roles` 表，包含 `id`、`name` 和 `prompt`；数据库约束保证规范化名称唯一。同步 ORM、迁移 head 和迁移说明。
2. 角色 DTO 和服务负责输入规范化、稳定排序、生成 ID 与错误映射；库层唯一约束兜底并将已识别的名称冲突映射为 409，其余存储失败沿用现有错误处理。仅删除模板，无成员或历史消息级联。
3. 用现有请求事务机制绑定角色存储，交付 `MemberRoleService.get(role_id)`；若事务已打开，该读取必须和成员存储复用同一个 SQLAlchemy session。路由不接收房间或频道 ID。
4. 与普通消息共用正文校验，首版不引入能力字段。若提取现有校验函数，保持 `CreateMessage` 的原有校验顺序与行为，通过回归用例验证。

## 检查与风险

- 针对性 pytest：临时 SQLite 全新建库及旧 head 升级、保留旧数据、重开读取、列表排序、CRUD、校验、409/404、角色读取复用请求事务；如共用消息校验，同时跑 `tests/unit/application/test_request_contracts.py`。
- 运行改动范围 Ruff、Mypy。向 T02 提供 HTTP 契约和可用迁移版本，向 T03 提供事务内读取入口；不在开发数据库验证迁移。

## 交接、进展与交付

- 分配 `MRP-T01-01`，执行者为高级开发 `member-afabe09f28af`，方案修订 1，授权来源为频道 #321。代码和回报均在 `D:/SourceCodes/mywork/conflua`，基线 `315b40b` 加已有无关改动。先核对总计划和 SpecFlow 协作契约，再在本文写接收记录；无前置交付。
- 接收（21:22:58）：已核对权威执行登记、方案修订、#324 派发和工作区 `315b40b`。仅实施 T01，保留无关 CLI 改动，不操作在用数据库、不暂存或提交。
- 检查候选：权威工作区 `315b40b` 上的未暂存 T01 变更包含 `migrations/README.md`、`0007_member_roles` 的 SQL 和 revision、持久化 `migrations.py`/`models.py`/`repositories/member_roles.py`、应用 DTO `member_roles.py`/`messages.py` 及 `application/member_roles/`、`bootstrap/dependencies.py`、接口 `dto.py`/`http/routes.py` 及 `http/member_roles/`、`tests/unit/interfaces/test_member_roles.py`/`test_dependencies.py`。没有改动加成员、投递或 Web。
- A01 实现与证据：增量迁移 `member_roles_20261118`，全站 `GET/POST /api/member-role` 和 `PATCH/DELETE /api/member-role/{role_id}`，稳定排序、规范化后名称唯一、公开错误码和请求事务内 `MemberRoleService.get(role_id)`。临时库用例覆盖全新库 CRUD、旧 head 升级保留成员与消息、重开读取和未提交角色仅在请求范围内可见；请求用例覆盖名称冲突、缺失与非法正文。共享的普通消息正文校验应一并回归。
- 交付（`MRP-T01-01`）：`D:/SourceCodes/mywork/conflua` 的 `315b40b` 基线加上述 19 个实现、迁移和用例文件；未暂存或提交。交付内容指纹 `907909580a59bfbb78cdd0545e45bb83d22ee073`（按路径字典序排列 `git hash-object` 文件哈希与路径，再对清单计算 `git hash-object --stdin`；不含过程文档、无关 CLI 改动）。无前置交付。
- 复验依据频道 #331：中级开发以 `.venv` Python 3.12.12 跑 `test_member_roles.py`、`test_dependencies.py`、`test_request_contracts.py`，18 项通过；相关 18 个 Python 文件的 Ruff lint、Ruff format --check、Mypy 均通过；`git diff --check` 通过。#329 首轮的三处 Ruff 行宽/格式问题由高级开发在 #330 到达前等价换行修正，中级开发只读复跑。
- 未运行全量检查、在用数据库迁移或真实 Codex 投递；后两者不属于 T01。T02 可消费上述 API，T03 可在创建成员的请求事务内调用 `MemberRoleService.get(role_id)`；请架构师审查后放行。
- 本文用于接收、进展、阻塞和交付记录。交付须附实际变更、对应验收证据、可访问版本、检查结果及剩余风险；摘要默认由用户转交主会话。
