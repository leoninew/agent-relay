# Verification / 验证：SQLAlchemy 与 Repository 数据访问重构
最后修改时间: 2026-11-11 15:00:42

## Review status / 审查状态

Draft

2026-11-11 用户要求进入 Verification 且不再运行测试。本次依据已审查的实现、开发检查记录与当前工作区快照核对；未重新运行测试。结论供用户审查，不表示已获得用户最终验收。

## Intent alignment / 意图对齐

- 对照[意图 A01—A12](../intent/20261111-sqlalchemy-repositories.md)：运行时采用同步 SQLAlchemy 和业务能力仓储，请求事务与后台短事务各有明确所有者；继续使用 SQLite 和当前迁移 head。
- 原意图不包含变更公开接口。工作区另有独立房间改名接口和移除 Topic `messageCount` 字段的修改，最终实现及已有测试融合了它们；因此不能将当前整体工作区描述为相对原 HEAD 公开契约完全不变。这些独立修改不归属于本重构，未回退或修改其意图。

## Plan alignment / 计划对齐

- 对照[总计划修订 2](../plan/20261111-sqlalchemy-repositories.md)：T01—T06 均完成并由主会话接受；正式装配已切换，旧 sqlite3 运行时模块与旧事务类已移除。
- 同一请求或用例的仓储共享事务，外部 RPC 前使用独立短作用域；未引入模块专用 UoW、异步数据库访问、新数据库配置或 schema 迁移。

## Task deliveries and integration / 子任务交付与集成

以下哈希为原任务文件清单在 T06 集成后的工作区版本；接受过程及最初交付版本以总计划历史和各 task 为准。

| ID | 集成后清单 SHA256 | 审查与验收归属 |
| --- | --- | --- |
| T01 | `da36ac0bae8c5c33fc49f79d1d303ce4a4f1529fe5898d62122e982a836f4240` | 映射/事务基础；A01—A05、A10、A11 的基础证据已审查 |
| T02 | `58fd2acc2a6b151ccd989d5ed69af7c164d1fc097ba31767b87b9ebebeb7b56f` | 房间资源；A02、A05—A07 的局部证据已审查 |
| T03 | `877479dfccf85c4144a04a0dd8274d8e0e18681a3001495bfaf5dd86b1d02fba` | 消息与查询；A02、A05—A08、A10 的局部证据已审查 |
| T04 | `5a3c031a54bc2a3add8882aec01d0510bc0afb4c20a48955a9984e48149999e5` | 投递条件写入；A04、A07、A08、A11 的局部证据已审查 |
| T05 | `40b9e09f30cdc50787a2bacbf7f49b490d3f523c5f63344da35112c44eabb25a` | 上下文事务；A04、A07、A09 的局部证据已审查 |
| T06 | `83d18308ac286111379e4ae8aa653acfdb0664fb0ddc685258f380b49755c6aa` | 正式接线、旧实现移除与完整开发回归；A01—A12 的组合证据已审查 |

本次复算的 T01、T02 集成后子清单与 T06 原记录中的子清单哈希不同：除已记载的事务/测试演进外，最终组合还包含独立 Topic 字段变更所需的 mapper、房间仓储、查询及测试适配。已更正 T06 记录和总计划，保留各阶段原始接受版本。T03 的集成后变化为局部夹具复用正式适配，T04/T05 哈希与接受版本一致。

T01—T06 去重后的 53 项工作区组合清单 SHA256 为 `18f64536138a34f360a4554bc5a96db26623f813641c07a7df4c6d83d0c12edb`，与 T06 交付、既有完整回归及本次复算一致。独立的 contracts、service、HTTP routes 和 domain models 四项背景文件哈希也与 T06 记录一致；因此本次核对的产品/测试组合与已有开发检查所针对的快照一致。

## Actual diff summary / 实际差异摘要

- 引入 SQLAlchemy Engine/sessionmaker、14 表映射、时间/回执映射、SQLite 方言边界及资源、消息、投递、上下文仓储。
- HTTP、后台和成员上下文统一接线；显式保持请求事务、短事务、事件、锁路径、RPC 与 WebSocket 生命周期边界。
- 删除六个旧 sqlite3 持久化模块及 SQLiteTransaction，更新公共/局部测试夹具、集成测试及后端架构说明。
- 原有暂存区和独立 design/web、房间改名及 Topic 字段变更均保留；本次没有调整暂存状态。

## Expected vs actual changed files / 预期与实际修改文件对比

