# 子任务 T05：后台运行与投递动作
最后修改时间: 2026-11-09 21:32:23

## 审查状态

Accepted

## 父任务与权威记录

权威[总计划](../../plan/20261109-backend-architecture-governance.md)，任务 T05，方案修订 1。

## 目标、范围与局部设计

交付 A04—A07。DeliveryService 仅接收 DeliveryStore、QueueDriver 和日志，提供 submit/activate_after_submission/observe；应用保留有限分页核验游标。DeliveryRunner 拥有 lock、线程池、轮询节奏、future 隔离与关闭，调用应用动作。SubmitterLock 留 infrastructure。MemberPresenceRunner 只调度可取消的成员观测应用动作。

## 输入与实施安排

使用 T04 装配；迁移并拆分现有循环与动作，明确 runner 注入锁和存储，接入 lifespan。保留单库单提交器、会话顺序、并发额度、一次首项启动、unknown 不重发和状态观测检查点。

## 检查与风险

运行投递与成员状态生命周期集成回归，单次应用动作使用轻量存储/驱动测试。检查外部调用期间无事务，关闭等待有界 RPC，文件锁最终释放。

## 交接依据与接收

当前主会话，architecture-05；依用户连续实施授权使用同一工作区 T04 装配与用例。执行和接收记录在本轮收尾统一补齐。

## 交付与审查

2026-11-09 21:32:23，当前主会话，architecture-05，方案修订 1，经实际运行代码及相关回归接受。

- 变更：`infrastructure/dispatch/{delivery,presence,lock,dependencies}` 与 `application/delivery/service.py`；成员轮询运行器调用应用观测动作，循环不执行 SQL。
- 验收：A04—A07，锁和并发机制留 runner；应用端口保存单次结果，unknown 不重发，首项启动与接收核验保留；lifespan 关闭线程并释放锁。
- 版本与前置：4c26eaf + 当前工作区 T04，未提交。
- 检查：单次拒绝/未知/后续精确输入确认及启动拒绝保留回执的无数据库测试通过；投递集成 4 项和成员状态生命周期回归通过，追加锁排他及关闭后可接任断言通过。
- 未完成项与风险：无目标偏差；真实共享 daemon 和容器未运行，执行范围仍为已有本机模式。
