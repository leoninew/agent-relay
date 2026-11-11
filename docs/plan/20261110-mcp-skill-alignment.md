# Plan / 计划：MCP 与 Skill 对齐当前协作业务
最后修改时间: 2026-11-10 23:50:09

## Review status / 审查状态

Accepted

本轮按用户“查看和实现在途任务”的明确要求重新审阅并接受本实施方案。实现状态和验证结论分别记录在下方及同标识验证文档。

## Intent basis / 意图依据

- [意图](../intent/20261110-mcp-skill-alignment.md)：A01–A10。
- 记录基线：`2d5d63158573316d59ce316c9b12ea5ab07101c7`；记录前工作区干净。接手会话应核对实际 HEAD 和新增工作区修改，避免覆盖后续工作。
- 初始授权仅记录任务；用户于 2026-11-10 后续要求查看并实现当前在途任务，据此由本会话接收实施。该授权不继承既往 Git 提交授权。

## Technical decisions / 技术设计与决策

### 1. 复用已有业务边界

- CLI/MCP → `RelayClient` → 现有 HTTP API；不在适配器内重算活动队列或实现清空 SQL。
- 当前队列查询和清空由 `interfaces/http/rooms/routes.py`、`application/rooms/service.py`、`infrastructure/persistence/queries.py` 和 `rooms.py` 提供，保持不变。
- 队列按消息去重；`totalMessages/removedMessages` 都是消息数，不是投递数。活动条件为存在 `deletedAt` 为空且 status 为 pending/submitting/queued 的投递。
- 不传范围参数表示全房间；话题按显式关联、成员按发送者或保存的实际接收人，组合取交集。清空将该消息范围的全部未完成 Agent 投递标记移除，覆盖未加载页。

### 2. 共用客户端、CLI 与 MCP

| 入口 | 请求与参数 | 返回与约束 |
| --- | --- | --- |
| `RelayClient.queue_list` / MCP `queue_list` | GET `/api/room/{id}/queue`；room_id，topic_id/member_id/before_seq/limit 可选 | limit 默认 50、1..200；before_seq >= 1；返回现有队列页 |
| `RelayClient.queue_clear` / MCP `queue_clear` | DELETE `/api/room/{id}/queue`；room_id，topic_id/member_id 可选 | 不接收分页参数；返回 `{removedMessages}` |
| CLI `agent-relay queue list ROOM` | `--topic-id/--member-id/--before-seq/--limit` | 与 MCP 同一请求、结果与范围语义 |
| CLI `agent-relay queue clear ROOM` | `--topic-id/--member-id` | 显式命令发起一次清空，沿用既有删除命令形态 |

- 新工具使用 room_id 与筛选 member_id，不将筛选成员误作调用者身份；不改现有成员专用工具按 threadId 解析身份的逻辑。
- `room_get/message_list` 在现有参数列表末尾增加可选 `keyword`，避免破坏客户端已有位置参数调用。CLI 增加 `--keyword` 并显式传值；字面匹配、空白处理和最大长度 200 沿用 HTTP。
- 修正上述方法和 CLI `--member-id` 帮助，说明发送者或实际接收人；不改变 `member_context` 的订阅与可见范围限制。
- 使用 SDK 支持的 `Annotated`/Pydantic `Field` 在新队列工具与受影响的 room_get/message_list 参数 Schema 中表达 limit、before_seq、keyword 约束。CLI 使用既有 Click 类型约束风格；HTTP 保持最终业务校验。
- 成功/失败沿用当前 `ApiResult`、`RelayClientError` 和 MCP `structuredContent`，不另造结果包裹或扩大到所有工具的输出 Schema 重构。
- `queue_list` 注解：readOnly=true、idempotent=true、destructive=false、openWorld=false。`queue_clear`：readOnly=false、destructive=true、openWorld=false；不承诺可自动重复调用，idempotent=false，因为后续同范围调用可能移除新到消息。
- `_clear` 不属于当前破坏性后缀识别，需显式配置新工具注解。保留 member_context 和 member_sessions 的既有非只读标记。
- HTTP DELETE 的网络失败继续返回 `outcome=unknown`，不自动重试。清空没有 publication_id 找回能力；不能把未知发布找回规则套到清空，也不能凭重查空队列证明某次请求确定执行。

