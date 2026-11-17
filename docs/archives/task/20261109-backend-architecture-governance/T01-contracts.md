# 子任务 T01：业务规则与中立契约
最后修改时间: 2026-11-09 21:32:23

## 审查状态

Accepted

## 父任务与权威记录

总意图与权威[总计划](../../plan/20261109-backend-architecture-governance.md)，任务 T01，方案修订 1。

## 目标、范围与局部设计

交付 A01—A03。实体、RoomState、路由、成员约束及路径规则放 domain；输入输出和消费方端口放 application。房间存储的 read_rooms/write_rooms 返回 RoomData，提供业务事实和原子写入；RoomQueries 是查询端口。会话快照使用中立状态，队列返回回执值与输入证据；明确拒绝错误由应用契约拥有。上下文契约表达单存储的原子查阅能力，位置规则为纯函数。复用 Pydantic 编码，不复制每层模型。

## 输入与实施安排

无前置。核对基线规则，迁移实体与契约，提取 build_message/resolve_recipients/validate_member/normalize_project_path，建立轻量房间存储用于业务测试。后续节点不得依赖旧私有规则。

## 检查与风险

单元测试验证并集去重、排除发送者、用户无投递、非法目标整体拒绝、幂等冲突与位置单调推进；不创建数据库或真实子进程。跨节点导入接入按总计划串行集成。

## 交接依据与接收

当前主会话，编号 architecture-01；授权与基线见总计划。2026-11-09 接收，先按本方案实施。可写本记录与总计划；无需交接执行会话。

## 交付与审查

2026-11-09 21:32:23，当前主会话，architecture-01，方案修订 1，已交付并由主会话按实际 diff 接受。

- 变更：`domain/rooms/{models,state,rules,positions,errors}` 与 application 的 rooms/contracts、rooms/ports、members/sessions、members/context、delivery/ports；规则不再是服务私有方法。
- 验收：A01—A03 对应结构、消费方契约、纯值规则和应用测试具备；中立 SessionStatus 在适配层与底层状态转换。
- 版本与前置：4c26eaf + 当前工作区，无前置；实际差异以新目录和总计划为准。
- 检查：首批规则 6 项通过，最终默认纯业务测试 26 项通过；mypy 及导入审查通过。
- 范围偏差、未完成项与风险：无目标偏差；全链路集成由 T06 汇总。未运行真实会话探测。
