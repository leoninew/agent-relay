# Task / 子任务 T10：Relay HTTP CLI 客户端
最后修改时间: 2026-11-07 19:41:39

## Review status / 审查状态

Draft。命令与 JSON/退出码契约须在 Plan 接受前固定；不复刻 housekeeper 命令或状态文件。

修订 9：成员入口统一为项目目录会话发现、选择和持久绑定；移除 operationId 新建状态/结果查询前提。Relay 生命周期只管理自身服务与连接，不自动新建、恢复或关闭成员宿主。

## Parent and authority / 父任务与权威记录

- [总意图](../../intent/20261107-backend-from-web.md)、[权威总计划](../../plan/20261107-backend-from-web.md)。任务 ID：T10；方案修订：10。
- 协调根：`D:/SourceCodes/mywork/agent-relay`；任务定义及执行登记见总计划。

## Goal and acceptance / 目标与验收

G15，对应 A03、A15：CLI 与 Web 共享 Relay 的持久事实，覆盖资源管理、发布、结果找回与查询，网络/等待/取消不悄悄改写投递事实或重发。

## Scope and files / 范围与文件

`cli.py`、HTTP client、`pyproject.toml` 入口及必要锁文件、README/帮助说明和 CLI 测试。CLI 不直接写数据库、不直连 Codex 队列、不创建另一套后台调度器。

## Inputs / 输入

见总计划 T10：T02 资源 API、T03 发布幂等、T08 查询/事件契约。成员自主管理权限沿用已接受 D10。

## Technical decisions / 局部技术设计

- 建议标准库 argparse，命令分为 room/topic/member/message/delivery；入口名、参数、输出和退出码在计划接受前形成具体命令表。
- 所有业务通过 Relay HTTP，集中配置服务地址/连接超时；调用身份与 Web 规范一致。发布接受调用方稳定 publicationId 并返回结果找回键，不用 requestId 替代。
- JSON 输出结构稳定，包含业务结果、requestId 和已有 message/delivery 事实；普通查询失败与结果未知分别表达，不能都用“发送失败”概括。
- publish 仅等待 Relay 持久接收，队列结果从持久记录查询；不增加会话输出 observe/等待命令，停止等待 HTTP 不撤销或重新入队。
- 不提供隐式自动重试发送；结果找回是只读。明确拒绝后的人工再发复用 T04 确定的操作契约。
- 成员命令通过 T02 API 列出项目目录已有会话，以 sessionId/name/topicIds 加入；无后台新建操作或创建结果等待。重复 409、校验 422、读取失败 503 按统一契约输出；不自动重发加入请求。

## Implementation outline / 实施安排

1. 固定命令/输出/退出码表，覆盖创建/列出房间、话题和成员、修改订阅、发布、查询消息/投递及结果找回。
2. 实现 HTTP 客户端、JSON/人类可读展示与请求 ID 保留；输入本地校验不替代服务校验。
3. 编写可重复的 CLI → 服务 → Web 共享持久记录示例，不直接观察模型输出。
4. 打包 console entry，更新帮助与运行说明；不修改用户 Codex 配置。

## Checks and risks / 检查与风险

- CLI 测试覆盖参数、HTTP 错误契约、断连/超时后找回、重复发布键、unknown、请求取消；用临时服务/伪 HTTP，不对真实会话重发。
- 成员创建键重放/冲突、响应未知后只读找回、取消等待后同一成员可查；CLI 不直接拥有 app-server 进程。
- 相关 pytest、mypy、ruff；构建与入口 smoke 检查纳入 T11。需要依赖时使用项目锁文件，不能假设开发依赖已在运行包可用。
- Web/CLI 命名各异不改变共同事实；CLI 缓存不能成为资源或投递权威。

## Handoff basis / 交接依据

未分配。遵循总计划 SpecFlow 协议；派发时登记有效编号、授权和 T02/T03/T08 版本。本文为回报位置，打包/锁文件由主会话串行整合。

## Reception and progress / 接收与进展

无接收、无 CLI 实现。后续记录实际命令契约与输入版本。

## Delivery and review / 交付与审查

无交付。提交命令/输出契约、实际版本与测试证据、未完成项和风险，输出 T10 摘要，主会话接受后放行依赖。
