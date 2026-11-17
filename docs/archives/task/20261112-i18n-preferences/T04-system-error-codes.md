# Task / 子任务 T04：系统错误与会话原因语义
最后修改时间: 2026-11-12 23:29:04

## Review status / 审查状态

Accepted

局部方案随父级 Plan 修订 2 接受；等待前置交付后分配，实施交付另行审查。

## Parent and authority / 父任务与权威记录

- 总意图：[中英多语言与用户偏好设置](../../intent/20261112-i18n-preferences.md)。
- 权威总计划：[Plan](../../plan/20261112-i18n-preferences.md)；任务 ID：T04；方案修订：1。
- 权威协调根：`D:\SourceCodes\mywork\agent-relay`。

## Goal and acceptance / 目标与验收

交付不依赖中文原文判断的公开错误／原因码，对应 A08，供 T05 本地化系统反馈。

- 产品业务异常使用稳定 code，状态、错误结构及请求 ID 保持。
- 会话不可用原因提供独立语义码，旧文本仍可作为诊断读取。
- 不修改投递状态机、CLI/MCP 字段或持久化结构，不进行历史诊断迁移。

## Scope and files / 范围与文件

- `domain/rooms/errors.py`、`rules.py`、`resources.py`、`members.py`、`positions.py` 的错误定义／抛出点。
- `application/rooms/service.py`、`messages/service.py`、`members/service.py`、`members/sessions.py`、`capabilities/service.py`、`capabilities/ports.py` 和 `dto/members.py`。
- `infrastructure/persistence/resource_queries.py`、`message_queries.py`、`repositories/context.py` 的现有业务错误抛出点。
- `interfaces/http/exception_handlers.py` 及相关领域／应用／接口单元；必要时同步结构化响应兼容测试。
- 不修改 bootstrap 装配、前端、桌面、投递持久化字段、旧 SQL 或 migration head。

## Inputs / 输入

- 直接前置 T02：已接受的 HTTP 异常处理版本与可访问代码，避免并发修改同一 handler。
- 语义码唯一清单为总计划 D06，HTTP 状态映射沿用当前异常分类；新增码须先回报主会话更新计划，不能留给界面猜测。
- 当前错误抛出点已核对，包含房间／成员／话题、发布清空冲突、上下文范围、会话接入及能力读取。

## Technical decisions / 局部技术设计

- 异常保留原有字符串消息和分类，增加可选命名参数 code；未传码的旧调用使用原状态类默认码。业务代码改为显式语义码，不建立“中文字符串 → code”映射。
- 404 区分 room/topic/member/message/publication 及消息范围；409 区分同名、已有房间／会话、发布身份冲突／已清空；422 区分路径、路由目标、固定人类成员修改及引用限制。详细枚举采用 D06。
- SessionUnavailableError、CapabilityUnavailableError 保持 503 和安全摘要，分别携带会话元数据、身份不匹配及能力目录 code，handler 不向响应泄露异常详情。
- `SessionInfo.unavailable_reason_code` 按事实分支：archived 优先 `session_archived`，error 为 `session_error`，其他不可用为 `session_not_connected`，可用为 None。
- `SessionCandidate.unavailable_reason_code` 以 `unavailableReasonCode` 序列化，可空且缺省 None，便于旧 fixture／调用者兼容；`unavailableReason` 保留。
- 加入成员的不可用冲突沿用现有异常／状态，但 code 来自原因属性，缺少具体原因时为 `session_unavailable`。不从 reason 文本反推状态。
- `CatalogIssue` 已有语义 code 直接复用；member.activity、Delivery.error/note 和第三方文本不做语言替换。
- 不引入语言偏好到领域或业务 service；本任务只生产语义，翻译由展示端消费。

## Implementation outline / 实施安排

1. 为异常增加兼容的 code 能力，逐处配置总计划中对应的业务码。
2. 更新 HTTP 映射，保留原 HTTP 状态、请求 ID、5xx 诊断日志和安全响应。
3. 添加 SessionInfo／Candidate 原因码并接线到候选会话与加入校验。
4. 补充行为单元，交付“抛出点—code—状态”核对清单及新增 DTO 字段给 T05。

## Checks and risks / 检查与风险

- 代表性同状态不同业务码：项目已建房／成员同名／话题同名／发布冲突；无实际接收者与排除发布者后无接收者。
- 检查 publication 已清空、消息不在可见范围、未加入会话和固定用户限制的原行为不变。
- DTO 检查归档／error／未接入／可用、原因码序列化和缺省字段兼容。
- handler 保持 code、HTTP 状态、requestId、5xx 不泄露原消息；CLI client 仍按状态和结构处理，不因新增 code 自动重试。
- 使用现有 fake／mock 运行定向 Python 单元和 mypy／Ruff，不建 SQLite，不接真实 Codex。
- 风险是遗漏某个业务抛出点或把所有不可用错误压为同一码；通过源码检索与场景检查共同核对。

## Handoff basis / 交接依据

- 未分配；无有效分配编号或 Implementation 授权。
- 协议入口与权限见总计划“协调信息”和 SpecFlow 协作契约。
- 工作区：`D:\SourceCodes\mywork\agent-relay`；派发时登记 T02 已接受的 handler 基线。
- 可写回报位置：本文“接收与进展”“交付与审查”；主会话读取后审查，默认由用户转交摘要。

## Reception and progress / 接收与进展

2026-11-12 23:23:15：执行者 `independent-20261112-225606` 接收 `T04-20261112-232315`，方案修订 2，用户委托实施。基线为 HEAD `e57ede1` 加已接受 T01–T03 工作区文件；直接前置 T02 handler 与检查可访问，无共享写入冲突。

| 时间 | 分配编号 / 执行者 | 接收、进展或阻塞 | 证据 / 回报位置 |
| --- | --- | --- | --- |
| 2026-11-12 21:32:46 | 无 / 无 | 已记录方案，等待 T02 交付接受和授权 | 本文与总计划 |

## Delivery and review / 交付与审查

- 2026-11-12 23:29:04，`T04-20261112-232315` 提交；前置为 T02 accepted 工作区版本，交付为 HEAD `e57ede1` 加当前 T01–T04 工作区文件。领域、应用和持久化的现有业务异常抛出点显式指定 D06 code；异常类别、原文及状态保留。SessionInfo／Candidate 增加原因码并保留原文。
- A08：404／409／422 与 503 的代表性映射、请求 ID、5xx 安全摘要、会话归档／异常／未连接原因及原异常文本经单元检查。`rg` 核对现有抛出点，包含房间清空、发布清空、上下文查询和能力目录；无数据库迁移或历史诊断修改。
- `uv run --locked pytest tests/unit/interfaces/test_business_error_codes.py tests/unit/application/test_room_service.py tests/unit/application/test_message_service.py tests/unit/application/test_capabilities.py tests/unit/application/test_context_provision.py`：41 passed；相关 Ruff 与 `uv run --locked mypy src/agent_relay` 通过。未启动真实 HTTP／数据库／Codex；全量回归归 T07。
- 主协调者核对实际变更与检查后接受 T04，T03／T04 集成版本可供 T05 使用。范围偏差、未完成项及待仲裁事项：无。
