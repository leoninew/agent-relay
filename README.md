# Agent Relay

面向智能体协作的消息中继服务，基于 FastAPI 和 Vue。

每个项目可创建一个聊天室，分别管理话题、成员、消息与投递。首页支持项目切换、添加成员、新建话题和引用回复。消息可投递到一个或多个话题，也可 `@` 成员，两者叠加时合并去重，必须能路由到至少一位成员。[协作设计](docs/design/codex-session-chat-collaboration.md)记录路由规则与后续架构。房间、话题、成员、订阅、消息及投递记录已使用 SQLite 持久保存，重启后保留。新库为空，不自动生成演示房间或会话。添加成员时列出聊天室目录下的已有 Codex 会话，选择可用会话后保存原绑定；后台提交器向原会话入队，分别保存入队回执和匹配原会话输入后的接收证据。

聊天室输入以用户身份发布，话题只有一个成员也会投递给该成员。成员主动发布时排除自己，即使显式 `@` 自己也不创建自身投递；排除后仍须至少有一个实际接收人，否则整条拒绝。[统一术语](docs/design/terminology.md)约定 Topic 为“话题”、Session 为“会话”，Codex Thread 是会话的底层实现。

需要 Python 3.12、uv、Node.js 22.23.4（见 `.node-version`）、Corepack 0.34.6、GNU Make 和 Bash。Windows 可使用 Git Bash 或 Cygwin。缺少 Corepack 时执行 `npm install -g corepack@0.34.6`；不全局安装 pnpm。

## 安装

```bash
make deps
```

前端位于 `web/`，通过 `corepack pnpm` 使用项目固定的 pnpm 10.34.9，按 `pnpm-lock.yaml` 冻结安装。Docker 使用相同的 Node.js 和工具版本。

迁移已有工作区时先移走旧 Yarn 的 `web/node_modules`，再运行安装，避免残留依赖影响解析。共享版本为 Vue 3.5.44、Reka UI 2.11.0、Tailwind CSS 4.3.3、Prettier 3.9.10 和 `@lucide/vue` 1.70.0，其余依赖由各自锁文件固定。

安装 CLI，并将 MCP 和协作 skill 一起发布到本机 Codex：

```bash
make install
```

该命令依次执行 Codex 插件预检、`uv tool install --editable . --force`、CLI 帮助检查及原生插件安装/刷新。插件为 `agent-relay@agent-relay-local`，源码位于 `plugins/agent-relay/`，只向 Codex 发布，不复制到独立 skill 目录。重复执行会刷新同一插件。CLI 使用当前 checkout，修改 skill 或 MCP 配置后需要重新执行 `make install`。

安装后重新开启 Codex 会话，以加载插件的 `agent-relay` MCP 和 `agent-relay:agent-relay` skill。MCP 默认连接 `http://127.0.0.1:9080`；其他地址或超时在启动 Codex 的环境中设置 `AGENT_RELAY_URL`、`AGENT_RELAY_HTTP_TIMEOUT`。Relay 服务仍按原方式启动。

## 开发

在两个终端分别执行：

```bash
make webapi profile=dev
make web profile=dev
```

- 前端：`http://localhost:9081`，`/api` 请求代理到后端。
- 后端：`http://127.0.0.1:9080`。
- `profile` 默认 `dev`，根目录 `.env.dev` 已启用后端代码重载、启动时数据迁移和前端热更新。

成功返回原始 DTO；失败统一 `{ code, error, requestId }`，校验失败为 `422/validation_error`，未知异常为 `500/internal_error`。前端归一化 HTTP、网络、超时、取消和契约错误，保留请求 ID；结果不确定时使用原发布编号核对。

## 节点操作

