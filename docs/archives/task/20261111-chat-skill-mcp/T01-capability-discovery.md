# Task / 子任务 T01：能力目录发现

最后修改时间: 2026-11-11 22:12:09

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：`docs/intent/20261111-chat-skill-mcp.md`。
- 权威总计划：`D:\SourceCodes\mywork\agent-relay\docs\plan\20261111-chat-skill-mcp.md`；任务 ID：T01；方案修订：1。

## Goal and acceptance / 目标与验收

- 交付 application-level 目录查询和 HTTP API：房间项目 Skill 列表及按成员目标 Codex 会话的 MCP 状态。对应意图 A02、A03。
- `GET /api/room/{room_id}/skills?force_reload=false` 按房间 `project_path` 调 `skills/list`，返回稳定 opaque ref、name、displayName、description、scope/source、pluginId 和 enabled；不回传 path/secret。
- `GET /api/room/{room_id}/member/{member_id}/mcp` 先验证 room membership 和有效 session，再按该目标 `threadId` 调 `mcpServerStatus/list`，读取全部分页，返回只读服务器/工具摘要、可用性和逐服务器错误，不包含认证凭据。
- HTTP/application 向后端 Codex adapter 传受限 typed arguments；MCP partial list error、无效 payload、跨 room member、deleted member 和 driver 断连均可识别；所有 app-server RPC 均在数据库事务外执行。

## Scope and files / 范围与文件

- 新建 application capability query/contracts/port 及对应 Codex infrastructure catalog adapter。
- 修改 `src/agent_relay/interfaces/http/` routes/dependencies；增加 capability route tests、driver unit/integration/RPC fixture tests。
- 本任务拥有 `infrastructure/codex/driver.py` 的 list-catalog 实现；T04 只能在本任务接受后增量修改该文件。不得修改 delivery enqueue 或 message schema。
- 不实现数据库 capability 持久化、composer UI、queue/add、CLI/MCP catalog 工具、安装器、凭据/OAuth 或直接 MCP tool call。

## Inputs / 输入

- 无前置 task。Codex 本机已核对 `codex-cli 0.167.1` app-server schema：`skills/list` 提供 cwd、errors、Skill metadata；`mcpServerStatus/list` 支持 `threadId`、cursor/detail；driver 不得把 wire schema 外漏 application。
- 房间成员 session CWD 由 `MemberService.add` 校验与 room project directory 一致；最终列表仍需对目标 thread 发协议查询。
- RPC driver 使用独立 `ProxyRpc`；任何持久读取作用域都应在调用外释放。

## Technical decisions / 技术设计

- 新 application service 承担 Skill/MCP 目录查询，注入 room/member query 与只读 capability RPC port；HTTP dependency 只负责装配，不自行查 SQLAlchemy、调用 RPC 或构造协议 JSON。
- Skill identity 在后端按来源/插件/name/相对 CWD path 形成稳定 opaque id；adapter 存留准确 native name/path 供 T04 重新解析，绝对路径不返回浏览器。
- MCP public ID 为原生 server name 的稳定 SHA-256 opaque ID，`name` 字段保留原名作展示；不对协议允许的名称字符做额外白名单校验。MCP 可用性必须按目标 member 的原 thread 检查，不能用房间或安装机器的全局配置冒充每个成员均可用。
- 能力目录返回失败信息时与“空列表成功”区分；服务器下工具分页和逐服务器错误要完整传播安全摘要。
- 重复请求合并/按规范化 CWD 做有界缓存仅作性能优化，manual force reload 绕过 cache；不能缓存 auth secrets 或声称缓存就是投递保证。

## Implementation outline / 实施安排

1. 定义 Skill/MCP public option、internal native binding 和 capability query port。
2. 在 Codex adapter 实现 Skill 列表及有 cursor 的目标 thread MCP 状态查询，校验响应字段和 server/tool pagination。
3. 装配 application query service：短读 room/member scope、退出 DB transaction、再读取外部目录；校验 caller scope 和跨房间资源。
4. 添加两个 HTTP GET API，返回稳定可识别失败语义并确保无 path/token 泄露。
5. 使用真实 API fixture 增加 adapter/unit/HTTP tests；提供通过审查的 API 类型给 T03、native resolver 给 T04。

## Checks and risks / 检查与风险

