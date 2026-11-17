# 计划：Python 后端分层与抽象治理
最后修改时间: 2026-11-09 23:27:36

## 审查状态

Accepted

## 意图依据与授权

依据[意图 A01—A08](../intent/20261109-backend-architecture-governance.md)。用户开始计划与实现的指令授权本会话完成计划后连续实施及必要开发检查。实施起始基线为 `4c26eafaa3aa5ef40d8eaaa384c828d6294454b9`，当时仅本功能意图为未跟踪文件。总计划及以下 task 局部方案按该连续授权接受。用户现已另行授权整体 Verification 及必要修复，沿用既定方案；按用户最新限制，不操作数据库、不启停或访问运行服务，测试由用户执行。不包含 Git 提交或真实会话投递。

## 技术设计与决策

1. 技术层优先：`domain/rooms` 放实体、状态、路由与成员规则；`application/rooms` 放资源和发布用例、输入输出及存储/查询端口；`application/members` 放会话绑定、状态观测及上下文契约；`application/delivery` 放单次投递和能力契约。Pydantic 实体及 camelCase 编码继续复用，避免重复 DTO。
2. `infrastructure/persistence` 维护连接、迁移、SQL 查询和写入。保留现有 raw `read/write` 供适配器内部使用；新增 `read_rooms/write_rooms` 返回房间专用操作契约，应用不接触连接。该契约提供资源、发布查找、序号、原子保存和状态观测，不是泛化 UoW。查询适配直接实现 `RoomQueries` 契约。变化事件由写入代码显式追加，不使用 SQL trigger。
3. `RoomService` 接收中立 `RoomStore`；其读写作用域内执行幂等检查、路由、保存及写结果 metadata。应用只操作业务值。成员加入保持读取、外部 inspect、短事务重新检查并保存的顺序。
4. 上下文查询作为单存储的原子复合能力，SQLite 实现查询、提供记录和位置写入；应用契约明确可见范围，独立函数计算位置推进并校验订阅。无需增加只转发的 MemberContextService。
5. 会话快照及队列首项、输入证据属于中立类型；会话状态转换在 Codex 适配器完成。队列端口返回明确回执值，适配器剔除回显 input；明确拒绝错误与 RPC 实现异常分开，数据库只认识中立证据。
6. `infrastructure/dispatch` 负责线程、文件锁、并发、轮询和关闭，自己的 `dependencies.py` 构造 runner、锁及对应应用动作；`application/delivery` 负责 submit、activate、observe。新基线的成员观测由应用动作读取活动绑定并逐项 inspect，运行器只负责周期、取消和故障隔离；观察检查点策略保持原样。
7. `bootstrap` 管配置、日志、HTTP 和后台对象组合；持久化及 Codex 包提供普通工厂。HTTP 下按数据库资源、房间、成员能力设置 provider；`app.state` 桥接资源，不保存供业务访问的全能服务对象。WebSocket 依赖进程级查询能力，每轮短读，不复用 HTTP 请求事务。
8. HTTP 事务中间件接收事务工厂，保持惰性 BEGIN、响应前 commit、失败 rollback；持久化 provider 绑定该事务。数据库连接只在顺序作用域使用；后台任务独立创建短事务，外部 RPC 不持锁。
9. HTTP 路由、中间件、错误及静态文件移至 `interfaces/http`；CLI、MCP、HTTP 客户端归属 `interfaces`。保留 `agent_relay.server`、`agent_relay.cli`、`agent_relay.migrate` 的模块运行方式和 CLI script；更新内部导入、迁移脚本和 probes，不为旧内部模块建立兼容转发层。`logging.yaml` 路径、reload 配置和静态文件响应保持可用。
10. 单元测试以纯业务状态和轻量端口实现运行；数据库、HTTP、CLI/MCP 全链路、真实协议 fixture 子进程归入集成测试。提供独立 unit/integration 入口，`make test` 仍覆盖全部后端及前端测试。旧长期任务只作为历史背景，本功能 G01—G06 为当前治理清单。
11. 本次交付此前包含删除重建当前配置的本地开发库 `D:/SourceCodes/mywork/agent-relay/data/agent-relay.sqlite3`，执行结果留在 T02。用户已要求自行测试、不要再删库或停止服务；本轮不再执行该过程或访问运行服务。README 仅保留开发说明，不安排历史数据转换或兼容适配。
12. 事件游标和断线补取行为保持，移除事件写入触发器。应用/领域使用轻量 `RoomChange` 值表达变更；持久化适配在对应 SQL 写入后显式追加 `room_events`，确保仍在同一 SQLite 事务内。事件不是完整审计日志，不为领域实体机械增加生命周期或 observer 框架。