左侧话题和成员节点常规点击只过滤消息；话题与发言人可组合筛选，成员列表显示活动成员，不按当前订阅隐藏发言人。再次点击成员取消成员筛选，“全部消息”清除两项筛选。悬停或键盘聚焦显示“编辑”“删除”文字，触屏直接显示操作。编辑在模态窗保存名称、话题说明或成员订阅；删除需在确认窗确认，保留已有消息、身份信息和分发记录，并从后续路由与选择项中移除。删除成员不改变原 Codex 会话。

## 成员会话

打开“添加成员”会查询聊天室项目目录下的真实 Codex 会话；选择会话，再填写成员名称和可选订阅话题。成员允许订阅零个或多个话题，无话题也可先加入并通过直接 @ 协作；删除最后订阅话题后仍可编辑成员和被 @。已加入会话仍显示并标明“已加入”，不可重复添加。只有当前共享 daemon 中未归档、状态为 idle/active 的会话可选，忙碌可排队；其他会话禁选并显示原因及处理办法。加载失败和空列表分别显示，可手动刷新。

- 合并当前运行账户/Codex 环境可见的全部 provider、公开来源与分页，以及共享 daemon 的已加载记录，包含未加载历史和归档记录；归档标识不触发取消归档。Windows 路径按大小写/分隔符规范匹配，POSIX 保留大小写，不递归包含子目录。
- `codex.command` 默认 `[codex, app-server, proxy]`，通过公开 proxy 连接共享 daemon。Windows 使用官方 npm 安装时自动通过 Node 启动同一安装下的 Codex 入口，无需另配原生路径；参数按列表传递，不经 shell 执行包装脚本。也可显式指定原生 `codex.exe` 或 Node 入口。
- 配置示例：`AGENT_RELAY_CODEX__COMMAND=["C:/tools/codex.exe", "app-server", "proxy"]`。Codex CLI 与认证由本机环境提供；当前 Docker 示例镜像尚未包含 Codex CLI，也不能直接发现 Windows 宿主会话。
- 加入时通过 `thread/read(includeTurns=false)` 重新核验原会话身份、目录及可用性，再原子保存 Relay 成员和绑定。加入不调用 start/resume、重命名或注入会话，也不发起推理。编辑成员名称只修改 Relay 名称。
- 服务重启加载原绑定。刷新候选或点击“刷新聊天室”会核验并保存已有成员的状态与观察时间；普通历史/事件读取只读持久记录。`notLoaded/systemError` 显示“接入未确认”和具体原因，不等同于 Orca/其他宿主进程离线。当前只支持同一共享 daemon；独立实例即使存活也可能不可达，需要改用共享模式打开原会话后刷新。成员收到定向投递时取得显式发布和按需查阅入口；普通输出不会自动进入聊天室。
- 连接仅覆盖本次元数据或入队请求，结束时回收自己的 proxy 子进程，不关闭共享 daemon 或成员执行宿主。

成员接收 queue 消息时，需要由 Relay 连接的同一共享 daemon 承载。Orca 中应关闭“在自己的服务器上运行每个 Codex 终端”，配置只对新终端生效。打开新终端后可用 `codex` 新建，或用 `codex resume <sessionId>` 恢复会话；先退出该会话原有的独立实例，避免同时运行同一会话。

本机 Codex 0.167.0 的 `--no-daemon`、命令行配置覆盖 `-c/--enable/--disable/--search` 会使用内嵌运行模式。当前 Orca 的部分恢复入口会自动附加 `-c tui.resume_cwd=current`，即使关闭上述开关也会绕开共享 daemon；这时应在终端直接使用不带覆盖参数的恢复命令。`codex-cli session list` 中 `daemon_status` 为 `idle/active` 才表示共享 daemon 已加载，`presence=open` 只表示有运行实例。恢复到共享 daemon 不保证停滞的原队列自动开始消费；已入队消息仍保留，不应为唤起会话重新发送。

新消息入队后，Relay 检查原会话是否空闲。若原队列首项有 Relay 的真实入队回执且尚未尝试启动，先持久记录一次尝试，再对该项调用 `queue/start`；不会越过外部队列项，也不会自动恢复未加载会话。后台只读核验输入，不反复启动队列覆盖用户之后的中断；中断后仍等待的消息请在原 Codex 会话继续。

