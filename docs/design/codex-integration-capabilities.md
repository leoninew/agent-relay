# Codex 接入能力核验与方案建议
最后修改时间: 2026-11-07 19:41:39

## 状态与结论

T01 已按当前收窄范围接受，T02 存储保留，成员接入已按修订 9 纠偏。其余产品取舍与功能仍按完整台账推进。本文的真实观察、协议定义、工程建议与待确认事项分别记录；协议探测不代替产品验收，实际 T02 交付以最新任务记录和产品烟测为准。

在本机 Codex `0.167.0` 下，已验证两条路径：

1. 通过既有共享 daemon 的公开 proxy，可以按项目目录发现会话元数据；未向用户已有工作会话投递、恢复或修改配置。
2. 在独立 app-server 进程和临时工作目录中，新建持久会话、注册动态工具、真实入队、忙碌时连续入队、工具回调、历史分页与进程重启后的工具恢复均可用。

关键限制：相同 `clientUserMessageId` 重复提交会生成不同队列项，不能用它实现上游幂等。动态工具在本机公开 schema 中仅能通过 `thread/start` 提供，`thread/resume` 和 `thread/settings/update` 没有同等添加字段；恢复已存储的工具与给任意已有会话新增工具是不同能力。

**D02 最新纠偏已接受**：用户明确添加成员应列出聊天室目录下已有 Codex 会话，并要求“纠偏”。Relay 持久管理成员和原会话绑定，不隐式创建、恢复、重命名或注入会话。原先独立运行时和创建时动态工具的主路径推论撤回；本机已有会话发布/查阅入口属于 T05/T07 主线待核验，额外宿主才归 T12。

D07 保持显式结构化目标、受控成员身份与来源幂等规则；已有会话的实际发布入口在 T05 实施前核验。创建时动态工具只是已测能力，不能推导为任意已有会话的必经路径。

后续用户已确认 D03“成员发布时排除自己”并接受[统一术语](terminology.md)。发布目标先全部校验，按话题订阅与 @ 取并集去重，再排除可信绑定的发布成员，之后检查非空；显式 @ 自己不例外。D09 自动链限制仍待取舍。

最新[审视修正](20261107-architecture-review.md)按用户反馈收窄职责。下文协议事实保留，修订 5 的执行权限管理、全部工具冻结、输出观察和后台工具核对要求已撤回；备份/恢复后置。

## 证据与可重复入口

- 父记录：[总意图](../intent/20261107-backend-from-web.md)、[总计划](../plan/20261107-backend-from-web.md)、[T01](../task/20261107-backend-from-web/T01-capabilities.md)。
- 可审查的脱敏证据：[20261107-codex-0.167.0.json](evidence/20261107-codex-0.167.0.json)。包含真实队列回执、active 状态下的队列分页、回调上下文、历史字段、重载观察和 12 个 schema 指纹，不含认证配置、其他会话正文或账号用量通知。
- 独立探测脚本：[codex_capabilities.py](../../scripts/probes/codex_capabilities.py)。不导入、复制或依赖 housekeeper；不属于产品驱动实现。
- 本轮队列恢复：[脱敏证据](evidence/20261107-codex-queue-recovery.json)、[codex_queue_recovery.py](../../scripts/probes/codex_queue_recovery.py)。新建临时会话 active 时确认两条待处理项，强制结束自有 app-server，恢复原 thread 后两条 clientId 均进入历史，没有再次 add；测试会话已归档。
- 临时原始产物目录：`C:/Users/leon/AppData/Local/Temp/agent-relay-t01-20261107-1213`；schema 由本机 CLI 生成，原始通知仅供本地调查，长期审查使用仓库内脱敏证据。
- CLI 与共享 daemon 均为 `0.167.0`；模型沿用本机默认 `auto/gpt-6.1-terra`，没有指定其他模型。运行平台是 Windows，结论不扩展到其他宿主或版本。
- 探测创建的会话明确标为 `[T01 isolated probe]`，工作目录均位于临时目录。已归档测试会话，移除测试自身的待处理队列项；没有归档或删除用户工作会话。