## 实施步骤与修改范围

1. T01 建立领域规则和消费方契约，迁移业务类型并接入无数据库测试。
2. T02 实现 SQLite 房间操作作用域、查询及原子上下文适配；移除事件 trigger，以代码显式记录房间变化。
3. T03 迁移 Codex 驱动，转换中立快照、回执和异常。
4. T04 接通应用用例、HTTP provider、配置、启动、CLI/MCP 和内部导入，纳入成员观测动作。
5. T05 拆出后台运行器与单次投递，接回 lifespan。
6. T06 完成测试归属、必要回归及 G01—G06 的实际证据。

主要修改 `src/agent_relay`、对应 `tests`、内部导入消费者、Makefile/pytest 配置及本功能记录。迁移不再创建事件 trigger，业务表与持久 payload 不变。本功能未修改前端产品实现，工作区另有独立前端变更。使用 apply_patch 修改文件，不提交。T02 此前按授权执行指定本地开发库的删除重建和对应后端恢复；该操作已结束，本轮遵守用户不再操作数据库和服务的限制。

## 子任务与协调

### 协调信息

- 方案修订：3；追加事件记录简化的目标和实现，不改变既有事件读取/API 契约。T02 完成后已重建指定本地数据库；本轮只审查已有结果，不再次执行。
- 权威协调根：`D:/SourceCodes/mywork/agent-relay`。
- 仲裁会话：当前主会话。
- 阶段授权：2026-11-09 用户要求开始计划与实现，随后要求整体 Verification；当前会话维护 task、总计划和验收记录，按验收授权修复既定范围偏差。测试由用户执行，不再操作数据库或运行服务。

### 任务定义表

| ID | 任务文档 | 直接前置任务与要求 | 预期交付与验收 | 意图验收归属 |
| --- | --- | --- | --- | --- |
| T01 | [业务规则与契约](../task/20261109-backend-architecture-governance/T01-contracts.md) | 无 | 中立契约、规则、单元测试，可被持久化及协议适配使用 | A01—A03 |
| T02 | [SQLite 边界](../task/20261109-backend-architecture-governance/T02-persistence.md) | T01 契约已审查，工作区版本可用 | 连接留在适配器，事务及有界查询保持；指定本地库完成删除重建并恢复后端 | A03、A04、A07 |
| T03 | [Codex 适配](../task/20261109-backend-architecture-governance/T03-codex.md) | T01 中立会话及队列契约已审查 | 业务层及存储不导入 Codex 实现 | A03、A06、A07 |
| T04 | [用例与装配](../task/20261109-backend-architecture-governance/T04-application.md) | T02、T03 的实现可用于当前工作区 | 入口依赖注入、独立用例和作用域可检查 | A03—A05、A07 |
| T05 | [后台运行](../task/20261109-backend-architecture-governance/T05-dispatch.md) | T04 的用例及装配已接通 | 生命周期及调度与应用动作分离 | A04—A07 |
| T06 | [测试与集成](../task/20261109-backend-architecture-governance/T06-integration.md) | T01—T05 交付及必要检查已接受 | 全部现有回归、静态检查、治理对应表 | A01、A07、A08 |

