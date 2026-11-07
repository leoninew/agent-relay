# Task / 子任务 T03：原子消息发布、路由与幂等
最后修改时间: 2026-11-07 19:41:39

## Review status / 审查状态

Draft。D03 自身排除已接受；D11 和调用方/发布键契约仍须在接受计划前收敛。

## Parent and authority / 父任务与权威记录

- [总意图](../../intent/20261107-backend-from-web.md)、[权威总计划](../../plan/20261107-backend-from-web.md)。任务 ID：T03；方案修订：10。
- 协调根：`D:/SourceCodes/mywork/agent-relay`；总计划为依赖唯一来源。

## Goal and acceptance / 目标与验收

G04、G05、G12/G13 的持久事实基础，对应 A01—A03、A12：一次显式发布原子创建唯一消息、目标快照、投递和事件，重放找回同一结果而不重新路由。

## Scope and files / 范围与文件

`room_routing.py`、`room_service.py`、消息/投递/发布键/房间事件迁移与 repository、`room_models.py`、`routers/room.py`、现有错误映射及相关测试。不发起真实外部调用。

## Inputs / 输入

见总计划 T03：T02 的可组合短事务、房间资源与成员快照；T01 的 D03、D11、调用方身份与接口决定。

## Technical decisions / 局部技术设计

- Message 保留话题、显式 @、实际接收人和可选同房间引用；Delivery 固定 targetMemberId 和发送时 targetSessionId，初始 pending。按已接受 D11 保存当时命中的路由来源。
- 实际目标须已有 T02 的可核验会话绑定；创建中或创建未知的成员不能成为有效目标。已绑定但运行时暂不可用不改变路由，投递保留绑定版本快照，后续恢复不得改投新 thread。
- 同一写事务内完成目标校验、订阅展开、去重、实际非空校验、Seq 分配、Message/关联/Delivery/事件/幂等记录；任何无效目标整条回滚。新序号来自持久计数，不从列表长度推导。
- D03 已接受：全部目标有效后，合并话题订阅与 @、去重、排除可信发布成员，再检查实际非空；显式 @ 自己仍排除。空目标整条拒绝，保留原始显式选择用于成功消息的目标快照。控制台无绑定成员不排除任何人，不按显示名推断身份。
- 唯一约束覆盖 `(room_id, seq)`、`(message_id, target_member_id)` 和 `(room_id, caller_id, publication_id)`。成员 sender 取可信调用上下文，控制台/CLI 取已定入口身份。
- 发布请求指纹以服务接受后的正文、去重排序目标与引用计算；目标顺序不产生新意图。先检查已有发布键再看当前订阅，重放返回原发布结果；相同键不同请求 409。
- POST 成功仅表示 Relay 持久接收。新增按调用方及 publicationId 找回结果的接口；X-Request-Id 继续只用于链路排障。
- 事件采用独立持久 ID，记录消息发布/资源和投递变化；事务提交后才可通知。T08 实现传输，不在本节点建立内存权威事件源。

## Implementation outline / 实施安排

1. 固定消息、目标、投递、发布键与事件 schema 及 DTO；与 T02 迁移顺序一致。
2. 提取统一发布用例和路由函数，供 Web/CLI/成员入口复用；保留正文 #/@ 不路由规则。
3. 实现事务、幂等冲突/找回接口和持久目标快照；订阅更新和发送以数据库事务顺序确定生效关系。
4. 暴露 T04 领取 pending 所需的最小接口及 T08 读取事件接口；不按 presence 生成 delivered。

## Checks and risks / 检查与风险

- 三种目标组合、跨话题去重、无目标/无实际收件人/跨房间目标整体拒绝；订阅变化后旧快照不变。
- 话题命中自己、显式 @ 自己、两者叠加均无自身 Delivery；排除后只剩空集合不保存 Message/Delivery，出现任何无效目标仍整条拒绝。控制台发布保持原路由，无成员身份覆盖入口。
- 临时 SQLite 下并发相同键只一条消息；不同指纹 409；故障注入在消息/投递/事件中间无半条结果，重启可找回发布。
- 运行相关 pytest、mypy、ruff。原 delivered 演示断言改为 pending，不以旧数据证明真实入队。

## Handoff basis / 交接依据

未分配。沿用总计划的 SpecFlow 协议、协调根及分配审查；实施授权不由本文路径产生。主会话派发时填写实际基线与 T01/T02 已接受版本；本文记录接收与交付，共享 API/模型文件串行整合。

## Reception and progress / 接收与进展

无接收、无实现。后续先记录有效编号、方案修订、授权和前置版本。

## Delivery and review / 交付与审查

无交付。需提交 schema/API、幂等与故障证据、实际 diff/前置版本、检查和未完成项，输出摘要后由主会话接受。
