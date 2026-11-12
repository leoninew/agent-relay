# Task / 子任务 T02：偏好 HTTP 接口与服务装配
最后修改时间: 2026-11-12 21:32:46

## Review status / 审查状态

Draft

局部方案属于父级 Plan 修订 1。未接受、未分配，未授权实施。

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

尚无接收记录。

| 时间 | 分配编号 / 执行者 | 接收、进展或阻塞 | 证据 / 回报位置 |
| --- | --- | --- | --- |
| 2026-11-12 21:32:46 | 无 / 无 | 已记录方案，等待授权及 T01 交付接受 | 本文与总计划 |

## Delivery and review / 交付与审查

- 未实施、未交付；未产生当前分配、实际版本、检查或修复记录。
- 正式交付时填写变更／范围偏差、A03／A04／A08 结果、T01 使用版本、检查与未完成项。
- 主会话尚未接受交付，不放行 T03、T04、T06。