### 执行登记表

| ID | 执行状态 | 执行者 | 分配编号 | 工作基线 / 交付位置 | 仲裁结论 / 当前阻塞 |
| --- | --- | --- | --- | --- | --- |
| T01 | accepted | 当前主会话 | architecture-01 | 4c26eaf + 当前工作区；T01 交付记录 | 规则、契约及纯业务测试已核对 |
| T02 | accepted | 当前主会话 | architecture-02-events | 4c26eaf + 当前工作区；T02 修订 3 交付和验收记录 | 显式事件、同事务写入及无触发器 SQL 已审查；既有 204 项开发检查通过；最近一次重建已完成，重启后 HTTP 未验证 |
| T03 | accepted | 当前主会话 | architecture-03 | 同一工作区；T03 交付记录 | 中立契约、回执及协议 fixture 回归通过 |
| T04 | accepted | 当前主会话 | architecture-04 | 同一工作区；T04 交付记录 | 用例、HTTP/WS provider、CLI/MCP 及启动回归通过 |
| T05 | accepted | 当前主会话 | architecture-05 | 同一工作区；T05 交付记录 | 后台动作、锁、线程关闭及成员观测回归通过 |
| T06 | submitted | 当前主会话 | architecture-06-verification | HEAD 4c26eaf + 验收记录中的工作区快照；T06 验收修复交付 | 两处遗漏已修复，当前静态检查通过；组合工作区全量回归及运行验收待用户自测，不以旧 204/90 项结果放行 |

### DAG 与集成

T01 → T02、T03；T02、T03 → T04 → T05；T01—T05 → T06。当前会话串行执行，领域/契约、导入更新、fixture 和 bootstrap 为共享修改区，不启动并行写入。阶段内必要类型和导入接入可与契约同步，依赖接受以实际工作区 diff 和检查为准。

### 分配历史

| 时间 | ID | 分配编号 | 执行者 | 动作与依据 |
| --- | --- | --- | --- | --- |
| 2026-11-09 21:05:00 | T01 | architecture-01 | 当前主会话 | 按用户连续实施授权分配首节点 |
| 2026-11-09 21:32:23 | T01 | architecture-01 | 当前主会话 | 读取实际规则与测试交付，完成局部审查并接受 |
| 2026-11-09 21:32:23 | T02 | architecture-02 | 当前主会话 | 补记本会话连续实施与交付；核对 T01 契约及实际存储回归后接受 |
| 2026-11-09 21:32:23 | T03 | architecture-03 | 当前主会话 | 补记本会话连续实施与交付；核对 T01 契约及协议边界后接受 |
| 2026-11-09 21:32:23 | T04 | architecture-04 | 当前主会话 | 补记 T02/T03 集成后的用例和装配交付，按实际回归接受 |
| 2026-11-09 21:32:23 | T05 | architecture-05 | 当前主会话 | 补记 T04 接通后的后台拆分，按锁与生命周期证据接受 |
| 2026-11-09 21:32:23 | T06 | architecture-06 | 当前主会话 | 核对全部 task 与最终检查，接受开发交付 |
| 2026-11-09 21:47:31 | T02 | architecture-02-rebuild | 当前主会话 | 按用户追加授权重新分配本地删除重建；修订 2 已接受，保留原代码交付 |
| 2026-11-09 21:55:02 | T02 | architecture-02-rebuild | 当前主会话 | 核对实际迁移、空表、完整性、外键及 HTTP 200 [] 证据，接受重建交付 |
| 2026-11-09 22:20:45 | T02 | architecture-02-events | 当前主会话 | 按用户要求修订事件记录设计；采用轻量领域事件值和显式同事务持久化 |
| 2026-11-09 23:16:06 | T06 | architecture-06-verification | 当前主会话 | 整体验收发现探测脚本引用已删除迁移文件、README 仍称使用触发器；返工范围为该脚本、README 和本功能过程记录，使用静态检查复验 |
| 2026-11-09 23:19:01 | T02 | architecture-02-events | 当前主会话 | 补齐修订 3 的开发检查与最近一次重建历史，读取完整交付后按显式事件写入、事务所有者及当前静态检查接受；未运行重启后 HTTP 检查 |
| 2026-11-09 23:19:01 | T06 | architecture-06-verification | 当前主会话 | 静态修复交付转 submitted；当前 mypy 104+10 文件、Ruff 151 文件格式检查及 AST 审查通过，整体验收待用户提供当前版本自测结果 |

