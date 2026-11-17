# Task / 子任务 T06：投递动作、协议与后台运行边界
最后修改时间: 2026-11-11 16:21:00

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[后端三层职责审视与业务组织调整](../../intent/20261111-backend-responsibility-alignment.md)。
- 权威总计划：[方案修订 1](../../plan/20261111-backend-responsibility-alignment.md)，任务 ID：T06。
- 权威协调根与代码工作区：`D:/SourceCodes/mywork/agent-relay`。直接依赖、有效编号、共享写入安排以总计划为准。

## Handoff basis / 交接依据

- 用户已授权自主实施；执行者为主会话，分配编号 ALIGN-T06-20261111-01。接收、基线及前置见本文记录，最终组合见 T07。
- 协议入口为总计划 Coordination 所列 SpecFlow skill 和协作契约；需读取总登记及已接受输入。
- 执行者只写本文接收、进展、交付与最后修改时间；不改总登记、方案状态或其他节点记录。
- 在执行会话回报可复制摘要，由用户转交主会话，不自动向聊天室发送；不得对真实 Codex 会话执行验证动作。

## Goal and acceptance / 目标与验收

主要结果：一条责任明确且保持现有事实语义的投递链路，领域状态、应用动作、SQL 保护、协议适配与后台执行机制可分别核对。覆盖 A02—A04、A06—A09 及 R03—R08 的投递部分。

- 投递状态和失败语义有明确业务来源，应用组织一次提交、启动、接收核验及恢复动作，runner 不直接决定中断后的业务状态或业务文案。
- adapter 负责 RPC、原始结构和身份校验、技能输入绑定及中立结果/异常转换；不是因为内容包含业务词汇就把协议适配全部上移。
- 仓储保留跨房间相同会话互斥、领取、原身份条件保存、只尝试一次启动、清空标记保护与接收确认等原子操作；不会被无保护的读后写替代。
- 未知结果不重新 enqueue，启动拒绝/失败不重复启动或覆盖已保存回执；仅实际匹配输入可记 received，清空后的迟到结果不复活队列。
- 历史游标、轮询与并发状态的所有者有说明；锁/线程池/停止仍属运行机制，关闭顺序、独立 Session、RPC 前释放与借入资源所有权保持。

## Inputs and eligibility / 输入与可开始条件

直接前置及版本要求见总计划。消费已接受的状态/协议/运行设计，以及消息、队列、清空和投递身份实现；其中包含成员节点交付的会话 adapter 基线。T05 不是产物依赖，但共享文件未协调时按计划串行。有效授权/分配核对后先记接收。

## Scope and files / 范围与文件

- `application/delivery/{service,ports}.py`、`domain/rooms/models.py` 的投递语义及必要专用规则；收敛重复 Store/Repository Protocol，保持明确短动作边界。
- `repositories/deliveries.py`、`delivery_store.py`、相关 mapper/回执事实转换及共享状态引用。
- `infrastructure/codex/driver.py` 的 enqueue/delete/activation/input-history 及必要共用协议部分；会话部分以已接受前置为基线，不回退 T03。
- `infrastructure/dispatch/{delivery,dependencies,lock}.py` 的必要调整、bootstrap/provider 投递接线，以及 delivery fake、协议 fixture 和相关测试。
- 不变更成员生命周期、上下文提供、调度频率、并发配置、文件锁身份或公开协议，不引入队列平台或真实投递探测。

## Technical decisions / 局部技术设计

