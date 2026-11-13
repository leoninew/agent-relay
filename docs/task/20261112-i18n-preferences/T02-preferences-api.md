# Task / 子任务 T02：偏好 HTTP 接口与服务装配
最后修改时间: 2026-11-12 23:16:10

## Review status / 审查状态

Accepted

局部方案随父级 Plan 修订 2 接受；等待前置交付后分配，实施交付另行审查。

## Parent and authority / 父任务与权威记录

- 总意图：[中英多语言与用户偏好设置](../../intent/20261112-i18n-preferences.md)。
- 权威总计划：[Plan](../../plan/20261112-i18n-preferences.md)；任务 ID：T02；方案修订：1。
- 权威协调根：`D:\SourceCodes\mywork\agent-relay`；执行前置与审查只以总计划为准。

## Goal and acceptance / 目标与验收

交付供 Web 与桌面共享的偏好服务和 HTTP 契约，对应 A03、A04、A08。

- GET 返回当前有效策略和解析语言；PATCH 只保存一个经过校验的语言策略。
- 存储读写失败映射稳定错误码，保留请求 ID 和安全的 5xx 摘要。
- HTTP 与桌面能注入同一服务实例，不持有聊天室事务或调用 Codex。

## Scope and files / 范围与文件

- `src/agent_relay/bootstrap/http.py`。
- `interfaces/http/routes.py`、`exception_handlers.py`、新 `preferences/routes.py`、`preferences/dependencies.py` 与包入口。
- HTTP 依赖桥接、偏好接口与启动装配相关的单元测试。
- 不修改 `bootstrap/desktop.py`、房间模型、数据库、业务错误抛出点或前端；T04／T06 在本任务接受后接续各自修改。

## Inputs / 输入

- 直接前置 T01：已接受的 Preferences DTO、读写端口／异常、应用服务、工厂和可访问版本。
- 使用总计划 D03 固定接口，派发时登记 T01 的实际交付版本；仅有 task 自报完成不满足输入条件。
- 当前 `app.state`／HTTP dependency 惯例、统一错误响应及请求 ID 中间件。

## Technical decisions / 局部技术设计

- 在 `create_app/build_app` 增加可选 `preferences_service` 参数。缺省由 T01 工厂创建，传入时原样复用；桥接到 `app.state.preferences` 并由 typed dependency 取出。
- `GET /api/preferences` 返回 200 的 `{language,resolvedLanguage}`；字段来自服务，不从浏览器 header 推导语言。
- `PATCH /api/preferences` 请求 language 必填，只允许三种策略，拒绝未知字段；成功响应与 GET 同形，只有文件保存成功才返回 200。
- 由异常处理器将 `PreferenceReadError/PreferenceWriteError` 分别转换为 503 的 `preferences_read_failed/preferences_save_failed`，记录内部异常；响应不带路径或 I/O 原文。
- 请求校验使用现有 422／`validation_error`；不改变 `{code,error,requestId}`、`X-Request-Id` 或 `Retry-After` 的既有能力。
- 偏好读写只使用文件服务，不触发惰性的 SQLite transaction；不把所有运行配置开放成可写对象。

## Implementation outline / 实施安排

1. 装配并注入 T01 服务，保留现有调用者缺省行为及测试替身能力。
2. 新增偏好 router／provider，接入总 api_router。
3. 注册偏好读写异常映射，核对已存在的 room／session 异常处理不回退。
4. 用替身服务和直接调用检查 DTO、handler、依赖及装配，交付参数签名和错误行为给 T03／T04／T06。

## Checks and risks / 检查与风险

- GET 缺省／固定语言、PATCH 三个合法值、字段缺失／非法值／额外字段的 DTO 单元。
- 检查传入服务未被重新创建、GET 不写文件、PATCH 仅保存一次且没有 Codex 或数据库操作。
- 读写失败保留状态、code、body/header requestId；5xx 不泄露原始异常或文件路径。
- 使用 fake service／Request 和装配替身，不启动真实 Uvicorn、HTTP、Codex 或 SQLite；不新增集成测试脚本。
- 定向执行相关 Python 单元及 mypy／Ruff；记录供下游可访问的实际 diff。
- 共享风险：T04 也会修改 exception_handlers；本任务交付接受后才放行该写入。

## Handoff basis / 交接依据

- 未分配；无有效分配编号或实施授权。
- 协议入口与回报规则见总计划“协调信息”及 SpecFlow 协作契约。
- 工作区：`D:\SourceCodes\mywork\agent-relay`；派发时记录当前基线和 T01 已接受版本。
- 可写回报位置：本文“接收与进展”“交付与审查”；默认输出可复制摘要由用户转交主会话。

## Reception and progress / 接收与进展

2026-11-12 23:02:30：执行者 `independent-20261112-225606` 接收 `T02-20261112-230230`，方案修订 2，用户委托实施。基线为 HEAD `e57ede1` 加已接受的 T01 工作区文件；T01 服务、DTO、工厂及检查可访问，记录见 T01 交付。无共享写入冲突。

| 时间 | 分配编号 / 执行者 | 接收、进展或阻塞 | 证据 / 回报位置 |
| --- | --- | --- | --- |
| 2026-11-12 21:32:46 | 无 / 无 | 已记录方案，等待授权及 T01 交付接受 | 本文与总计划 |

## Delivery and review / 交付与审查

- 2026-11-12 23:16:10，`T02-20261112-230230` 提交；前置为 T01 accepted 工作区版本，交付为 HEAD `e57ede1` 加当前 T01、T02 工作区文件。新增偏好路由、注入依赖、HTTP 装配、读写异常映射与偏好路径事务绕过。
- A03／A04：GET 与 PATCH 调用同一服务，严格 DTO 限定字段与策略；应用可注入同一实例。A08：读写异常分别映射 503 和指定 code，复用安全摘要与请求 ID；验证错误沿用既有 422 handler。fake 测试确认无事务工厂调用；未启动真实 HTTP、SQLite 或 Codex。
- `uv run --locked pytest tests/unit/interfaces/test_preferences.py tests/unit/interfaces/test_http_errors.py tests/unit/interfaces/test_transaction_middleware.py`：17 passed；相关文件 Ruff、格式检查与 mypy 通过。首次 Ruff 提示两处长行，修正后通过。
- 主协调者核对实际代码、注入身份、错误映射及检查后接受 T02，放行 T03、T04、T06。按串行安排先执行 T03；全量检查归 T07。真实 HTTP 运行未测试，按约定使用直接调用和 fake；其他未完成项、范围偏差及待仲裁事项：无。