执行登记晚于本会话实际代码推进，本轮按实际工作区和检查统一补齐。全程只有当前主会话执行，没有因登记滞后重复分配或启动其他执行者。局部契约、适配和装配在同一工作区连续接入；初次通过 6 项规则测试后继续适配，43 项协议/投递/事务/成员回归及 45 项规则/存储/查询回归提供中间证据，最终以本计划下方检查为交付依据。

## 检查与验证安排

- T01 直接测试路由、固定用户、非法目标、成员约束、位置推进及发布用例；无需 SQLite 或应用启动。T02 保留存储事务、并发发布、查询分页及查阅记录集成测试；T03 保留 fixture 协议子进程测试，不调用真实 daemon。
- T04/T05 保留 HTTP 错误契约、请求提交、WebSocket 事件、CLI/MCP 身份及写入结果、成员观察检查点、后台停止和原会话输入关联的已有回归。
- Implementation 已使用项目既有 uv 锁定环境执行 pytest、mypy、Ruff 和前端检查。本轮 Verification 按用户自行测试的要求，只运行只读类型、lint、格式、源码依赖及 diff 检查，不重复执行测试、启动入口或真实探测，不安装依赖。
- 按问题清单检查 application/domain 无 SQLite、FastAPI、Codex 实现及部署配置导入；目录检查只是辅助，以真实调用链及测试为证据。
- 所有检查记录实际命令、范围、结果和未运行项。整体 Verification 已获授权，结果见[验收记录](../verification/20261109-backend-architecture-governance.md)，旧开发检查不作为当前组合工作区的全量运行结论。

## 风险与恢复

重构同时影响导入、fixture、事务和线程生命周期，按节点保留对应回归。移除数据库 trigger，不改变业务表与 payload；代码恢复仅反向修改本功能差异，不覆盖工作区其他变更。本地数据库重建及后端恢复已执行；用户现已禁止继续操作数据库和服务，本轮不再执行恢复或服务检查。已有成员状态轮询及节流策略作为回归约束，不借治理更改产品行为。新设计缺口先修订计划再继续受影响部分。

## 用户审查记录

2026-11-09：依据用户开始计划与实现的指令接受意图和本计划，完成各 task 的局部方案后连续实施，未授权独立整体 Verification。

2026-11-09：用户明确旧库删除重建即可，不做离线迁移适配。核对当前代码无旧库兼容适配，更新意图、计划、结构说明及迁移说明，不新增迁移实现任务。

2026-11-09：用户进一步明确删除重建属于本次任务，README 只保留简单开发指南；接受修订 2，执行 T02 的本地库重建及后端恢复。
2026-11-09：用户明确不希望使用复杂数据库编程；接受修订 3，T02 改为显式事件记录并移除事件触发器。

2026-11-09：用户要求自行测试、不要再删库或停止服务；随后明确开始整体 Verification。本轮完成源码验收、必要修复和静态复验，动态检查交由用户执行。

## 实施结果与问题清单

完成实现及必要开发检查。实际目录和调用链见[后端结构说明](../design/backend-architecture.md)。版本为基线 `4c26eaf` 加当前未提交工作区，其中包含收尾时观察到的独立迁移基线整理。后续观察到既有变更被暂存，本会话未操作暂存区，未创建提交或分支；本轮文档更新留在工作区。

