# 子任务 T03：Codex 协议适配边界
最后修改时间: 2026-11-09 21:32:23

## 审查状态

Accepted

## 父任务与权威记录

权威[总计划](../../plan/20261109-backend-architecture-governance.md)，任务 T03，方案修订 1。

## 目标、范围与局部设计

交付 A03、A06、A07。驱动迁移到 infrastructure/codex；RPC 传输异常保留在该边界。SessionInfo、QueueHead、ReceivedInput、InputPage 由中立契约拥有；原始 notLoaded/systemError 映射为业务不可用/异常状态。enqueue 验证匹配回执，返回 QueueReceipt(id, metadata)，剔除 input。队列明确拒绝映射 QueueRejected，启动拒绝映射 ActivationRejected，应用不依赖 RpcRejected。

## 输入与实施安排

使用 T01 契约；迁移类型和驱动、接通普通工厂、调整 fake driver 与协议 fixture 断言及 probes 的内部导入。保持每次 RPC 的 proxy 作用域、共享 daemon 范围、队列首项与精确输入匹配规则。

## 检查与风险

运行现有协议 fixture 测试，核对 receipt、分页、会话身份和 proxy 子进程关闭；不运行真实 daemon 探测。

## 交接依据与接收

当前主会话，architecture-03，使用 T01 契约和用户连续实施授权；接收及执行登记在本轮收尾按实际工作区补齐。

## 交付与审查

2026-11-09 21:32:23，当前主会话，architecture-03，方案修订 1，交付经局部审查接受。

- 变更：`infrastructure/codex/{driver,dependencies}`，消费中立 SessionInfo、QueueReceipt、QueueHead 和输入证据；queue/start 明确拒绝转换 ActivationRejected。
- 验收：A03/A06/A07，queue/add 回执在 adapter 校验并剔除 input；原会话分页、身份、skill 与 proxy 回收保持，业务和数据库不导入该驱动。
- 版本与前置：4c26eaf + 当前工作区 T01 契约；未提交。
- 检查：协议 fixture 与投递/事务/成员中间 43 项回归通过，最终全量及 probes/migrations 类型检查通过；fixture 真实回显 input 验证边界。
- 范围偏差及风险：无；未运行真实 daemon，也未替换会话或修改宿主。