- 按 T01 的责任表核对当前转换：pending → submitting；submitting → queued/rejected/unknown；中断 submitting → unknown；有匹配输入的 queued/unknown → received。删除标记保留为独立事实，启动尝试只允许标记一次。
- 领域定义允许状态和结果规则；应用根据中立 RPC 结果决定后续动作；SQL WHERE 继续核对旧状态、room/原身份、deleted_at 和启动标记，条件未满足不得覆盖现有事实。
- 恢复、领取/提交与核验以明确应用动作供 runner 调用；runner 决定何时和如何并发执行，处理取消/停止与单次失败隔离，不产生业务状态机的第二份实现。
- 外部消息文本组织与协议 input/skill 结构区分：业务表示在应用有明确归属，RPC 输入结构和技能路径选择在 adapter。回执只保存既有必要事实，不泄漏原始 input 或扩大 payload。
- `history_cursors` 等可变状态按生命周期和并发访问事实决定保留或迁移；如果保留须解释同 session 动作隔离，不为此增加外部存储或更改历史遍历策略。
- 每次数据库动作使用独立短作用域，RPC 在退出后执行；并发任务不共享 Session，runner 停止并释放锁后才 dispose 自建 Engine。

## Implementation outline / 实施安排

1. 落实投递状态/结果规则和端口职责，明确恢复、提交、启动、核验的应用入口。
2. 调整原子仓储和短动作适配，保留全部身份、状态、删除与竞争条件。
3. 核对 Codex 转换和文本/协议边界，接通 runner 与工厂，说明运行状态所有者。
4. 删除重复/旧路径，验证竞争、失败、未知结果和生命周期，交付最终投递链路。

## Checks and delivery / 检查与交付

- 纯业务检查使用 `tests/unit/test_delivery_actions.py`、`tests/fakes/delivery.py` 及必要状态/恢复规则测试，覆盖拒绝、未知、保存后启动失败、原回执保留及不重发。
- 定向入口：`uv run --locked pytest -o addopts=-ra tests/integration/test_delivery_repository.py tests/integration/test_delivery_service.py tests/integration/test_codex_driver.py tests/integration/test_runtime.py tests/integration/test_persistence_runtime.py -q`。
- 保留八路竞争、跨房间会话互斥、领取/清空与回执/清空、事件/提交失败、原身份核验及 RPC 前归还连接的既有集成断言；只使用临时数据库和模拟协议进程。
- 检查所有 runner/driver 消费者和必要类型/格式，记录实际版本、文件清单、命令结果与未运行项，说明状态、文本、回执及游标的最终归属。

## Risks / 风险

- enqueue 成功后发生的启动或记录错误不能被当作可安全重复提交；本节点不能为统一异常处理删除阶段事实。
- 状态机提取和 SQL 条件会表达不同层面的保护，两者必须对应；不因重复表象删除 SQL 最终防线。
- driver、模型、工厂与夹具可能含其他节点修改，变更共享签名或超出范围时先由主会话评估。

## Reception and progress / 接收与进展

2026-11-11 主会话接收 ALIGN-T06-20261111-01/rev1；用户已授权自主实施。HEAD 03b45fd，输入为已接受 contracts-v1/messages-v1 及其成员/资源前置。上下文分支已完成实现与 80 项定向集成、mypy140 检查；当前串行修改投递路径，保留独立 web 变更，不操作真实服务或会话。

## Delivery and review / 交付与审查

2026-11-11 16:18:10，主会话提交并审查接受 ALIGN-delivery-v1（ALIGN-T06-20261111-01/rev1）。领域 delivery 定义有效/待确认状态、提交成功与拒绝/不确定/处理中断失败结果，应用调用结果规则并提供 recover；runner 调用应用恢复，保留原子领取、调度与同会话观测互斥。移除空 DeliveryStore Protocol，保留具体短事务适配；仓储原状态、原身份、删除和单次启动条件完整保留。

投递仓储/服务、Codex driver、runtime/persistence_runtime 为 102 passed（28.19s），已有纯投递动作与上下文/位置合计 12 passed；新增结果不可修改原领取值、迟到失败不能覆盖已入队值、恢复不重发的纯业务覆盖，随 T07 最终检查。Codex driver 经核对保留：技能绑定、原始 input/receipt 身份和状态转换属于协议适配。历史游标仍由进程级 DeliveryService 持有，runner 保证同 session 不并发 observe。无范围偏差、真实环境操作或阻塞；最终清单和完整检查由 T07 关联。