| 问题 | 结果与实际证据 |
| --- | --- |
| G01 | RoomService 仅依赖 RoomStore/RoomData 及业务值；路由、路径与成员校验在 domain，发布/幂等及成员绑定使用轻量端口测试 |
| G02 | SQLiteRoomQueries 与 SQLiteMemberContext 归属 persistence；上下文维持一个原子复合能力，订阅与推进计算使用独立规则，有界 SQL 及事务回归保留。事件由显式持久化写入记录，与业务行处于同一事务，无数据库触发器 |
| G03 | SessionInfo、QueueReceipt、输入证据和拒绝错误归应用契约；Codex 适配转换底层状态并剔除 input；存储不再导入 Codex 驱动 |
| G04 | persistence/codex/dispatch 各有普通工厂，HTTP provider 按资源与业务组合；请求数据库直接取得资源，WS 通过查询依赖执行短读，应用不读取 app.state |
| G05 | DeliveryRunner、MemberPresenceRunner 拥有运行机制；DeliveryService 和 MemberSessions 拥有应用动作；共享 daemon、会话队列顺序、unknown 不重发和检查点行为保留 |
| G06 | 默认 pytest 指向纯业务单元测试，集成测试显式组织，make test 仍运行全部后端及前端。事件改造交付时为 26 unit、178 integration；当前另有默认话题相关测试，不沿用历史数量宣称当前全量通过 |

局部实施细化：runner 的普通工厂最终归属 `infrastructure/dispatch/dependencies.py`，避免组合根重建下层系统锁；应用组合视图与输入放在 `application/rooms/contracts.py`，实体留 domain。分层本身未改变业务表/payload；修订 3 删除事件触发器 DDL，未增加迁移版本，保留独立整理后的 `baseline_20261109`。

事件交付细化：`RoomChange` 仅描述 `room_id/kind/entity_id/message_id`；写库方法在行更新成功后显式记录对应事件，房间资源、成员状态、消息、投递、会话观察及阅读位置均覆盖。成员资料变化以一个 member 事件表达，避免订阅关联表改写产生重复通知。事件 ID 由 SQLite 自增，接口 DTO 与游标语义不变。`room_events` 无触发器依赖，失败回滚时事件同事务回滚。

T02 事件实现交付：领域 `RoomChange` 表达事件值，持久化方法在写入后显式追加事件，无数据库 trigger；无变化的阅读位置不产生事件。该交付当时的后端全量 204 项、mypy 104 文件、Ruff check 和 151 文件 format check 已通过。随后已再次按无触发器基线重建指定本地库并恢复后端；用户限制生效前尚未执行恢复后的 HTTP 检查，本轮不补做服务访问。

21:35—21:36 收尾检查观察到工作区另一组迁移变更：历史 SQL/revision 合并为 `baseline_20261109`，持久化实现共用新的 head 常量，新增 2 项迁移集成测试。该变更不属于原架构实施，原样保留并在组合工作区重新执行全部后端测试及静态检查。用户随后明确本次执行旧库删除重建；实际操作和结果由 T02 修订 2 单独记录，不增加旧库兼容或离线迁移实现。

T02 修订 3 删除完整基线 SQL 中的事件触发器，改由 `RoomChange` 领域值和 `SQLiteRoomStore`/`SQLiteMemberContext` 的显式写入记录事件。原本地开发库在再次清空重建前已没有业务数据，后续执行和验收记录在 T02。

首次全量检查发现一项既有 MCP 测试仍要求无话题的用户消息出现在 backend 话题。该断言与已接受的 `20261109-message-filtering` A01 冲突，已改为验证不混入无关话题，保留普通消息读取断言；未改变产品筛选行为。协议 fixture 增加真实 queue/add 的 input 回显，用来验证适配器确实不保存 prompt。

## 开发检查结果

