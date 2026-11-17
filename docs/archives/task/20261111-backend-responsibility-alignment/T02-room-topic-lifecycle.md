# Task / 子任务 T02：房间与话题生命周期
最后修改时间: 2026-11-11 16:34:20

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[后端三层职责审视与业务组织调整](../../intent/20261111-backend-responsibility-alignment.md)。
- 权威总计划：[方案修订 1](../../plan/20261111-backend-responsibility-alignment.md)，任务 ID：T02。
- 权威协调根与代码工作区：`D:/SourceCodes/mywork/agent-relay`。依赖和分配以总计划为准；方案状态不表示实现状态。

## Handoff basis / 交接依据

- 用户已授权自主实施；执行者为主会话，分配编号 ALIGN-T02-20261111-01。接收、基线及前置见本文记录，最终组合见 T07。
- 协议入口为总计划 Coordination 所列 SpecFlow skill 及协作契约；输入采用主会话已接受的当前有效版本。
- 执行者可写本 task 的接收、进展、交付章节及最后修改时间；方案、总登记和共享写入安排由主会话维护。
- 回报在执行会话输出可复制摘要，由用户转交主会话；不自动向聊天室发送。

## Goal and acceptance / 目标与验收

主要结果：房间与话题生命周期拥有清晰的领域规则、应用用例和原子存储分工，覆盖 A02—A04、A07—A09 及 R01、R03—R06、R08 的资源部分。

- 固定用户、初始话题及其业务默认值由明确业务构造决定，仓储保存传入事实，不在 `insert_room` 内隐式制定业务初始化内容。
- RoomService 的资源部分组织创建/改名/删除房间、创建/编辑/删除话题；领域表达路径、名称冲突及删除话题时移除有效订阅等规则，DB 继续保存最终约束。
- 初始化、资源变化和事件同事务；已有默认话题、固定用户、关联顺序、软删除及十四表删除清理行为保持。
- 房间/话题公开入口、返回 metadata 及资源读取投影可用，成员和消息的未迁移方法不被越界删除。

## Inputs and eligibility / 输入与可开始条件

依赖边及版本条件只查总计划。需要已接受的资源类型、初始化/事件/作用域契约及可访问设计版本；方案、阶段授权、有效编号与共享文件安排满足后，先记录接收再实施。发现签名无法实现原行为时回报，不自行重设其他节点契约。

## Scope and files / 范围与文件

- `domain/rooms/{models,state,rules}.py` 的房间/话题内容，必要的专用资源规则文件按 T01 决定；`application/rooms/{service,contracts,ports}.py` 的资源部分。
- `infrastructure/persistence/repositories/rooms.py` 的初始化、保存、删除，相关 `resource_queries.py`、mapper 和 scope 接线；只处理本节点必要改动，不重写 Database/SQLite 方言。
- 房间/话题 HTTP route/provider 和对应消费者，`tests/fakes/rooms.py`、`tests/room_fixtures.py` 及资源测试的必要配套调整。
- 不迁移成员编辑/删除、消息发布或上下文；后续节点会消费本节点资源能力。共享模型、事件与端口只按已接受契约变更。

## Technical decisions / 局部技术设计

- 应用生成所需 ID/时间并组织领域初始化结果；领域构造只依赖业务输入，不自行连接存储或调用外部会话。
- 房间、固定用户和默认话题在统一写作用域内保存。可以保留复合原子保存方法，方法输入必须清楚表达完整初始化事实，不能仅把隐含创建藏入新的仓储名称。
- 名称冲突等规则使用当前有效资源判断，数据库约束继续保护竞争；保留大小写和路径规范化的当前语义，不新增校验规则。
- 删除话题保持软删除及订阅调整；物理删除房间保持清理顺序和外键完整性，存储清理顺序属于基础设施责任。
- Query 继续批量生成 metadata 等投影；不为路径相同的读取建立转发 Service。事件形态遵循 T01 的真实使用或删除决定。

## Implementation outline / 实施安排

1. 将当前初始化与资源约束整理为可独立调用的业务规则及输入输出。
2. 调整资源用例和仓储输入，接通同事务初始化/变更/事件与删除清理。
3. 同步本节点入口、读取投影、fake 与夹具，移除被替代的资源路径。
4. 完成规则、用例和 SQL 原子性检查，交付供成员节点消费的有效版本。

## Checks and delivery / 检查与交付

- 在现有 `tests/unit/test_room_rules.py` 及适当的资源用例测试中验证初始化、冲突和删除规则，使用中立 fake，不建立 SQLite 或 FastAPI。
- 定向入口：`uv run --locked pytest -o addopts=-ra tests/integration/test_room_repository.py tests/integration/test_room_store.py tests/integration/test_room_api.py tests/integration/test_user_members.py tests/integration/test_persistence_runtime.py -q`。
- 重点复用/调整现有断言：固定用户与默认话题、项目唯一性、改名、软删除和订阅、完整房间删除、失败时资源及事件共同回滚；不添加仅验证方法搬移的测试。
- 受影响模块完成必要 mypy/Ruff/空白检查；记录真实命令、结果、未运行原因及输入/输出快照，不以历史通过代替本节点证据。

## Risks / 风险

- 初始化输入改变会影响生产与测试专用建房路径，需区分业务默认与测试构造，不将演示数据写入产品。
- 资源契约同时被成员和消息消费；超出已冻结签名的变化由主会话协调，不能只修本节点测试而破坏其余调用方。

## Reception and progress / 接收与进展

2026-11-11 15:46:05 主会话接收 ALIGN-T02-20261111-01/rev1，依据用户自主实施授权；HEAD 03b45fd，已接受 T01 ALIGN-contracts-v1。范围为房间/话题规则、初始化事实、仓储及消费者测试；成员/消息主流程暂留给后续节点，保留独立 web 修改。

## Delivery and review / 交付与审查

2026-11-11，ALIGN-T02-20261111-01/rev1 交付 ALIGN-resources-v1：新增 domain resources 工厂/话题规则；insert_room 接收显式 user；应用使用初始资源事实；删除无调用者 RoomChange。对应测试夹具同步，新增 3 个独立资源测试。输入 contracts-v1；实际产品/测试修改见 HEAD 03b45fd 工作区差异。`pytest tests/unit/test_resource_lifecycle.py tests/unit/test_room_rules.py -q` 9 passed；本 task 列明的五个 integration 文件 77 passed（13.00s）。静态检查于最终组合补齐，不伪记已运行。主会话审查事实输入、事件和资源行为后接受，无阻塞、未完成业务或范围偏差。