- 运行 capabilities unit/HTTP tests 和 Codex adapter RPC fixture/integration tests。
- 覆盖 Skill 空目录、同名跨 source、partial errors、refresh 参数；MCP 未配置/断连/分页、member 不存在/跨房间、响应格式不完整。
- 本地 protocol schema 变化时核对 installed CLI 实际 schema，不假设远程最新版与本地一致。未回传 secret/path；HTTP 目录不可直接用于调用。
- T04 依赖本 task 的已接受 binding resolver 和 MCP page normalization 接口，不自行重做第二套解析。

## Handoff basis / 交接依据

- 协议入口：`C:\Users\leon\.codex\plugins\cache\specflow-local\specflow\0.2.1\skills\specflow\SKILL.md` 与同目录下的 `references\task-coordination.md`。
- 分配与授权：用户消息 `room-94f73433cde7-msg-0101` 授权本计划范围内实施并审查；分配编号 `AR-20261111-T01-01`；总计划 registry 是权威记录。
- 工作区与基线：`D:\SourceCodes\mywork\agent-relay`，源基线 `cf901ed`，另有同一工作区的 SpecFlow 接受/分配记录及未提交导航修改。执行者接收时核对实际 HEAD/status 和 task 文档，不覆盖非本 task 文件。
- 可写回报位置：本文 Reception/progress 和 Delivery/review；主会话读取 task 和实际 diff。
- 回报渠道：Agent Relay 对架构师（主会话）直接回报，并更新本 task Reception/Delivery 章节。

## Reception and progress / 接收与进展

- 接收：高级开发已核对并接收 `AR-20261111-T01-01`，方案修订 1，父意图、计划及 task 均为 Accepted；无前置 task。有效代码基线为 `cf901ed6fa1fb02e6ebdffe2be57cb29ba6ae8ce`，叠加当前已接受 SpecFlow 文档工作区快照。
- 授权：主会话派发消息 `room-94f73433cde7-msg-0105` 及其引用的用户消息 `...msg-0101`；权限限于 T01 实施及必要开发检查。后者单条消息不在本成员查阅范围内，以主会话引用及权威计划授权记录为依据。
- 范围：仅能力目录 application/adapter/HTTP 查询、driver list 方法及相邻测试。保留现有 `RoomSwitcher.vue`、`useSidebarOrder.ts`、`room.css`、`style.css`、`RoomSwitcher.test.ts`、`useStoredOrder.ts` 未提交修改；不启动 T03/T04、不提交 Git、不操作真实 Codex 队列/会话。

| 时间                | 分配编号 / 执行者               | 接收、进展或阻塞                                                                                                                                                     | 证据 / 回报位置                                                                                                 |
| ------------------- | ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| 2026-11-11 21:05:22 | `AR-20261111-T01-01` / 高级开发 | 已核对 HEAD/status、修订 1、授权和无前置依赖，接收有效；开始实施                                                                                                     | 本节；权威计划 Execution registry；派发 `...msg-0105`                                                           |
| 2026-11-11 21:27:27 | `AR-20261111-T01-01` / 高级开发 | application/adapter/HTTP 已接线；本机只读 schema 导出核对完成；首轮联合 93 项定向测试及 mypy 通过，继续最终回归                                                      | `application/capabilities/`、`infrastructure/codex/catalog.py`、`interfaces/http/capabilities/`；本会话检查输出 |
| 2026-11-11 21:43:36 | `AR-20261111-T01-01` / 高级开发 | 按预审补充 public JSON shape、availability 与 T04 resolver 入口；待复查 MCP public ID 契约 | 本 Delivery；相关 capability tests；本会话检查输出 |

- 当前接口事实：Skill API 返回 `{skills, errors}`，选项为 `{type, id, name, displayName, description, scope, source, pluginId, enabled}`；MCP API 返回 `{servers}`，服务器为 `{type, id, name, available, status, tools, errors}`，工具只含 `name/description`。native path/schema/auth/config 不进入公开 DTO。
- 本机协议依据：通过 `codex app-server generate-json-schema --experimental --out <临时目录>` 只读导出 schema，未查询真实会话。`mcpServerStatus/list` 的 cursor 分页覆盖服务器列表；每个服务器的 `tools` 是完整 map，schema 没有另一个工具分页入口。目标 thread/CWD/loaded 状态均在 adapter 核验；工具错误与运行状态只转换成安全摘要。
- 后续 T04 可复用 `CodexDriver.discover_skills(project_path, force_reload=...)` 的 `SkillDiscovery/SkillBinding` 及强制刷新的 `resolve_skill(project_path, skill_id)`；此处尚未改动 enqueue。