下表为 Implementation 阶段历史证据。事件改造后的最后一次后端检查已更新为 204/104/151；此后工作区出现默认话题与前端独立改动，当前静态检查和未运行项在验收记录单列。

| 实际命令与范围 | 结果 |
| --- | --- |
| 根目录 `uv run --locked --no-sync pytest tests -q` | 首次 202 项通过；独立迁移整理后 204 项通过；显式事件改造后的最后一次为 204 项通过，65.17 秒，当时包含 26 unit、178 integration |
| 根目录 `uv run --locked --no-sync pytest -q` | 默认 26 项纯业务测试通过，0.22 秒；不加载集成 conftest |
| 后续工厂归属调整及锁断言后 `uv run --locked --no-sync pytest tests/integration/test_delivery_service.py -q` | 4 项通过，覆盖原会话、重启、输入分页以及新增的运行中锁排他和关闭后释放 |
| 根目录 `uv run --locked --no-sync mypy src tests` | 显式事件改造后 104 个源文件通过 |
| 根目录 `uv run --locked --no-sync mypy scripts/probes migrations` | 最新 10 个源文件通过，包含合并后的基线 revision；合并前为 18 个 |
| 根目录 `uv run --locked --no-sync ruff check .`、`ruff format --check .` | 显式事件改造后全部通过，151 个文件格式合规；未更新工具依赖 |
| web 下 `corepack pnpm test` | 21 个文件、90 项通过 |
| web 下 `corepack pnpm typecheck`、`lint`、`format` | 当时全部通过；本功能未改前端产品代码，不能用该结果证明后续独立前端变更 |
| `python -m agent_relay.cli/server/migrate --help`，均经 uv 锁定环境 | 三个公开模块入口通过，不启动服务或执行迁移 |
| AST 导入审查 | domain/application 的外层及具体技术依赖违规为 0；domain 也无 application 导入 |
| `git diff --check` | 通过；收尾再次检查 |
| `dev` 配置下 `uv run --locked --no-sync python -m agent_relay.migrate` | 实际删除指定开发库后，成功初始化为 `baseline_20261109` |
| 修订 2 重建后只读 SQL、SQLiteRoomStore 初始化及 `GET http://127.0.0.1:9080/api/room` | 21:55 的首次重建检查：6 项业务表均为 0 行，完整性为 ok，外键检查为空，HTTP 200 []；该 HTTP 结果不属于后续无触发器重建 |
| 修订 3 无触发器基线再次重建后的本地检查 | SQLiteRoomStore 初始化通过，triggers=[]，6 项业务表均为空，完整性 ok，外键检查为空；后端已恢复，恢复后的 HTTP 未验证 |

本机 PowerShell PATH 未发现 make，故执行 Makefile 对应的锁定工具命令，未安装或替换工具。开发阶段未运行真实 Codex daemon 探测、浏览器交互或容器。本地开发库删除重建及后端恢复已完成；README 不承载本次操作过程。用户随后禁止继续操作数据库和服务，本轮未运行测试、真实探测或服务访问。

## 整体 Verification 进展

2026-11-09 23:27:36：静态验收和必要修复已完成，详见[验收记录](../verification/20261109-backend-architecture-governance.md)。发现并修复探测脚本的失效迁移路径和 README 过期事件说明；更新 T02 交付及历史检查口径。收尾观察到独立新增的删除聊天室接口、应用/存储操作和测试，原样保留，补查其分层及事务接点。最新 mypy 104+10 文件、Ruff check、152 文件格式检查、AST 依赖与探测路径审查通过；暂存及未暂存 diff 空白检查通过。证据只覆盖验收记录中的截止快照，后续并行改动不自动继承。

T01—T05 的架构交付已核对；T06 验收修复为 submitted。当前组合工作区的完整测试及实际运行效果由用户自测，尚无该版本动态证据，整体 Verification 保持 Draft，不宣称全部 A01—A08 已通过。