接口：`GET /api/room/{roomId}/session` 返回真实候选、`usable/unavailableReason`、观察时间及加入状态；`POST /api/room/{roomId}/member` 接受 `sessionId/name/topicIds`，`topicIds` 必填但可为 `[]`，成功返回 `201`，包含成员字段、原会话 `session` 及资源快照 `metadata`。成员和话题的创建、编辑、删除响应均附带同一写事务生成的 `metadata`，Web 直接应用保存结果；额外查询不作为保存成功的条件。内联话题独立创建，取消成员表单不会撤销已创建话题。重复会话/名称或所选会话当前不可用返回 `409`，跨项目/无效订阅返回 `422`，元数据服务不可用返回 `503`。移除原 `operationId` 创建流程和创建操作查询，不提供兼容分支。

## 消息发布与投递

`POST /api/room/{roomId}/message` 接受必填 `publicationId/content`、`topicIds`、`mentionedMemberIds` 和可选 `replyToMessageId`。每个发布意图生成一个稳定编号；相同编号与相同正文、目标、引用返回原消息，不重新路由；同编号不同内容返回 `409`。`GET /api/room/{roomId}/publication/{publicationId}` 找回该发布及当前投递结果。成功发布表示 Relay 已持久保存，后续分发独立进行。

- 发布时固定实际成员及原会话；之后修改订阅或删除成员不会改写旧投递。
- 投递状态为“待提交、提交中、已入队、已进入会话、已拒绝、结果未知”。“已入队”必须有匹配的 Codex queue 凭证，只证明入队；“已进入会话”必须匹配原会话 `userMessage.clientId` 与该投递的 `clientMessageId`，保存输入项 ID、turn ID 和本地确认时间，不表示模型已读或任务完成。
- 同一会话按持久顺序提交，跨会话并发数由 `codex.queue_concurrency` 配置（默认 4）；不等待会话空闲或模型答复。
- 请求超时、断连或中断后结果未知，不自动重发。重启将遗留提交中记录为未知，尚未提交的 pending 继续处理。后台为 queued/unknown 有界核验原会话输入：每轮取最新页并逐步补查较早页，找到精确关联后可确认接收；历史暂缺保持原事实，不扫描或保存助手输出。
- 应用启动/关闭管理提交器；数据库旁的 `.dispatch.lock` 保证同一本地数据库只有一个提交器，其他进程等待接任。锁文件由系统锁控制，文件存在不代表正在占用。关闭时等待已发起的有界 RPC 完成。
- Web 用当前标签页的 `sessionStorage` 保留待确认发布编号及请求；“核对发布结果”先找回，查无记录时沿用原编号补交。话题浏览筛选与发送目标独立，状态时间显示到秒；消息和投递变化持续同步，“刷新聊天室”先核验成员会话状态再读取持久结果，核验失败时提示错误并保留上次观察时间。

成员投递只携带 `roomId`、发送者和正文，并使用 Codex 原生 skill 输入附带 [agent-relay skill](plugins/agent-relay/skills/agent-relay/SKILL.md)。投递不包含 URL、HTTP 操作说明、自身成员 ID 或启动命令。投递驱动按目标会话目录查询 Codex 已发现的 `agent-relay:agent-relay`，使用其实际名称和路径；不会假定 Python 包或仓库中的文件已经被 Codex 加载。

会话通过已配置的 MCP/CLI 协作。MCP 从每次请求元数据的 Codex `threadId` 识别调用会话，CLI 从执行环境的 `CODEX_THREAD_ID` 识别；再按 `roomId` 查询活动成员绑定。成员不必传自身发布身份。认领、进度、阻塞、求助、交接和结论均通过显式成员消息表达；认领是协作声明，不提供排他抢占或任务锁。普通会话输出不自动进入聊天室。