### 3. 历史投递与有效队列

- `message_get/delivery_list/delivery_get` 保留历史原状态、时间、回执和 deletedAt；不更改默认返回范围，也不新增过滤参数。
- 在说明中明确：status 条件筛选的是保存状态，包含已被业务移除的历史事实；有效积压通过 queue_list 查阅。
- 清空不是 Codex 撤回，也不证明任务取消。已入队或进行中的外部提交仍可能到达；不增加删除状态、完成状态或界面标签。

### 4. 投递消息定位

在 `application/delivery/service.py` 现有 `_submit` 文本中使用下列头部，字段全部来自当前持久消息和房间，不接受正文覆盖：

```text
roomId: <work.room_id>
messageId: <work.message.id>
seq: <work.message.seq>
createdAt: <work.message.created_at.isoformat()>
sender: <sender_name>（<sender_id>）

<原消息正文>
```

- createdAt 保留保存时间的时区，不使用提交或接收时刻；对应上下文结果中的同一时间事实。
- 发送者字段名按用户补充统一为 `sender:`，姓名与成员 ID 格式保留；测试和说明使用相同字段名。
- 原 clientMessageId、队列回执、输入匹配、单次首项启动和未知结果不重发规则不变。
- 仅影响后续正常提交生成的文本，不扫描、重写或重新投递既有 Codex 队列。

### 5. Skill 与说明同步

- 只修改 `plugins/agent-relay/skills/agent-relay/SKILL.md` 作为 Skill 源码；不手工修改用户缓存、复制第二份 Skill 或修改通用安装器。
- 工具表加入队列查询/清空及对应 CLI，区分普通成员上下文查阅、房间管理查询和历史投递核对。清空只在用户请求或明确覆盖该操作的任务中执行，不因发现积压而自行清理。
- 沟通条件以交叉修改、接口依赖、阻塞、范围影响或需对方行动为准；独立工作无需逐阶段频道汇报。保留不回应普通确认和避免循环确认的规则。
- 有延迟、冲突或已完成迹象时，使用 messageId 定位原消息，并按需要用 seq/关键词/话题查询后续可见背景；不对每条普通消息强制查询或轮询全部历史。
- 将新增要求作为原目标的补充；只有同一事项的明确后续决定才覆盖旧要求。序号本身不决定指令优先级，其他成员的消息不自动扩大用户授权。
- 交接记录产品位置/改动范围、检查命令与结果、未验证项以及证据所属版本，防止重复运行和复用过时截图。
- 补充三阶段事实、不自动重发、清空边界、全部筛选不是广播、订阅全量替换等规则；保留显式路由、人类成员、publication_id 找回和引用不继承目标。
- README 补充最小 MCP/CLI 使用说明；MCP server instructions 与工具 docstring 保持一致，不复制整份 Skill。

## Implementation steps / 实施步骤

1. 接收：核对授权与实际基线，在本计划的“接收、进展与交付”记录接手事实；完成方案审阅后按用户授权推进。对应 A01–A10。
2. 适配：补 queue_list/queue_clear 客户端、CLI 和 MCP，修正相关成员说明、补 keyword 和参数约束；运行相关适配器检查。对应 A01–A06。
3. 定位：扩展投递头部并校验真实消息字段、单次提交及原回执核验行为；更新既有完整文本断言。对应 A07。
4. 说明：更新唯一 Skill 源码、MCP instructions/docstring 与 README；对照最终工具名、参数和清空语义复核示例。对应 A03、A06、A08–A10。
5. 交付：运行受影响测试与既有质量入口，在本计划记录版本、改动和检查，输出实现摘要；整体 Verification 按后续授权推进。对应 A10。

## Files to change / 修改范围

