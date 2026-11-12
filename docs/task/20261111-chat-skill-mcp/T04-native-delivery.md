# Task / 子任务 T04：Codex 原生能力投递

最后修改时间: 2026-11-12 08:16:13

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：`docs/intent/20261111-chat-skill-mcp.md`。
- 权威总计划：`D:\SourceCodes\mywork\agent-relay\docs\plan\20261111-chat-skill-mcp.md`；任务 ID：T04；方案修订：2（按用户最新指令收紧测试范围）。

## Goal and acceptance / 目标与验收

- 将已持久化的 Skill 和 MCP server refs 按目标 Session 准确翻译为 app-server `thread/queue/add` 原生输入，对应意图 A05–A07。
- QueueDriver/Application 传递稳定 typed delivery request；Codex adapter 负责读取 Skill/native path、MCP/server binding 和序列化；native RPC dict不泄露domain/application。
- Skill 使用已接受 T01 resolver 精确对应 name/path；必需的 `agent-relay:agent-relay` Skill 每次仍校验/附带一次，与用户选择去重。不得只凭同名 fallback。
- MCP server 经 T01目标 thread检查并生成对应 `{type: "mention", name, path: "mcp://<server>"}`。不发起 `mcpServer/tool/call`；tool execute result不会伪装成 Relay receipt。
- 缺失/禁用/不兼容的已选 ref 属于入队前确定拒绝且不调用 `thread/queue/add`；队列提交已发出但回执无法确认，继续记录 unknown、不重复 add 或 start。
- 现有 text/envelope、clientUserMessageId、frozen recipient target、FIFO、receipt validation、activation guard 和 received input 核验均保持。

## Scope and files / 范围与文件

- 修改 `src/agent_relay/application/delivery/ports.py` typed request、`application/delivery/service.py` 组装持久化 message refs 和 `infrastructure/codex/driver.py` 原生 payload。
- 通过 T01 capability resolver/port 复用同一 adapter query binding；只在本任务中增加投递前 target validation 与 input construction。
- 只更新单层 Codex adapter/delivery action 单测，不新增真实 SQLite、跨层或可由单测覆盖的集成测试，不恢复用户删除的测试和支持目录。
- T04 与 T01 在 `driver.py` 有共享写入：必须等 T01 被接受，基于其交付版本只做增量；不能用自身分配覆盖 T01 仍在工作的文件。
- 不修改 message migration/replay contract（由 T02 所有）、Vue composer/API（由 T03 所有）、实际 Codex 安装或已运行线程。

## Inputs / 输入

- 前置 T01：已接受的目标 thread catalog request/response、完整 cursor binding、stable native resolver 及其测试。
- 前置 T02：已接受的 `Message.capabilities` 类型、persist/query mapping、publication identity 与单目标 delivery refs。
- Room DeliveryService 与 external RPC 不同数据库 transaction；一 delivery 对应一个已冻结目标 thread，可分别核验能力。

## Technical decisions / 技术设计

- 把 `QueueDriver.enqueue` 签名从裸 `text` 变更为 typed `QueueRequest`（text + capabilities）；`DeliveryService` 按 Room ID/message ID/seq/created_at/sender/content 现有格式保留 envelope，追加的refs绝不信任调用方native path。
- 通过 driver 调用既有 read/skills catalog、thread-scoped MCP catalog 完成实时核验；读完再原子性尝试一次 `thread/queue/add`。目录预检全部在queue add之前，避免已知无效引用造成 unknown。
- 已有 relay Skill 与选定 Skill 按稳定identity去重；结果必须准确保留官方 app-server UserInput schema的 `type`, `name`, `path` 字段。
- Skill解析成功但 queue/add 返回有效 receipt 后，继续 `queue_accepted` 并按既有唯一守卫激活；确定性的 capability errors映射 `QueueRejected`/rejected；传输或 receipt ambiguous继续 unknown。
- 多recipient逐 target生成相同 frozen user refs 的原生 request；送前验证target能力。任何外部 add之后不因验证/数据库finish失败自动重复外部调用。

## Implementation outline / 实施安排