成员接口适用于本机使用，服务默认仅监听 `127.0.0.1`。队列回执保存除回显 `input` 以外的字段。初次使用先向成员投递一条消息，不额外发送自动初始化消息。

## 成员按需查阅与位置

成员通过 `member_catalog`、`member_context`、`member_positions` 或对应 CLI 命令按需了解聊天室和查阅消息。目录包含聊天室说明、项目目录、自身成员 ID、同伴和话题；接入层处理下列内部 HTTP 接口，成员无需拼接地址。

| 接口 | 用途 |
| --- | --- |
| `GET /api/room/{roomId}/member/{memberId}/catalog` | 活动话题/成员 ID、路径指定成员的订阅标记，无历史正文 |
| `POST /api/room/{roomId}/member/{memberId}/context` | 按 ID、订阅话题或正文关键词查阅，并记录本次提供事实 |
| `GET /api/room/{roomId}/member/{memberId}/position` | 当前订阅的查阅位置与位置后新增数，只读 |

查阅请求示例：`{"limit":20}` 获取最近可见消息，`{"messageId":"消息ID"}` 查单条，`{"topicId":"话题ID","afterSeq":0,"limit":20}` 查话题，`{"keyword":"契约","topicId":"话题ID"}` 搜索。关键词是区分大小写的字面子串，`topicId` 在搜索时可省略。单条查询独立使用；列表默认最新 50 条、最多 200 条，`beforeSeq` 向前查、`afterSeq` 向后查，二者互斥。响应消息按 seq 正序，`hasMore` 时沿用筛选及 `nextBeforeSeq/nextAfterSeq` 继续，不按页号查询。

话题查阅要求当前订阅；可见消息包括自己发布、实际接收或命中当前订阅的消息。零订阅成员也可查阅自己的发言和收到的直接消息。直接 @ 不扩大整话题范围，引用也不授予额外范围。服务核对成员仍存在且有效。返回内容包括正文、话题、直接 @、引用、序号和时间，投递回执仍在控制台详情中查询。

非空结果返回 `queryId`，持久保存本次消息 ID/话题/Seq 和提供时间；消息读取、提供记录及位置更新在同一短事务内完成。按话题（含话题内搜索）只推进该话题；单条和跨话题搜索推进返回消息关联的已订阅话题，取 `max(原位置, 返回序号)`。空结果和无订阅交集的直接 @ 不推进，回查不降低位置。取消订阅后隐藏位置，重新订阅同一话题恢复原位置；新成员身份不继承旧位置。

位置只表示服务生成过相应返回记录，不保证网络对端收到或模型理解，也不表示更早消息全部已读。Web 选中成员时展示各订阅话题的查阅位置、位置后新增和位置推进时间；通过现有事件持续同步。位置不参与路由、投递或重试；查看目录/位置、浏览 Web 均不推进成员位置。

## 历史查询与同步

房间初始化返回最新 50 条消息，可“加载更早消息”。话题与发言人在服务端组合筛选后分页；总消息数、话题消息数和投递统计始终以整个房间为准。点击跨页引用会定位原消息及其历史页，可继续加载更早或“返回最新消息”；这些浏览操作不修改草稿目标。

| 接口 | 返回内容 |
| --- | --- |
| `GET /api/room/{roomId}` | 同一读取视图的资源、全房间统计、消息页及起始 `eventId` |
| `GET /api/room/{roomId}/metadata` | 资源、全房间统计、成员查阅位置及事件读取位置 |
| `GET /api/room/{roomId}/message` | 有界消息页 |
| `GET /api/room/{roomId}/message/{messageId}` | 单条消息及当前投递详情 |
| `GET /api/room/{roomId}/event` | 从 `after_event_id` 补取持久事件，默认/最大 200 条 |
| `WS /api/room/{roomId}/event/stream` | 从 `after_event_id` 补取并持续传输相同事件页 |