- `src/agent_relay/interfaces/client.py`：新增队列请求、keyword、参数约束和查询说明。
- `src/agent_relay/interfaces/cli.py`：queue 命令组、keyword 与帮助。
- `src/agent_relay/interfaces/mcp.py`：新工具、Schema、注解与 instructions。
- `src/agent_relay/application/delivery/service.py`：持久消息定位头部。
- `plugins/agent-relay/skills/agent-relay/SKILL.md`、`README.md`：使用与协作规则。
- `tests/integration/test_cli.py`、`tests/integration/test_mcp_server.py`：复用现有 HTTP/TestClient harness 验证适配器，MCP 工具集合从 23 项更新为 25 项。
- `tests/unit/test_delivery_actions.py`、`tests/integration/test_delivery_service.py`、`tests/integration/test_member_publish.py`：新增定位事实检查并更新原完整文本断言；仅按行为覆盖需要修改。
- 本功能的意图、计划、验证记录：接收、变更与证据。历史 T13 和上一轮队列文档属于当时交付，不重写其工具数量或检查结果。
- 不改前端、数据库结构、已有队列业务实现与 `scripts/install.py`。

## Tasks and coordination / 子任务与协调

不拆分独立 task，不建立 DAG、分配编号或执行登记表，也不启动其他会话。本会话按上述步骤串行实施；无交叉工作项无需向聊天室发布认领或进度。

### 接收、进展与交付

- 接收位置：本节。接手会话记录用户实际授权、当前 HEAD/工作区状态、方案审阅结果与实际写入范围。
- 进展位置：本节。只记录关键范围变化、阻塞和影响交付的事实，并同步文档修改时间。
- 交付位置：本节记录版本或可核对 diff、实际文件、必要检查命令/结果、未运行项和剩余风险；整体验证证据写入[验证记录](../verification/20261110-mcp-skill-alignment.md)。
- 接收记录：2026-11-10，用户要求查看并实现当前在途任务；当前 HEAD 与记录基线 `2d5d63158573316d59ce316c9b12ea5ab07101c7` 一致。工作区仅有本任务意图、计划、验证三份未跟踪文档；接收后只在本任务声明的源码、测试与文档范围内修改。已复核 HTTP 队列、查询范围与清空语义均可由现有 API 复用，无新增方案阻塞。
- 当前执行者：本会话；实现：已完成；产品交付：本节当前交付记录；整体 Verification 仍 Draft。

### Current implementation delivery / 当前实施交付

- 2026-11-10：为 `RelayClient`、Click CLI 与 MCP 接入 `queue_list` / `queue_clear`，复用现有 HTTP 队列端点；查询参数增加 HTTP 一致的 `before_seq`、`limit`、`keyword` Schema/CLI 约束。房间消息与普通消息查询增加关键词，并将成员范围说明修正为发送者或已保存的实际接收人。
- MCP 队列清空标记为 destructive、非幂等写入；查询保持只读。历史 `message_get/delivery_list/get` 不过滤 `deletedAt`，文档明确历史 queued 与当前有效队列不同；清空未知结果不自动重试。
- 投递文本头部改为 `roomId/messageId/seq/createdAt/sender`，时间直接采用消息模型的 JSON 序列化值，与查询返回的 `createdAt` 保持一致；正文、回执关联、单次入队及原会话接收核验保持不变。
- 更新唯一 Skill 源码及 README：明确沟通触发条件、延迟/冲突时的按需查阅、清空和筛选范围、队列状态与业务完成的区别、订阅全量替换及交接证据要求。
- 修改文件限于计划范围内的共用客户端、CLI、MCP、投递服务、README、Skill 源码及相邻测试。未改 HTTP/数据库/前端、未安装插件、未操作真实房间或服务、未修改 Git index 或提交。

## Verification plan / 检查与验证安排