## Delivery and review / 交付与审查

- 交付状态：本窗口已复核并接受。检查 application 事务释放、目标 thread/CWD 校验、MCP 全分页、typed DTO 敏感字段隔离、opaque ID 和当前测试；最近 265 项后端回归及类型检查通过。catalog 当前 SHA-256 `759cae0abac7a1412507f59e0cccb200b097a77a8b1ac7a02b0be5107ab97875`，driver 接入前 SHA-256 `c8175488ad97c7f7d33e7efe436b4648c2045866ba148d149a4e353a86b7aa6d`。未提交 Git。
- 实际变更：新增 application capability query、Codex catalog adapter 与两个 HTTP GET API；driver 增加 Skill discovery/resolver 与目标 thread MCP 分页查询。MCP 原生名称不再受额外字符白名单限制；public `id` 为 `mcp-` 加原生名称 UTF-8 SHA-256，`name` 保留原名供展示及 T04 定向解析。范围内无偏差。
- Public JSON contract：`GET /api/room/{room_id}/skills?force_reload=false` 返回 `{"skills": [...], "errors": [...]}`；Skill 项字段为 `type,id,name,displayName,description,scope,source,pluginId,enabled`。`GET /api/room/{room_id}/member/{member_id}/mcp` 返回 `{"servers": [...]}`；服务器字段为 `type,id,name,available,status,tools,errors`，工具只含 `name,description`。Skill 路径、工具 schema、认证信息、endpoint 和原始错误不公开。
- MCP availability：先在目标成员绑定的原始 thread 上验证 thread 身份、可用状态和 room CWD，再查目录。服务器 `available=true` 当且仅当 `runtimeStatus=connected`、没有 `toolsError`、且 `authStatus` 不是 `notLoggedIn`（`runtimeStatus=authenticationRequired` 映射认证未完成）；`starting/notStarted` 映射 `starting`，缺失 runtime 状态映射 `unknown`，其余运行失败态或工具目录错误映射不可用。分页/顶层 RPC 错误不返回伪造的部分成功列表。
- T04 使用入口：Skill 选择通过 `CodexDriver.resolve_skill(project_path, skill_id)` 强制刷新后解析，返回仅服务端持有的 `SkillBinding(option,native_name,native_path)`；缺失或 disabled 会拒绝。MCP 需按每个目标 `thread_id` 调用 `CodexDriver.list_mcp_servers(thread_id, project_path)`，用返回的 opaque `id` 与已存 ref 对齐、检查 `available`，并取对应项的 `name` 生成 native mention；不能把 public API JSON 直接当作 queue payload。尚未实现 T04 queue mapping。
- 验收证据：`uv run --locked pytest tests/unit tests/integration/persistence tests/integration/http tests/integration/codex -o addopts=-ra`：262 passed；`uv run --locked mypy src tests`：162 source files 无问题；`uv run --locked ruff check .` 通过；`uv run --locked ruff format --check .`：245 files already formatted。Web API 检查：`corepack pnpm exec prettier --check src/services/roomApi.ts tests/services/roomApi.test.ts`、相同文件 ESLint、`corepack pnpm typecheck` 均通过；`corepack pnpm test tests/services/roomApi.test.ts --reporter=default --silent=false --no-color`：9 passed。`git diff --check` 通过。
- 版本：源基线 `cf901ed6fa1fb02e6ebdffe2be57cb29ba6ae8ce`，工作区交付快照 19 个 T01 源码/测试文件；清单格式为排序后的相对路径与单文件 SHA-256，整体 SHA-256 `e8cccd42cc9ee8b84f425b8d094e71d5361ae0c94d0ace29f0009408bc50d812`。task 文档不包含在指纹内。
- 未完成项与风险：仅用本地 Codex app-server schema 和 subprocess RPC fixtures 验证，未对真实 Codex 会话执行 RPC；T03/T04 与整体 SpecFlow Verification 尚未开始，等待主会话接受 T01/T02 后分配。