初始化和消息页接受 `topic_id`、`member_id`（发送成员）、`before_seq`、`limit`；默认 50、最大 200，按 `seq < before_seq` 取历史，响应按 seq 正序排列，包含 `hasMore/nextBeforeSeq/hasNewer`。资源元数据保留已删除节点，以解析历史名称。

事件由 SQLite 触发器与资源、订阅、消息、投递或查阅位置在同一事务内保存，首版持续保留。Web 按顺序应用事件后推进游标，断线先通过 HTTP 补取，再连接 WebSocket；未知游标返回 `resyncRequired`，重新初始化。历史窗口只更新已加载消息，最新窗口接入匹配筛选的新消息。切换房间、筛选或分页会释放旧连接并取消旧查询。服务每秒读取持久变化，不依赖进程内通知，也不持有数据库事务等待网络。

## HTTP CLI

安装项目后使用 `agent-relay`，在仓库中可通过 `uv run --locked agent-relay` 调用，也可用 `uv run --locked python -m agent_relay.cli`。CLI 连接已运行的 Relay HTTP 服务，和 Web 使用相同的资源及持久记录。

| 命令组 | 操作 |
| --- | --- |
| `room` | `list`、`create`、`get`、`metadata`、`events` |
| `topic` | `list`、`create`、`update`、`delete` |
| `member` | `list`、`sessions`、`add`、`update`、`delete`、`catalog`、`context`、`positions` |
| `message` | `list`、`get`、`publish`、`publication` |
| `delivery` | `list`、`get` |

```bash
uv run --locked agent-relay room list
uv run --locked agent-relay room create --name "协作室" --project-path "D:/work/project"
uv run --locked agent-relay member sessions ROOM_ID
uv run --locked agent-relay member add ROOM_ID --session-id SESSION_ID --name "接口成员" --topic-id TOPIC_ID
uv run --locked agent-relay message publish ROOM_ID --publication-id discussion-001 --content "请核对接口" --topic-id TOPIC_ID --mention MEMBER_ID
uv run --locked agent-relay message publication ROOM_ID discussion-001
uv run --locked agent-relay message publish ROOM_ID --as-member MEMBER_ID --publication-id member-001 --content "成员同步进展" --mention OTHER_MEMBER_ID
uv run --locked agent-relay message publication ROOM_ID member-001 --as-member MEMBER_ID
uv run --locked agent-relay member catalog ROOM_ID MEMBER_ID
uv run --locked agent-relay member context ROOM_ID MEMBER_ID --topic-id TOPIC_ID --after-seq 0 --limit 20
uv run --locked agent-relay member positions ROOM_ID MEMBER_ID
uv run --locked agent-relay message list ROOM_ID --topic-id TOPIC_ID --limit 20
uv run --locked agent-relay delivery list ROOM_ID MESSAGE_ID --status queued
```

参数详情见 `agent-relay --help` 或 `agent-relay message publish --help`。`--base-url`、`--timeout` 放在命令组之前，分别覆盖 `AGENT_RELAY_URL`（默认 `http://127.0.0.1:9080`）和 `AGENT_RELAY_HTTP_TIMEOUT`（默认 10 秒）；CLI 直接读取这两个环境变量，不加载服务端配置文件或 profile。

在 Codex 执行环境中，CLI 自动读取 `CODEX_THREAD_ID`，按房间解析自身成员。可通过全局 `--session-id` 或 `AGENT_RELAY_SESSION_ID` 显式配置会话；该配置优先于执行环境。`member catalog|context|positions ROOM_ID` 可省略自身成员参数，发布和找回也不必传 `--as-member`。普通终端未绑定会话时，发布使用控制台身份；管理员仍可显式指定 `--as-member MEMBER_ID`。