官方依据已实际读取：

- [OpenAI app-server 文档](https://developers.openai.com/codex/app-server/)；本轮跳转到 [app-server 页面](https://learn.chatgpt.com/docs/app-server)。说明初始化、版本对应的 schema、动态工具 `item/tool/call` 流程及工具持久恢复。
- [OpenAI MCP 文档](https://developers.openai.com/codex/mcp/)；本轮跳转到 [MCP 配置页面](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)。说明 stdio/HTTP MCP 与凭证配置；未据此宣称已有宿主的成员身份接入已通过实测。

PowerShell 复现示例，`$t01Codex` 需指向所测版本的原生 `codex.exe`，不使用另一仓库的 CLI：

```powershell
# 只读共享 daemon 元数据；不会启动 daemon 或读取其他会话正文。
uv run --locked --no-sync python scripts/probes/codex_capabilities.py --codex $t01Codex --mode metadata --cwd 'D:\SourceCodes\mywork\agent-relay' --output $t01Metadata

# 独立进程新建测试会话，--run-model 明确允许测试会话的真实入队与推理。
uv run --locked --no-sync python scripts/probes/codex_capabilities.py --codex $t01Codex --mode isolated --run-model --output $t01Evidence

# 只恢复上述证据证明由本探测创建的临时会话，不接受任意工作会话 ID。
uv run --locked --no-sync python scripts/probes/codex_capabilities.py --codex $t01Codex --mode isolated --run-model --resume-evidence $t01Evidence --output $t01ResumeEvidence

# 新建自己的临时会话，验证待处理队列跨进程恢复，不接受外部 thread ID。
uv run --locked --no-sync python scripts/probes/codex_queue_recovery.py --codex $t01Codex --run-model --output $t01QueueRecoveryEvidence
```

独立子进程使用临时的 CLI 配置覆盖禁用其他 MCP、插件、Shell、Hook 和多 Agent 能力；不改用户配置。队列提交本身可能启动推理，因此脚本现将所有入队测试放在 `--run-model` 后；没有该参数只验证会话建立和空查询。初次无工具排队试验也发生在隔离会话，随后已归档，不能将其描述成“完全没有模型启动可能”的试验。

## 能力矩阵

| 能力 | 证据层级与本轮结果 | 使用边界 |
| --- | --- | --- |
| 版本与初始化 | CLI/daemon 版本一致；stdio 与 proxy 均初始化成功，实验能力显式开启 | 上线时要核验实际 CLI 与连接目标版本，不把本机一次结果写成永久最低版本保证 |
| 共享 daemon 发现 | 公开 `thread/list`、精确 cwd 过滤及 `useStateDbOnly` 成功 | 未读用户其他历史；发现元数据不证明可在任意宿主中执行发布工具 |
| 新建持久会话 | `thread/start`、paginated history、临时 cwd 和动态工具注册成功 | 测试的是独立 app-server 管理的会话 |
| 入队凭证 | `thread/queue/add` 返回非空队列项 ID 与匹配的客户端消息标识 | 仅表示入队；初始队列项可很快被消费，不能要求队列列表始终保留它 |
| 忙碌时提交 | 工具请求尚未返回，`thread/read.status.type == active`；连续两个后续入队均确认 | 不等工具结束或模型空闲；并非通过 presence 推测 |
| 上游去重 | 相同输入和 `clientUserMessageId` 得到不同队列项 ID，并同时出现在待处理队列 | 已证明本轮没有该项去重，不可自动重发来找回原结果 |
| 队列查询 | `thread/queue/list` 的 limit/cursor 分页成功，三个待处理测试项分三页返回 | 正向找到精确关联项可成为证据；列表为空不能证明提交失败，也不是队列历史审计 |
| 队列删除 | 成功删除本次测试的三个待处理项 | 只证明待处理项操作；没有验证取消已消费/运行项，不据此新增产品撤回保证 |
| 明确拒绝 | 缺少 `clientUserMessageId` 的请求返回 `-32600` 参数错误 | 只验证入站参数拒绝；未模拟底层接受后响应丢失 |
| 动态工具调用 | `item/tool/call` 含 `threadId/turnId/callId/tool/arguments`；返回 `success/contentItems` 后 turn 正常完成 | JSON-RPC 请求 id 用于响应；持久来源应使用 callId，不能混为一谈 |
| 历史读取 | `thread/items/list` 分页返回 userMessage、dynamicToolCall、final_answer 及 turnId | userMessage.clientId 可匹配本次提交；phase 可辅助诊断，不决定发布资格 |
| 历史时间 | 本轮 item 有 startedAtMs/completedAtMs，且外层条目也有对应可选时间 | schema 允许为空；保留本地观察时间和来源，不保证所有宿主都提供 |
| 进程重载 | 独立 app-server 退出后重新启动，恢复相同测试 thread，不传 dynamicTools 仍再次产生工具回调 | 验证了已有动态工具恢复，没有验证给任意已有会话添加新工具 |
| 待处理队列恢复 | 本轮新增：active 时确认两条待处理项，强制结束自有进程，原 thread resume 后均进入历史，未再次 add 或主动 queue/start | 本机同状态目录、单次进程退出；不保证断电、损坏、历史备份或版本迁移；resume 可能自行继续模型执行 |
| 稳定来源 | 原工具 callId 在重载后的历史中仍存在 | 可用于 Relay 发布去重；不代表上游保证断连后自动重放未完成调用 |
| 已有会话新增动态工具 | 本机 resume/settings schema 均无 dynamicTools 字段 | 当前无已验证的公开直接添加路径；不声称所有 MCP 接入也不可能 |
| MCP 身份绑定 | 官方支持独立进程/HTTP 与凭证；尚未对本项目的成员凭证生命周期实测 | 若选择已有宿主完整接入，需要补这项，不能只传 memberId |
| 多条输入与 turn 关系 | 原试验后续项在运行前删除；本轮恢复试验两条待处理输入进入不同 turn | 仍不证明所有输入必然独占 turn，不自动补引用 |
| 故障恢复 | 重载工具与历史已验证；接受后本地 Relay 落库前崩溃尚未测试 | Relay 目前没有持久提交器，这类故障演练由 T04/T11 完成 |
| 其他宿主 | WSL、远程、Orca、桌面/IDE 独立宿主未验证 | 保留 T12，不把进程存活当可入队/可发布凭据 |

## 选定主路径与实施契约

以下以总方案当前修订为准。Relay 负责消息路由、持久记录及可视化，不负责成员代码执行权限、审批或执行流程。

### 1. 会话与成员绑定

D02 已纠正：Relay 管理持久成员与原会话绑定。发现使用当前 Codex 环境的公开共享 daemon proxy；连接是 WebSocket 字节流，不是独立 stdio JSONL 执行宿主。

#### 1.1 添加成员、创建与原会话连接

本标题保留旧引用锚点；当前动作仅为发现、选择、核验和绑定，不创建或恢复会话。

- GET /room/{roomId}/session 查询全部公开来源、provider 与分页，包含未加载及归档记录；按房间规范目录匹配。已加入会话标 memberId，归档标 archived，不以忙闲过滤。
- Codex cwd 筛选是精确字符串匹配；为保持项目已有 Windows 大小写/分隔符规则，遍历状态库元数据后本地规范匹配，不递归包括子目录。useStateDbOnly=true，不扫描/修复 rollout 历史。
- POST member 仅接受 sessionId/name/topicIds；事务外 thread/read(includeTurns=false) 核验 ID/cwd/provider，短事务复核资源及唯一性后保存 Session/Member，返回 201。
- 重启保留原绑定，不自动 resume 或新建。请求范围只关闭自身 proxy，不关闭共享 daemon 或原宿主；成员名称只保存在 Relay。
- Windows 默认 codex 支持官方 npm 安装：由 Node 直接启动同一安装的 codex.js，不经 shell 或要求手配原生路径。结束连接同时关闭标准输入，等待 proxy 与 Node 正常退出。
- 创建操作接口/operationId/创建状态与独立运行时移除，不保留旧协议兼容。元数据失败为安全 503，不返回部分成功列表，也不触发模型或重试写操作。
- T01 动态工具与重载实测为隔离能力证据；任意已有会话新增 dynamicTools 没有已验证途径。T05 需核验已有会话可用的受控发布入口和稳定来源键，不能为满足旧工具方案改变加入语义。

#### 1.2 任务边界

| 任务 | 当前交付 |
| --- | --- |
| T02 | 房间/话题/成员持久化、真实会话发现/核验与原会话绑定、proxy 连接基础 |
| T04 | Codex queue 调用、真实回执及未知结果记录 |
| T05 | 绑定身份的成员显式发布，复用普通消息路由 |
| T06 | **后置**，当前不增加会话输出扫描或等待，不阻断其他任务 |
| T07 | 查询 Relay 已持久消息；需要的接口按功能设计，查阅记录表达服务本次返回 |
| T09 / T10 | Web / CLI 操作并展示同一份持久记录 |
| T11 | 服务自身启停与诊断；备份/恢复部分后置 |

### 2. Codex queue 入队

1. 先保存目标成员/会话、本次关联标识和 submitting 记录，再调用固定的 thread/queue/add。
2. 核验 queuedSubmission.id 和客户端标识，保存真实回执及本地确认时间，记为 queued。
3. 明确拒绝记为 rejected；请求可能已提交但没有确定结果，记为 unknown。不因为技术超时、无输出或模型忙碌重新 add。
4. 如查询 queue/list，准确命中只能证明其实际可证实的结果；列表暂缺不能证明拒绝。不以读取模型输出作为入队成功前提。

### 3. 成员显式发布

当前发布字段沿用 content、topicIds、mentionedMemberIds 和可选 replyToMessageId。发送者由真实会话绑定取得，统一校验话题/@，并集去重、排除发布成员，实际接收人非空才保存 Message/Delivery。

先保存普通消息和投递，再返回本次发布结果。重复同一来源调用找回已有结果；工具回调发布后不从历史再次导入。普通正文 #/@、turnId 和 final_answer 不构成发布目标。

### 4. 已有消息查询与可视化

Web/CLI 和按需查阅功能读取 Relay 已保存的消息、目标、投递及回执。Relay 自己的 HTTP/工具接口、参数和返回按各功能需要定义，不要求一次冻结完整接口列表、未来 schema 或协议版本体系。

查阅位置只表达服务成功提供的记录，不解释为模型已读。撤回通过宿主 completed/success 历史扫描确认每次查询的要求。不增加收件箱、发件箱或作者自查作为本轮前置；成员发布仍排除自己。

### 5. 当前不做

- 备份/恢复方案及演练；已有探测只保留为事实，不扩大任务。
- 成员执行权限、代码审批、执行策略和安全隔离管理。
- 可选输出观察、普通输出扫描、自动回复关联和后台工具完成核对。

## 产品取舍建议及影响

| 决策 | 本轮建议 | 事实与影响 / 当前状态 |
| --- | --- | --- |
| D01 分发详情 | 显示实际成员、提交状态与对应时间；凭证/异常按需展开 | 没有独立接收/已读依据；具体页面方案仍待接受 |
| D02 首选接入 | **已纠正并接受**：按目录选择已有 Codex 会话，保存持久成员与原绑定 | 管理绑定不等于必须新建；发现/加入归 T02，额外宿主归 T12 |
| D03 自身投递 | **已接受**：成员发布排除自己，含显式 @ 自己；排除后继续实际目标非空校验 | 空目标拒绝整条；保存显式目标，实际 Delivery 不含自己；原型已按此同步，真实成员工具由 T05 实现 |
| D04 零订阅 | 允许仅通过直接 @ 参与的成员零订阅 | 路由已有非空校验，不需在成员表单强制订阅话题；尚未确认 |
| D05 内联创建 | 话题独立提交，取消成员表单不撤销已创建话题 | 保持当前独立资源语义；尚未确认 |
| D07 显式发布 | 显式目标、受控成员身份、来源幂等不变；已有会话入口待 T05 核验 | 不依赖创建时工具注册；不把隔离动态工具探测当成任意已有宿主可用证据 |
| D08 引用关联 | 当前只记录显式 replyToMessageId，不自动从 turn 推断 | 自动关联后置，不阻断消息发布 |
| D09 自动链 | 当前不增加隐式暂停/限额/链深度规则 | 后续如有明确需要再取舍，不作为当前路由前置 |
| D10 管理权限 | 仅指聊天室话题与订阅的管理入口 | 不扩展为成员执行权限、审批或安全隔离 |
| D11 路由来源 | 保存当时命中的话题及显式 @ 来源，详情可展开，不新增接收人预览 | 旧记录不能按当前订阅反推；尚未确认展示程度 |
| D12 运行交付 | 当前只交付 Relay 服务自身启停与诊断，备份/恢复后置 | 撤回执行配置档、请求矩阵及信任边界前置 |

D02、D03 已有明确用户决定，D07 入口按修订 9 在已有会话中重新核验；其余行仍为建议，不因本次接受一并变成已确认。当前 T01 已接受，T02 保留持久资源并修正已有会话加入；其余功能沿完整目标台账推进，条件接入保留。

## 检查与未完成项

- 真实证据断言通过：匹配入队回执、active 状态、重复客户端键生成不同队列项、队列三页、输入 clientId、工具 callId 与同 turn 历史、重载后原 callId 保留、恢复工具调用完成。
- 探测脚本 Ruff、格式与 Mypy 检查通过；help 可执行。再次验证共享元数据 transport 正常关闭；不带 --run-model 的隔离模式没有入队，测试会话正常归档。脚本错误时返回非零退出码，失败原始证据不作为成功用例。
- 协议探测阶段未修改产品 src/Web；用户后续确认 D03 后已同步原型路由和术语，应用检查另见 T01 最新记录。存储/发布/队列故障语义仍须 T02—T11 对应检查，协议探测不代替这些验收。
- 当前 T02 已交付持久存储，并按修订 9 同步真实发现/选择/绑定入口；真实队列提交与正式页面其余能力尚待对应任务实现。普通输出读取/关联、备份恢复已后置；不再以执行策略、全量接口冻结或后台工具核对阻断当前任务。
- T01 已接受；修订 9 的真实检查只读已有会话元数据，成员/房间写入临时 Relay 库，不向原会话发送消息或修改历史。

## T02 产品实现核验（修订 9）

当前检查使用 [只读成员绑定烟测](../../scripts/probes/member_session_smoke.py)，证据见 [现有会话绑定证据](evidence/20261107-t02-existing-session.json)，最终结果见 [T02 交付](../task/20261107-backend-from-web/T02-durable-rooms.md)。已有会话发现和绑定不等于真实 queue 或成员发布入口已验收。

2026-11-07 19:05:29 补测修复默认命令：此前绝对原生路径烟测漏掉 Windows npm codex.cmd 被拒绝的问题。当前证据以默认 `[codex, app-server, proxy]` 重新生成，保留当前源码指纹；真实后端及 Web 代理刷新均为 200，找到 2 条本项目会话，请求结束无残留 proxy。后端 107 项测试及 Mypy/Ruff/格式检查通过。

### 修订 8 历史证据（创建主路径已撤回）

- 原生 Codex 0.167.0：本次仅 thread/start 后立即关闭的测试未形成可恢复的历史，重启 thread/read 返回 not loaded、resume 返回 no rollout。不能只凭 start 返回 ID 宣告持久成员已建立。
- 采用原生 thread/inject_items 写入真实成员身份初始化上下文，再 thread/name/set 设置成员名称；不创建 turn、不触发推理或 queue 提交。初始化成功后才将成员与操作置为 ready。
- [产品烟测证据](evidence/20261107-t02-managed-session.json)确认自有第一进程退出后，第二进程读取元数据并恢复原 ID，队列为空，测试 thread 已归档且自有进程已退出。
- 当时使用 operationId 创建契约；该业务路径已由修订 9 的已有会话选择/绑定取代。旧烟测只保留隔离能力历史，不对应当前产品源码。