1. 核对 T01/T02 被接受版本与 shared driver diff，确认app-server schema和request model。
2. 新建/修改 QueueRequest 与 `QueueDriver` protocol，delivery service提供封装正文和持久化引用。
3. 实现每目标能力绑定检查、Relay Skill 去重和 native Skill/MCP Mention items；合并错误分类。
4. 扩展 RPC fake并按协议列表顺序验证 payload、目标 ID、selected refs和 receipt。
5. 验证确定拒绝仅在 queue/add之前、ambiguous add结果只有一次尝试、活动和接收核验未回归。

## Checks and risks / 检查与风险

- 单层 driver 与 application delivery action 单测：精确 native input、Relay Skill 一次、MCP 目标绑定、缺能力拒绝/no add；RPC 与仓储均使用替身。
- 复现 `thread/queue/add` 网络结果不确定并验证不会二次调用；校验回执必须匹配 `clientUserMessageId`，未知结果不被能力失败覆盖。
- 使用 `uv run --locked pytest tests/unit`；应用层仓储和驱动均由端口替身隔离，Codex adapter 使用内存 RPC 替身，不运行跨层、真实 SQLite 或界面测试。
- 协议响应/错误结构与 CLI 版本可能不同，所有 native structures通过 fixture验证；用户path不来自浏览器/DB snapshot，实际target binding需最终重解析。

## Handoff basis / 交接依据

- 协议入口：用户可见的 SpecFlow skill 及其 `references/task-coordination.md`。
- 分配与授权：总计划 Coordination/Execution registry 与用户接受记录；本任务尚未分配。
- 工作区与基线：`D:\SourceCodes\mywork\agent-relay`；派发时核对实际 HEAD/worktree；已有未提交导航工作区改动必须保留。
- 可写回报位置：本文 Reception/progress 和 Delivery/review；主会话读取 task 和实际 diff。
- 回报渠道：未分配；收到有效编号后回主会话提供可复制摘要。

## Reception and progress / 接收与进展

- 接收：用户“推进实现”授权本窗口实施；T01/T02 已接受。已只读导出本机 `ThreadQueueAddParams` schema，确认 skill/mention 均要求 type/name/path；不操作真实会话队列，开始本地 T04。

| 时间 | 分配编号 / 执行者 | 接收、进展或阻塞 | 证据 / 回报位置 |
| ---- | ----------------- | ---------------- | --------------- |

## Delivery and review / 交付与审查

- 交付：实现和单测清理完成，本窗口代码审查接受；用户已确认界面验收通过，原生队列行为使用内存 RPC 替身核对。
- 实际变更：QueueRequest 携带封装正文、room project_path 与已存 typed refs。每个冻结目标重新核验 thread 身份/状态/CWD，批量刷新 Skill 并按 ID 精确绑定；必需 Relay Skill 只附带一次。MCP 按目标实时核验后生成原生 mention，忽略客户端 name 快照作为执行身份。
- 错误边界：全部能力预检在 queue/add 前完成；失败确定拒绝且无外部写入。add 明确拒绝沿用 rejected；已发出后的超时/错误回执沿用 unknown，不重复 add/start；原消息 envelope 和 activation 守卫不变。
- 当前检查：`uv run --locked pytest tests/unit`：177 passed，1.50s，包含 adapter 的 14 项能力投递单测；`mypy src tests/unit`：137 files 通过；Ruff 检查及格式检查：32 个单测文件通过，`git diff --check` 通过。
- 测试清理：移除 8 个模块对已删除 support 的依赖。应用层改用仓储/驱动端口 Mock；目录 payload 为局部 fixture；领域投递规则移至 domain 单测，消息测试不再串联 MemberService。不恢复共享模拟仓储或已删除目录，不运行真实 SQLite、跨层或 UI 测试。
- 最终检查：全量后端类型检查因残留集成测试依赖已删除 support 而失败，现已删除 4 份失效脚手架并清理 marker，未扩大忽略范围；`mypy src tests migrations` 140 files、后端 177 项单测及全仓 Ruff lint/format 通过。
- 版本：当前 application delivery ports/service 和 infrastructure Codex driver 工作区；未提交 Git，未操作真实会话队列。最终证据见 `docs/verification/20261111-chat-skill-mcp.md`。