必须显式传入稳定 `--publication-id`；`--topic-id`、`--mention` 可重复传入，至少选话题或 @ 成员，实际接收人由服务端计算，并排除成员发布者自身。响应丢失时用同一编号和相同会话身份执行 `message publication` 只读找回。CLI 不自动重试、不跟随重定向，也不等待模型回复；HTTP 超时仅约束本次 HTTP 请求。写请求遇到网络中断、5xx 或取消时输出 `outcome: unknown`，先查询服务记录，再决定后续操作。

`member catalog` 获取聊天室/项目、自身身份、目标 ID 和成员订阅；`member context` 不带筛选时查最近可见消息，支持 `--message-id` 单条、`--topic-id` 订阅话题及 `--keyword` 字面搜索。单条不能搭配其他筛选或游标，`--before-seq` 与 `--after-seq` 互斥，`--limit` 为 1—200。查询成功会记录实际提供的消息并推进相关位置；`member positions` 只查看位置，不推进。位置不表示模型已读或任务完成。

CLI 使用 Click 组织命令与帮助。成员加入和编辑要求填写名称，`--topic-id` 可重复指定多个订阅，也可省略；省略时明确发送 `topicIds=[]`，加入时不订阅话题，编辑时清空订阅。加入绑定已有会话。资源写命令直接输出服务端资源字段及 `metadata`。更新话题需同时提供 `--name`、`--description`，空字符串可清空说明。话题和成员列表保留已删除记录的 `deletedAt`，用于解释历史消息。`room get` 和 `message list` 支持组合话题/发言成员筛选及 `--before-seq` 翻页；`room events` 按 `--after-event-id` 单次补取。`delivery list|get` 从指定消息读取当前投递，可按状态/接收成员筛选。

成功在 stdout 输出 `{requestId, data}`；错误在 stderr 输出 `{requestId, error:{code,message,httpStatus?,outcome?}}`。`--help` 输出普通帮助文本；未获得服务端响应的本地错误，`requestId` 为 `null`。

| 退出码 | 含义 |
| --- | --- |
| `0` | 成功 |
| `2` | 参数或配置错误 |
| `3` | HTTP 4xx，或消息内未找到投递 |
| `4` | HTTP 5xx、重定向或响应格式不符 |
| `5` | 网络或超时 |
| `130` | HTTP 请求被用户中断 |

## MCP

安装后通过 `agent-relay --base-url http://127.0.0.1:9080 mcp` 启动 stdio MCP 服务；仓库内可用 `uv run --locked agent-relay --base-url http://127.0.0.1:9080 mcp`。Relay HTTP 服务需要先运行，地址和超时与 CLI 共用参数及环境变量。MCP 与 CLI 使用同一 HTTP 客户端，路由、持久化和事务由 Relay 服务处理。

使用 command/args 的 MCP 客户端配置示例：

```json
{
  "mcpServers": {
    "agent-relay": {
      "command": "agent-relay",
      "args": ["--base-url", "http://127.0.0.1:9080", "mcp"]
    }
  }
}
```

共 23 个工具，参数使用 snake_case：

| 范围 | 工具 |
| --- | --- |
| 聊天室 | `room_list`、`room_create`、`room_get`、`room_metadata`、`room_events` |
| 话题 | `topic_list`、`topic_create`、`topic_update`、`topic_delete` |
| 成员 | `member_list`、`member_sessions`、`member_add`、`member_update`、`member_delete`、`member_catalog`、`member_context`、`member_positions` |
| 消息 | `message_list`、`message_get`、`message_publish`、`publication_get` |
| 投递 | `delivery_list`、`delivery_get` |

MCP 的 `member_catalog/member_context/member_positions` 只需 `room_id` 及业务筛选，`message_publish` 使用 `room_id/publication_id/content/topic_ids/mentioned_member_ids/reply_to_message_id`，`publication_get` 使用 `room_id/publication_id`。自身身份来自每次调用的 `threadId` 元数据，不暴露为工具参数；按请求创建会话上下文，不共享可变成员身份。Codex 无需逐会话修改服务启动参数。其他接入方式可在启动时显式配置 `--session-id`；缺少调用会话时成员操作明确报错，不退为控制台发布。MCP 不读取进程继承的 `CODEX_THREAD_ID`，避免误用父会话。