- 计划中的持久化基础、四类仓储、组合查询、入口装配、测试和架构说明均有对应交付；T06 的 [30 项清单](../task/20261111-sqlalchemy-repositories/T06-integration.md)包含 24 个现存文件及 6 个删除项。
- 未修改 Alembic 历史链、数据库 schema、`pyproject.toml` 或锁文件。T06 未按最初的预期修改 RoomService/MemberSessions，而是保留既有中立端口并在装配层组合仓储；与修订 2 的统一事务设计一致。
- 独立的应用、HTTP、domain 和前端修改与本任务并存，不能将整个暂存区或工作区直接等同于本重构的提交范围。

## Acceptance criteria checklist / 验收标准检查清单

下列结果依据已审查的节点与 T06 开发证据，不代表本次重新执行测试；公开契约的独立变更见意图对齐章节。

| 标准 | 证据与结果 |
| --- | --- |
| A01 | 14 表类型映射及单一 SQLAlchemy 正式装配；既有 AST 审查未发现产品源码直接导入 sqlite3。通过。 |
| A02 | 四类能力仓储及现有中立查询端口；应用/领域不接触 ORM 或 Session。通过。 |
| A03 | 已有请求事务测试覆盖惰性共享、响应前提交、异常/取消回滚和提交失败。通过。 |
| A04 | 已有 HTTP、后台与 fake RPC 检查覆盖短事务分段和 WebSocket 等待释放。通过。 |
| A05 | Alembic 临时库比较当前 head 映射、约束和历史时间/回执格式；不覆盖旧 revision 或真实库。通过当前 head 范围。 |
| A06 | 已有并发序号、发布幂等、项目和成员绑定竞争，以及 BEGIN IMMEDIATE 检查。通过。 |
| A07 | 已有资源、消息、投递及上下文事件原子性、游标与回滚检查。通过。 |
| A08 | 已有队列范围、分页、清空、历史状态/回执、竞争及 unknown 不重发检查。通过。 |
| A09 | 已有独立可见性、字面搜索、双向分页、实际提供记录及并发位置单调性检查。通过。 |
| A10 | 已审查运行时 SQLAlchemy 表达式及隔离的 SQLite PRAGMA/BEGIN/rowid/instr/julianday 例外。通过。 |
| A11 | 已有 Engine 所有权、关闭顺序、文件锁路径、跨 worker 收尾与 CLI/MCP 回归。通过测试范围。 |
| A12 | 已有完整后端测试、类型/lint/格式检查、更新后的夹具和架构文档证据；本轮不重跑。通过约定开发检查范围。 |

## Test / command results / 测试 / 命令结果

- 本次用户明确要求不再跑测试，故 Verification 阶段没有重新执行测试、类型检查或 lint；本次执行只读的文件、差异与 SHA256 核对。
- 前一轮主会话在相同 53 项组合及四项背景文件快照上独立执行 `uv run --locked pytest -o addopts=-ra tests -q`：474 passed；同时 `mypy src tests`、`mypy migrations`、Ruff lint/格式及暂存/未暂存 diff 空白检查通过。
- T06 交付还记录单元测试 33 passed、指定集成测试 57 passed、正式装配边界测试 8 passed；其他节点的定向证据见各 task。本次不将这些历史运行描述为新执行结果。
- 未对真实数据库、运行中的服务或真实 Codex 做验证；未运行前端检查。测试使用临时数据库、fake 和测试协议进程，详见 T06 记录。

## Missed or expanded scope / 遗漏或扩大的范围

- 未发现本重构范围内遗漏的实现。仓储组合采用装配层适配而非修改应用服务，属于计划内可接受的文件差异。
- 独立房间改名、Topic 字段移除及 web 变更与本重构并存；本验收不评价这些独立变更的产品授权、前端行为或向后兼容性。提交时需按实际归属拆分并核对暂存内容。

## Risks / 风险

- SQLAlchemy 模型与 SQL-first Alembic 同时描述结构，后续 schema 修改需同时维护并验证；当前仅承诺 SQLite 与 `queue_deleted_20261110` head。
- 未接触真实历史库或线上服务，临时历史格式 fixture 和并发测试不能完全替代实际部署环境验证。
- 53 项组合清单及四项背景文件哈希与既有回归匹配，但其他独立工作区文件不属于该清单；本次验证不对这些文件的变化作全面担保。

## Incomplete items / 未完成事项

- 本验证记录待用户审查；未执行 Git 暂存或提交。
- 真实环境验证和独立前端变更的验证不在本次授权范围。

## Conclusion / 结论

在用户要求不重跑测试的条件下，当前已核对的集成快照与既有 474 项后端通过证据一致，本重构 A01—A12 在上述范围内具备验收证据。公开契约存在独立并行变更，不能对整个工作区相对原 HEAD 的接口兼容性作无条件结论。验证记录为 Draft，等待用户审查。
