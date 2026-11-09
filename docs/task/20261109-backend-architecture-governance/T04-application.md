# 子任务 T04：应用用例与入口装配
最后修改时间: 2026-11-09 21:32:23

## 审查状态

Accepted

## 父任务与权威记录

权威[总计划](../../plan/20261109-backend-architecture-governance.md)，任务 T04，方案修订 1。

## 目标、范围与局部设计

交付 A03—A05、A07。RoomService 和 MemberSessions 只消费中立存储/会话端口；原始连接与 SQL 移除，外部核验前释放读事务，写入时重新核对。成员状态应用动作读取活动绑定、逐会话 inspect 并保存观测，运行循环不执行 SQL。

HTTP provider 按资源/房间/成员组织，以 Annotated Depends 显式组合；数据库资源直接桥接 app.state，不经业务服务反向取得。WebSocket 使用进程查询 provider，每轮独立短读。事务中间件依赖 transaction_factory。bootstrap 组合下层工厂并管理生命周期；CLI/MCP 和 RelayClient 迁移 interfaces，公开模块启动入口保留。迁移配置、日志和 reload 时核对文件路径与包资源。

## 输入与实施安排

使用 T02/T03 实现；迁移应用、入口与启动，更新测试/probes/迁移导入及 explicit store 注入。保持 HTTP DTO、错误、requestId、session 身份解析和全部 CLI/MCP 参数与结果。

## 检查与风险

运行应用单元测试及 HTTP、请求事务、事件、CLI/MCP、成员观测和启动测试。检查 domain/application 的依赖及接口注册；不启动开发服务。

## 交接依据与接收

当前主会话，architecture-04；使用同一工作区 T02/T03 的持久化和协议实现，授权见总计划。接收与连续集成记录收尾统一补齐。

## 交付与审查

2026-11-09 21:32:23，当前主会话，architecture-04，方案修订 1，交付按调用链与回归接受。

- 变更：application 的 RoomService/MemberSessions，HTTP provider 和适配模块、CLI/MCP/client、bootstrap、公开启动入口及内部消费者导入。
- 验收：A03—A05/A07，外部 inspect 前释放读取作用域并在写入重查；WS 用进程查询依赖短读；HTTP 请求惰性事务、响应前提交。app.state 不再通过业务对象桥接存储。
- 版本与前置：4c26eaf + 当前工作区 T02/T03 实现，无提交。
- 检查：全量 HTTP/WS、CLI/MCP、请求事务和成员观测回归通过；无数据库成员加入测试验证检查期间无作用域、并发事实重新核对；三个公开模块 --help 通过。
- 实施细化及风险：runner 工厂放在其能力包 dependencies，组合根引用；未改变外部契约。未运行真实页面和宿主联调。