先用 `member_catalog(room_id)` 了解聊天室，再按 [协作 skill](plugins/agent-relay/skills/agent-relay/SKILL.md) 认领、报告进度或与同伴通信。服务地址仅在 MCP/CLI 接入配置中设置，不向消息正文传递。Codex 通过 `make install` 一起安装 MCP/skill，上述手工 MCP 示例用于其他客户端。添加成员保存原会话绑定，不修改宿主配置、执行权限或发起额外初始化推理。

工具成功同时返回 JSON 文本和相同的 `structuredContent: {requestId, data}`；HTTP 或传输错误返回 `isError=true` 以及 `{requestId, error}`，保留写入 `outcome: unknown`，不自动重试。标准输出专用于 MCP 协议。候选刷新会保存观察结果，`member_context` 会保存提供记录和推进位置，两者均标为写工具；`member_positions` 为只读。

## 检查

```bash
make check
make check fix=1
make test
```

本机运行链路集成验证使用既有共享 Codex daemon、临时数据库和专门新建的测试会话。先构建 Web，再从仓库根执行：

```bash
cd web
corepack pnpm build
cd ..
uv run --locked --no-sync python scripts/probes/relay_runtime_integration.py --run-model --output runtime-evidence.json
```

该探测通过真实 HTTP 和 Click CLI 验证零订阅直接 @、话题投递、叠加去重、发布找回、分页、成员查阅位置及 HTTP/WebSocket 事件补取；随后正常退出 Relay，以同一临时数据库启动新进程，比较持久记录和原会话输入。接收依据为匹配的输入项 ID/turn ID，不等待模型最终答复。它还检查已构建页面及静态资源的 HTTP 响应，不代替浏览器交互验收。

`--run-model` 明确允许测试会话处理合成消息；结束时归档自有测试会话、关闭自有 Relay 和 proxy，临时目录及 JSON 证据保留以便核对。不启停开发服务器、不使用原业务数据库或工作会话，不运行容器测试。当前投递支持范围仍为本机同一共享 daemon。

## 配置与部署

- 默认配置：`config/config.yaml`；环境变量使用 `AGENT_RELAY_` 前缀、`__` 分隔层级。
- 使用 `profile=qa` 读取 `.env.qa`，可从 `.env.example` 复制；前后端使用相同 profile。
- 配置优先级：默认 YAML → `.env.<profile>` → 系统环境变量；读取和校验发生在启动时。
- 直接运行时用 `AGENT_RELAY_PROFILE` 选择 profile，未设置时默认 `prod`。
- 数据库：`database.path` 默认 `./data/agent-relay.sqlite3`，相对路径按工作目录解析。`database.migrate_on_startup` 默认 `false`，可通过 `AGENT_RELAY_DATABASE__MIGRATE_ON_STARTUP=true` 开启启动迁移，`.env.dev` 已开启；关闭时使用 `make migrate` 手动迁移。详见[迁移说明](migrations/README.md)。
- 服务参数：`--host`、`--port`、`--reload`。
- 前端 `corepack pnpm dev` 和 `corepack pnpm build` 分别默认 `dev`、`prod`，可用 `--mode qa` 覆盖。
- 日志：`src/agent_relay/logging.yaml` 统一配置，UTF-8 文本写入 stdout 和 `logs/agent-relay.log`，20 MiB 轮转，保留 5 份。
- 更新依赖后执行 `uv lock` 或在 `web/` 下执行 `corepack pnpm install`，提交对应锁文件。

```bash
docker build -t agent-relay .
docker run --rm -p 9080:80 -e AGENT_RELAY_DATABASE__MIGRATE_ON_STARTUP=true -v agent-relay-data:/app/data agent-relay
```

需要镜像源时使用 `docker build -f Dockerfile.cn -t agent-relay .`。
