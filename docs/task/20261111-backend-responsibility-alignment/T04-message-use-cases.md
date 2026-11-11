# Task / 子任务 T04：消息发布与队列管理
最后修改时间: 2026-11-11 16:21:00

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[后端三层职责审视与业务组织调整](../../intent/20261111-backend-responsibility-alignment.md)。
- 权威总计划：[方案修订 1](../../plan/20261111-backend-responsibility-alignment.md)，任务 ID：T04。
- 权威协调根与代码工作区：`D:/SourceCodes/mywork/agent-relay`。直接依赖、执行者和有效编号以总计划为准。

## Handoff basis / 交接依据

- 用户已授权自主实施；执行者为主会话，分配编号 ALIGN-T04-20261111-01。接收、基线及前置见本文记录，最终组合见 T07。
- 协议入口为总计划 Coordination 的 SpecFlow skill 与协作契约，输入以主会话已接受的当前版本为准。
- 执行者仅写本 task 接收、进展、交付与最后修改时间；总方案、公共契约变更及写入安排由主会话协调。
- 回报为当前执行会话中的可复制摘要，由用户转交主会话，不自动向聊天室发送。

## Goal and acceptance / 目标与验收

主要结果：消息发布、发布查询及队列清理形成独立的消息应用能力，与领域路由、只读投影及原子存储明确分工。覆盖 A02—A09 及 R01、R03、R05、R06、R08 的消息部分。

- 从 RoomService 移出 post/publication/clear_queue/clear_queue_with_codex 的实际职责，正式路由与消费者调用消息能力，不留下转发旧方法或双路径。
- 发布身份、publication_id 幂等及冲突、引用校验和操作顺序在应用清晰可见；接收人、发送者排除及目标有效性归属于领域规则。
- 活动投递状态有明确业务来源，消息队列查询/清理与后续投递使用同一语义，基础设施不自行制定重复状态集合。
- 序号读取与插入处于同一受保护写作用域，消息/关联/投递/事件原子保存；有效队列与历史投递、所有页清理及 removedMessages 计数保持。
- 清理 Codex 队列保持本地删除先提交、RPC 后执行及原结果汇总语义。只读消息投影不被强制包装成新的转发服务，原可见范围和分页保持。

## Inputs and eligibility / 输入与可开始条件

前置边及版本条件见总计划。需要已接受的消息/状态/查询设计、成员身份与资源访问实现，以及其传递前置的当前版本。有效阶段授权、分配和共享文件协调齐备后先写接收记录。

## Scope and files / 范围与文件

- 新增 `application/messages/{service,contracts,ports}.py`，按 T01 固定名称和最小职责；迁移 rooms service/contracts/ports 中的消息部分及所有对应消费者。
- `domain/rooms/rules.py` 的消息规则及必要状态定义；`repositories/messages.py`、`message_queries.py`、`room_queries.py` 和相关 mapper、资源身份读取与 scope 接线。
- 消息/发布/队列 HTTP route/provider、`tests/fakes/rooms.py`、`tests/sqlalchemy_message_fixtures.py`、相关 room fixture 及消息/队列测试。
- Codex 队列清理消费既有 QueueDriver，不改入队/启动/输入历史协议实现；不实现上下文提供，不迁移 runner。

## Technical decisions / 局部技术设计

- 保留业务导向的 `publication`、`next_message_seq`、`insert_message`、`clear_queue` 等存储能力，输入输出为业务值，不透出 SQL 语句或 ORM。
- 领域定义路由和有效状态语义，应用获得发布者与事实后判断幂等/引用并构建消息；仓储负责关联顺序、约束和显式事件。
- 请求内消息用例借用统一事务；带远程删除的清理用例使用独立短作用域，退出并提交后才调用 driver。provider 必须选择正确资源作用域，不能因统一消息类让 RPC 借用未提交请求会话。
- 普通 Query/Reader 直接生成页、队列、统计和事件投影；内部 MessageQueries/ResourceQueries 的加载复用留在持久化，不作为新的应用层业务服务暴露。
- 发布幂等按原内容/话题/@/引用一致性判断，保留字面关键词、双向涉及的序号与排序事实，为 T05/T06 交付稳定的消息值、读取和投递标识。

## Implementation outline / 实施安排

1. 迁移消息请求/输出和所需端口，建立明确的消息用例，复用领域路由。
2. 明确状态语义来源，调整消息仓储与读取复用，保持序号及关联/事件原子性。
3. 接通 HTTP 发布/查询/清理路径和短作用域 provider，移除 RoomService 的对应职责并迁移消费者。
4. 验证幂等、并发、清理/RPC 边界及投影，冻结下游消费版本。

## Checks and delivery / 检查与交付

- 使用 `tests/unit/test_room_routing.py`、`test_room_rules.py` 和必要消息用例测试验证接收人、幂等冲突、引用、身份、失败与远程删除前本地提交；按责任迁移测试命名，不丢失断言。
- 定向入口：`uv run --locked pytest -o addopts=-ra tests/integration/test_message_repository.py tests/integration/test_room_queries.py tests/integration/test_member_publish.py tests/integration/test_room_store.py tests/integration/test_room_api.py tests/integration/test_persistence_runtime.py -q`。
- 对清空/领取/回执边界运行相关 delivery repository 回归；重点保护全页清理、软删除、迟到回执、原始历史回执及 1/多条页面批量读取，不为提高分层纯度引入逐行查询。
- 完成受影响模块类型/格式检查，记录实际输入和输出版本、文件清单、检查结果与未运行原因；不得把主流程残留在旧 service 后交给 T07 清理。

## Risks / 风险

- 消息契约被上下文、投递、HTTP、CLI/MCP 测试消费；共享输入输出或字段调整需完整检索调用者，并保持公开编码。
- 目标是职责归属，不改变清空选择范围或远程清理的失败承诺；新增业务缺陷修复须单独说明。

## Reception and progress / 接收与进展

2026-11-11 主会话接收 ALIGN-T04-20261111-01/rev1，依据用户自主实施授权；基线 HEAD 03b45fd 工作区含已接受 contracts-v1/members-v1 及传递资源版本，相关检查通过。修改消息能力、所需领域规则/查询和正式入口，保留成员与独立 web 修改。

## Delivery and review / 交付与审查

2026-11-11 ALIGN-T04-20261111-01/rev1 交付 ALIGN-messages-v1：MessageService、消息 DTO/Repository 迁至 messages；RoomService 仅房间/话题；正式发布/清队列 provider 区分请求与短事务；领域验证 self/replay，活动状态由领域定义，SQL 原子性保留。11 unit 通过；七文件定向检查初次 181 passed/1 failed，失败为测试子进程导入 fixture 非产品能力，改为正式 SQLAlchemyRoomQueries 后 room_store 全部 8 passed；mypy132 通过。原输入 contracts-v1/members-v1 有效。无剩余业务阻塞；格式及最终组合检查留 T07。主会话审查并接受，未运行真实服务/库。
