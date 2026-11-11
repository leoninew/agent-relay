# Verification / 验证：后端三层职责审视与业务组织调整
最后修改时间: 2026-11-11 17:34:25

## Review status / 审查状态

Draft

2026-11-11 用户明确要求完成验证。本报告记录已执行的整体核对和检查，结论供用户审阅；Draft 是报告审查状态，不表示检查尚未执行。

此报告主体记录职责调整完成时的结果；后续测试整理结果见以下追加记录，当前测试入口见[后端架构说明](../design/backend-architecture.md)。

## 测试整理追加记录

### 第二轮：减少重复与低价值场景

- 按用户要求继续精简：单元用例从 126 增至 135，集成用例从 361 减至 107，合计从 487 减至 242，集成用例减少约 70%。
- 订阅修改后的路由、历史接收人、固定用户、投递历史翻页、清队列 RPC 编排和事务中间件使用单元测试。删除 HTTP/CLI/MCP 的重复业务枚举，以及重复的 RoomStore、RoomQueries 集成模块。
- 持久化测试收敛为真实 SQL 筛选/分页、外键、关键竞争与原子性代表场景；删除逐写入阶段故障注入、参数交叉组合、内部查询次数断言和人为数据损坏变体。HTTP 协作保留 6 例，CLI、MCP 各保留 2 例。
- 数据库集成测试仍全部使用 SQLite 内存模式，保留独立连接与真实迁移；未修改产品代码或独立前端工作。
- `uv run --locked pytest -o addopts=-ra tests -q --tb=short`：242 passed（30.74s）；收集结果为 135 unit、107 integration。上一轮完整后端为 487 passed（61.39s），耗时仅作本机参考。
- `uv run --locked mypy src tests`：148 文件通过；`uv run --locked mypy migrations`：2 文件通过；全仓 Ruff lint/format：224 文件通过；工作区 `git diff --check` 通过。

### 第一轮：测试归类与内存数据库

- 按用户继续精简单元/集成划分的要求，本轮单元用例从 97 增至 126，集成用例从 391 减至 361；配置校验、发布规则、成员观测编排、CLI 参数编码、MCP 工具目录及错误响应映射使用单元测试，删除重复路由断言。
- 数据库集成测试全部使用 SQLite 内存模式；共享夹具提供隔离命名、独立 Engine/连接、真实迁移和统一清理，并检查没有落盘数据库。跨进程持久化断言改为跨 Engine 读取；不再声称覆盖磁盘耐久性或进程重启。
- `uv run --locked pytest tests/unit -q`：126 passed（1.77s）；`uv run --locked pytest -o addopts=-ra tests -q`：487 passed（61.39s）。
- `mypy src tests`：152 文件通过；`mypy migrations`：2 文件通过；全仓 Ruff lint/format：228 文件通过。工作区 `git diff --check` 通过；既有暂存区六份 task 文档仍有文件末尾空行告警，本轮未修改暂存区。

## Intent alignment / 意图对齐

- 对照[意图](../intent/20261111-backend-responsibility-alignment.md) R01—R08 和 A01—A10，已同时审视并调整领域、应用、持久化、Codex 协议、后台运行及装配边界，不仅移动 Service。
- 保留当前 HEAD 的业务和公开接入、SQLite schema、共享事务及原子条件；保留有效的只读 Query、内部批量 loader 和短事务适配，没有引入模块 UoW 或完整 CQRS 框架。
- 独立前端工作不属于本任务；本次验证没有操作真实数据库、正在运行的服务或真实 Codex 会话。

## Plan alignment / 计划对齐

- 对照[总计划修订 1](../plan/20261111-backend-responsibility-alignment.md)，七个节点按依赖串行交付并由主会话审查接受，正式入口、纯业务和完整后端回归均已覆盖。
- 设计补正 ALIGN-contracts-v1.1 删除 `select_messages` 中与 VisibilityScope 重复的 member 参数；身份仍由 scope 携带，业务范围、权限和事务边界不变，T05 和最终组合已复核。
- 实际后端工作区基于 HEAD `03b45fd`；过程文档及独立 `web/` 修改不属于后端实现范围。

## Task deliveries and integration / 子任务交付与集成

| ID | 当前有效交付 | 必要证据与组合结论 |
| --- | --- | --- |
| T01 | ALIGN-contracts-v1.1 | R01—R08 契约与调用链；v1.1 补正已纳入实际组合 |
| T02 | ALIGN-resources-v1 | 初始化、固定用户、话题规则；9 unit 与 77 定向 integration，最终组合回归通过 |
| T03 | ALIGN-members-v1 | 成员加入/编辑/退出、观测与 RPC 分段；5 unit、83 integration、mypy，最终 scope 演进已复核 |
| T04 | ALIGN-messages-v1 | 发布、幂等、队列管理与 HTTP 接线；定向回归中测试子进程导入问题已修正，最终 488 项通过 |
| T05 | ALIGN-context-v1 | 独立可见性、实际提供、SQL 分页和记账；80 integration、纯用例、共享 Session 回滚，最终组合通过 |
| T06 | ALIGN-delivery-v1 | 领域提交结果、应用动作、SQL 竞争保护、协议和 runner；102 integration 和新增纯业务检查通过 |
| T07 | ALIGN-integrated-v1 | 正式接线、[架构说明](../design/backend-architecture.md)、R01—R08/A01—A10 对照和完整开发检查已审查 |

