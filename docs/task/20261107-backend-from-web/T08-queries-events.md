# Task / 子任务 T08：有界查询与持久事件同步
最后修改时间: 2026-11-07 19:41:39

## Review status / 审查状态

Draft。初始化读取视图、事件保留/过旧游标和兼容切换契约须在接受方案前固定。

## Parent and authority / 父任务与权威记录

- [总意图](../../intent/20261107-backend-from-web.md)、[权威总计划](../../plan/20261107-backend-from-web.md)。任务 ID：T08；方案修订：10。
- 协调根：`D:/SourceCodes/mywork/agent-relay`；直接依赖由总计划定义。

## Goal and acceptance / 目标与验收

G12、G13，对应 A07、A08 数据部分：历史查询有上限，引用可按 ID 读，事件可重连恢复，分页/筛选不改变全房间统计。

## Scope and files / 范围与文件

`room_queries.py`、`room_events.py`、`routers/room.py`、DTO、索引/事件迁移及 API/事件测试。Web UI 归 T09，成员范围封装归 T07。

## Inputs / 输入

见总计划 T08：T03 已接受的消息/投递/事件 schema，T04 真实状态与更新事件契约。下游使用接口必须在 Plan 接受时固定，不能由 T07/T09 猜测。

## Technical decisions / 局部技术设计

- 元数据/全局统计与有界消息查询分开，默认 50、最大 200；时间线按 `(roomId, seq)` 游标分页，不使用易漂移的 offset 页号。话题跨页消息去重，直接 @ 消息在全房间可见。
- 单条按 roomId/messageId 读取，提供引用定位和真实投递详情；receipt 只返回必要可解释字段。全局统计用全房间查询，不从当前页累计。
- 独立 RoomEvent 游标覆盖资源、消息和 Delivery 变化；事件持久化与业务提交同一事务，通知在提交后。HTTP 补取和 WebSocket 读取同一事实源。
- 资源事件含 T02 成员创建操作/绑定/恢复事实的变化，返回可查询的 operationId 与版本；Web/CLI 可找回同一创建，不靠刷新时另发创建请求。
- 初始化元信息/消息页与起始 eventId 在一致读取视图取得，再从该游标补取；WebSocket 重复/乱序按 eventId 和对象版本处理，不能只依赖实时通知。
- 首版事件持久保留；若今后裁剪必须维护最小可用游标并返回明确 resyncRequired。未知游标、断连和重启可用 HTTP 补取或重新同步恢复。
- 房间切换和成员权限上下文固定；空历史与断连不是错误投递。变更当前全量 snapshot 的契约与 T09 同步，不能静默截断仍被当作全历史的数组。

## Implementation outline / 实施安排

1. 固定路由/DTO、分页/统计和一致初始化响应，建立必要索引与单条读取。
2. 实现事件游标 HTTP 接口、WebSocket 通知与断连补取；提交后唤醒是优化，DB 扫描仍能补齐。
3. 增加重复/丢通知/重启/游标失效场景及旧 Web 兼容切换步骤。
4. 向 T07、T09、T10 交付接口与 fixture，记录实际 schema 和 API 版本。

## Checks and risks / 检查与风险

- 大于两页历史、查询中持续新增、跨话题去重、引用不在当前页、房间隔离、全局统计不随页变化。
- 同一 Delivery 多次事件可补取；初始化期间并发写入不漏事件；事务回滚不通知；断连/重复通知/过旧游标恢复。
- 相关 pytest、mypy、ruff；避免长事务等待网络，WebSocket 取消须释放连接和监听任务。

## Handoff basis / 交接依据

未分配。沿用总计划 SpecFlow 协议，派发时核对 T03/T04 已接受版本、授权与有效编号。本文为回报位置；路由/模型等共享文件由主会话串行整合。

## Reception and progress / 接收与进展

无接收、无实现。接收时记录接口版本与前置验收事实。

## Delivery and review / 交付与审查

无交付。提交 API/事件协议、版本/diff、分页与恢复证据、检查/复验和未完成项，由主会话审查接受。