| 验收 | 必要检查与证据 |
| --- | --- |
| A01、A03 | CLI/MCP 请求参数与现有 HTTP 结果一致；话题/发送者/实际接收人/组合范围；seq 降序与 before_seq 翻页；totalMessages 不受当前页影响 |
| A02、A03 | 范围清空覆盖未加载页；同一消息多个接收人时全部未完成记录移除；原消息、received、历史时间/回执保留；FakeQueueDriver 无清空引起的外部调用 |
| A04 | 相关成员同时命中发送和接收；关键词与话题/成员组合；保留客户端旧位置参数；member_context 可见范围不变 |
| A05 | 工具发现为 25 项；新工具及受影响参数 Schema 边界、CLI 参数范围和破坏性注解；结果/错误包裹不变；未知清空只发起一次请求 |
| A06 | 已移除 queued 历史投递仍可按原契约查到且携带 deletedAt；不出现在有效队列；不产生新状态 |
| A07 | 假驱动收到的 messageId/seq/createdAt 与保存消息一致；头部字段为 sender，身份和正文保留；原回执/clientMessageId 核验与不重发回归 |
| A08–A10 | 人工对照 Skill、MCP Schema/docstring、CLI 帮助和 README；确认沟通、过时消息、清空、订阅和全部筛选规则一致，只有一份 Skill 源码 |

建议使用仓库现有入口，按受影响范围先窄后宽：

```bash
uv run --locked pytest tests/unit/test_delivery_actions.py tests/integration/test_cli.py tests/integration/test_mcp_server.py tests/integration/test_delivery_service.py -q
uv run --locked pytest tests/unit -q
uv run --locked mypy src tests
uv run --locked ruff check .
uv run --locked ruff format --check .
git diff --check
```

- `make test` 仍仅为单元测试入口，不恢复集成测试 Make target；显式选择现有 integration 文件是本次适配器开发检查，不改变默认测试组织。
- 环境具备 Make/Bash 时可运行 `make check` 使用既有全仓入口；若仅运行底层命令，应按实际记录，不声称执行了 make。纯后端与 Skill 修改无需重复无关前端检查。
- 自动化使用临时数据库和 fake 驱动，不启动/停止/重启用户开发服务器，不清空真实房间、不向真实会话投递或自动安装插件。本任务不依赖页面复测；若后续确需页面检查，沿用用户要求的 Jev 已有 tab。
- 本轮用户授权实现及必要开发检查；检查结果写入同标识验证记录。独立整体 Verification、插件安装验证和真实环境操作仍不在授权范围。

## Risks and recovery / 风险与恢复

- 清空是当前动态消息范围的一次操作；结果未知时不能通过换请求或再次清空“确认”，避免误清理新到消息。
- 文本头部变化需要同步既有精确断言；不能放宽为仅检查正文来隐藏消息定位错误。
- 接手时若工作区已被其他会话修改，先核对实际交叉范围，按用户约定仅在有交叉影响时协调，不覆盖未归属修改。
- 无数据库迁移；恢复由后续执行者按用户授权还原本功能适配器、投递文本和说明即可，不撤销已发出的外部输入。本文不授权 Git reset、revert 或提交。

## User review notes / 用户审查记录

- 2026-11-10：按用户“记录任务，我会交由其他会话处理”创建本计划；已核对现有接口、客户端、CLI、MCP、Skill、投递实现与相邻测试。
- 初始接收时方案修订 2 尚待执行会话审阅；该状态已由 2026-11-10 本会话接收、复核并接受实施所取代。整体 Verification 仍单独保持 Draft。
- 2026-11-10 23:20：修订 2 按用户补充将计划中的发送者字段统一为 `sender:`，同步 A07 检查要求；任务范围与执行安排不变。
- 2026-11-10：按用户“查看和实现在途任务”接收本任务，复核后接受实施方案并完成产品修改；准确检查命令、结果和未运行项见验证记录。
- 2026-11-11：按用户要求，README 保持简洁的开发说明，具体协作工具用法留在 Skill。本次仅暂存原任务范围内的 Skill/MCP 对齐；Codex 等待项清理和正在运行轮次的取消留待后续。