## Actual diff summary / 实际差异摘要

- 按房间/话题、成员、消息、上下文和投递组织真实应用用例；领域表达初始化、约束、可见性、位置与投递结果。
- `RepositoryScope` 与 SQLAlchemy 适配统一 read/write 作用域，房间数据组合多个仓储，后台动作继续使用独立短事务；只读 Query 保留，无用继承 Protocol 与旧上下文整用例路径删除。
- SQL 仍负责分页前范围筛选、条件更新、领取与事件原子性；Codex driver 处理协议及身份，runner 管调度、互斥与退出。
- 调整 HTTP provider、测试夹具与测试，补充纯上下文/投递规则和后端架构说明；未修改迁移或数据库 schema。

## Expected vs actual changed files / 预期与实际修改文件对比

- 应用、领域、持久化、dispatch、HTTP、相关测试及架构说明均有计划内对应文件。Codex driver、bootstrap 及历史迁移经审视后不需修改；其责任和调用链由现有实现与回归覆盖。
- 相比预期，新增通用 `scopes.py` 与应用 `transactions.py` 以复用统一作用域，`TopicPosition` 移至应用视图；未增加功能或更改业务范围。
- 独立 `web/` 源码、测试以及视觉任务过程文档继续留在工作区，不属于本任务。

## Acceptance criteria checklist / 验收标准检查清单

| 标准 | 结果与证据 |
| --- | --- |
| A01 | 通过：T07 的 R01—R08 责任表和架构说明覆盖三层及入口、运行机制。 |
| A02 | 通过：领域默认值、约束、位置与投递结果可使用业务值测试；47 个纯业务测试通过，保留有用 Pydantic 值。 |
| A03 | 通过：资源、成员、消息、上下文和投递存在对应真实应用用例；应用/领域无 SQLAlchemy、FastAPI 或基础设施反向导入。 |
| A04 | 通过：原身份、旧状态、删除标记、单次启动、单调位置及原子领取等保护留在仓储 SQL；竞争和回滚集成测试通过。 |
| A05 | 通过：只读投影与提供用例分离，权限筛选发生在分页之前；lookahead、空结果、位置和事件的实际范围及回滚测试通过。 |
| A06 | 通过：driver 负责协议，Service 决定业务动作，runner 管调度；unknown 不重发、竞争与输入身份回归通过。 |
| A07 | 通过：统一作用域和请求事务保留；跨仓储共同回滚、RPC/WS 前释放、并发及 Engine 所有权测试通过。 |
| A08 | 通过测试范围：完整后端回归覆盖既有 HTTP/WS、CLI/MCP 和业务行为；26 个 rooms/member route 装饰器声明与基线一致，32 个相关类定义 AST 一致。CreateMember 删除了与父类重复的 `extra=forbid` 声明，配置仍由父类继承；未声称通过独立前端或真实环境验证。 |
| A09 | 通过：纯业务、完整后端、类型、Ruff 和差异空白检查实际执行；未将上一轮 474 项证据当成本轮结果。 |
| A10 | 通过：[后端架构说明](../design/backend-architecture.md)记录实际责任、调用链、事务/协议/运行所有者以及保留和删除理由。 |

## Test / command results / 测试 / 命令结果

- 项目为 Python 3.12+，使用 uv、pytest、mypy 和 Ruff；命令采用 `pyproject.toml`、README/Makefile 的后端入口。由于 `make check/test` 同时覆盖独立前端，本次单独执行等价后端部分并增加完整 integration。
- 进入验证前：`uv run --locked pytest tests/unit -q`，47 passed；`uv run --locked pytest -o addopts=-ra tests -q`，488 passed（82.95s）。
- Verification 阶段复跑：`uv run --locked pytest -o addopts=-ra tests -q`，488 passed（94.36s），测试仅使用临时库、fake 和测试协议进程。
- Verification 阶段：`uv run --locked mypy src tests`，141 文件通过；`uv run --locked mypy migrations`，2 文件通过；`uv run --locked ruff check .` 通过；`uv run --locked ruff format --check .`，216 文件通过；`git diff --check` 和 `git diff --cached --check` 通过。
- 静态核对 97 个产品 Python 文件的 domain/application 导入，未发现反向依赖；26 个受影响 route 装饰器声明与基线相同，32 个业务/视图类定义 AST 相同。
- 未运行前端测试、真实历史库/服务或真实 Codex 验证；不在本任务范围，也没有被本轮检查隐含覆盖。

## Missed or expanded scope / 遗漏或扩大的范围

未发现本任务范围内未实现项或业务功能扩张。签名补正和保留未改动的 driver/bootstrap 是记录在案的实现差异；前端工作为独立变更，未接管或评价。

## Risks / 风险

- 488 项回归基于临时库和模拟协议，不能代替真实历史数据库、服务部署和实际 Codex 环境验证。
- `RoomStore` 仍是组合资源/消息仓储与读取投影的便利作用域，而非新模块 UoW；查询直接服务接口，业务规则不能迁回 Store。
- 工作区同时存在独立前端及视觉文档修改，提交前必须按归属核对；本次没有执行 Git 暂存或提交。

## Incomplete items / 未完成事项

本次约定范围内无未完成实现或失败检查；报告待用户审阅。独立前端和真实环境不在本次验证范围。

## Conclusion / 结论

在上述范围和环境限制下，七项交付及 A01—A10 均有可追溯证据，整体验证通过；报告为 Draft，等待用户审阅。
