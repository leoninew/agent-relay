# Intent / 意图：消息图片输入与展示

最后修改时间: 2026-11-13 14:32:00

## Review status / 审查状态

Draft

当前执行边界：用户 `0162` 已授权尝试 Tiptap + Mention，支持消息框中的 Skill 与图片粘贴、拖入。[Tiptap 消息编辑器计划](../plan/20261113-tiptap-message-editor.md) 将首次实施收敛为编辑器替换，以及 Web/WebView 图片上传、API 本地保存和 Markdown 展示。本文的 MCP/CLI 上传、Codex 原生图片投递及历史看图仍保留为后续需求，不随本次编辑器试切启动；不能把当前实施结果报告为整条图片链路已完成。

以下是此前完整需求评估。用户消息 `room-a2493e542ba3-msg-0149` 要求将 Tagify 实现移交给高级开发，架构师开始评估图片输入和展示。消息 `0154` 进一步确定方向：支持粘贴、拖入图片，MCP/CLI 上传返回图片标识，图片存储在 API 本地，消息中通过 Markdown 渲染，并评估 Tagify 影响。后文 Tagify 事件接管和末尾追加均为旧方案参考；当前采用 Tiptap 事务与原位上传锚点，不沿用旧字符下标。

## Background / 背景

协作讨论经常需要发送截图、界面参考和错误现场。用户需要在发送前确认所选图片，消息发布后能在房间中查看图片，被提及的 Agent 也应能读取实际图像。

目前消息以 `content: string` 和 `capabilities` 表示文字与 Skill/MCP 引用；正在实施的 Tagify 只改变文字与 Skill 的编辑显示。本次收敛为：图片文件由 API 管理，正文以标准 Markdown 图片语法引用文件。正文继续负责图片的位置、顺序和重复出现，不另建一份附件数组作为发布输入。

这覆盖用户在 Web/WebView 输入图片，以及 Agent 通过 MCP/CLI 上传图片后发布给用户两条链路；Agent 回传图片已属于用户确定的范围。

## Repository findings / 仓库现状

| 环节       | 当前事实                                                                          | 需要补齐的能力                                                                       |
| ---------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| 输入       | RoomComposer 接入中的 SkillMessageEditor 自有 paste/drop capture 处理，会消费事件 | 在真实祖先 DOM 更早识别图片文件，交给上传，再通过编辑器事务插入 Markdown             |
| 展示       | messageMarkdown 使用 markdown-it；标准相对 URL 的图片语法能渲染 img               | 受管图片 URL、展示尺寸、加载失败反馈和点击查看大图                                   |
| 请求与存储 | CreateMessage、Message、MessageRecord 保存字符串 content                          | 新建图片资源的元数据和文件保存；消息仍保存相同 content，无须新增 attachmentIds       |
| 正文校验   | 前后端要求去掉 Skill 后仍有非空正文，文字上限 6000                                | 图片 Markdown 本身为非空正文，可沿用规则；新增受管图片的 ID、房间及可用性校验        |
| 草稿和发布 | 草稿保存 content；待确认请求和发布重放已保存、比较原正文                          | 成功上传后的 Markdown 自动随草稿恢复；上传中状态由输入层处理，不能发布尚未插入的图片 |
| CLI/MCP    | RelayClient.request 只编码 JSON；MCP 的普通调用返回 JSON 元数据                   | 新增文件上传能力，共用 API，返回稳定标识、URL 和可直接发布的 Markdown                |
| 投递       | QueueRequest 只有 text、project_path、capabilities                                | 从有效图片 Markdown 解析本房间图片，提供给 queue/steer 的原生图片输入                |
| 历史上下文 | member_context 已返回完整 content                                                 | Markdown 中已携带图片标识和读取 URL；另提供按 ID 查询或读取的方式即可                |
| 文件读取   | apiClient 强制 JSON 成功响应契约                                                  | 上传响应继续返回 JSON；img.src 直接读取图片 API，不能经 JSON 客户端解码图片二进制    |
| 部署       | Relay 与 Codex 使用本机共享 daemon；桌面数据根目录为用户数据目录                  | 图片放 API 的持久数据目录，独立于 web/dist；开发和桌面读取同一 API 路由              |

依据文件：`web/src/domains/room/RoomComposer.vue`、`SkillMessageEditor.vue`、`skillEditorModel.ts`、`messageMarkdown.ts`、`MessageTimeline.vue`、`RoomPage.vue`、`useRoomDraft.ts`、`web/src/services/api.ts`、`roomApi.ts`、`src/agent_relay/interfaces/client.py`、`cli.py`、`mcp.py`、`application/dto/messages.py`、`dto/context.py`、`dto/delivery.py`、`domain/rooms/rules.py`、`infrastructure/persistence/models.py`、`infrastructure/codex/driver.py`、`bootstrap/paths.py`。Tagify 实现正在进行，接入点以高级开发 `0156` 的确认和最终交付为准。

### 原生图片投递的依据

- 已实际获取 [OpenAI App Server 文档](https://developers.openai.com/codex/app-server/)，其用户输入示例包含 `image` 的 URL 输入和 `localImage` 的路径输入。
- 本机 `codex-cli 0.167.2` 执行 `codex app-server generate-json-schema --experimental --out <临时目录>`，生成的 `v2/ThreadQueueAddParams.json` 和 `v2/TurnSteerParams.json` 都将 input 指向 UserInput；两者都包含 `image`、`localImage` 分支。
- 当前本机部署优先评估 `localImage`：由 Relay 将附件 ID 解析为自己管理的文件绝对路径，作为原生输入交给 Codex。浏览器的 blob URL、前端开发服务器 URL 和 Markdown 图片链接不能直接替代这个过程。
- 这些证据说明协议支持，不证明某个实际会话/模型已成功接收并识别图片。真实图片的 queue、steer、排队后读取仍需实施后验证。

本次生成的 schema 位于 `%TEMP%/agent-relay-image-schema-20261113`，不属于产品构建或版本库。

## Goals / 目标

- 用户在 Web/WebView 粘贴截图或拖入图片文件，上传后得到可发布的图片引用；文件选择可复用同一流程。
- Agent 通过 MCP/CLI 上传本地图片，取得图片 ID 和 Markdown，再调用现有 message_publish 发布给用户或其他成员。
- 图片文件持久保存在 API 本地，消息通过 Markdown 在正文相应位置显示图片；刷新后仍可读取。
- 保留纯文字、Skill 标签、纯图片 Markdown 和图文混排；草稿及发布查回继续沿用原始 content。
- 发给 Agent 的消息除保存 Markdown，还应携带可识别的原生图片输入。

## Proposed contract / 建议的图片契约

### 上传后返回标识与 Markdown

以下名称是评估示例，进入计划时统一接口命名：

| 入口                                            | 建议职责                                                         |
| ----------------------------------------------- | ---------------------------------------------------------------- |
| `POST /api/room/{roomId}/image`                 | 接收图片二进制上传，返回图片 ID、读取 URL、Markdown 和基本元数据 |
| `GET /api/room/{roomId}/image/{imageId}`        | 按 ID 返回图片内容，供 Markdown 的 img.src 读取                  |
| MCP `image_upload(room_id, path)`               | 在 MCP 进程所在机器读取文件，上传同一 API，返回相同结构          |
| CLI `agent-relay image upload ROOM --file PATH` | 在 CLI 所在机器读取文件并上传；继续使用现有 JSON 输出 envelope   |

建议成功响应的 data 形态：

```json
{
  "id": "img-abc123",
  "url": "/api/room/room-abc/image/img-abc123",
  "markdown": "![截图](/api/room/room-abc/image/img-abc123)",
  "mediaType": "image/png",
  "size": 123456
}
```

- Web、MCP、CLI 共用上传服务。MCP/CLI 的 path 是它们各自机器上的文件路径；由客户端读取并传二进制，API 不接受任意磁盘路径作为读取指令。
- API 在持久目录保存文件，并保存 ID、roomId、文件位置、类型、大小等元数据；图片 ID 稳定、文件内容不可原地覆盖，便于同一 Markdown 引用和重试保持含义。
- 用户已确定 API 本地保存，无需引入对象存储。开发时目录随本地配置解析，桌面时归用户数据根目录，独立于安装包和 web/dist。
- 建议使用带图片 ID 的标准相对 URL。既有 Markdown 渲染即可显示，开发代理与桌面同源 API 也可共用；无须发明 image: 协议或把机器路径写进正文。
- 上传返回的 Markdown 应使用已转义的 alt 文本和稳定 URL。上传成功只代表文件已保存，发布仍由现有 message_publish 单独完成。
- 首版建议 PNG/JPEG/WebP；具体字节、数量、像素限制留在计划确定。服务端核对实际文件内容及大小。

### 正文是图片位置与引用的唯一输入

例如，上传后直接发布：

```json
{
  "content": "请看这个问题：\n![截图](/api/room/room-abc/image/img-abc123)\n这里的按钮没有对齐。"
}
```

示例只展示正文；实际 message_publish 继续要求 publicationId 和显式目标。

- 消息沿用 content，不再同时要求 attachmentIds 或另一份有序图片列表；图片身份从标准 URL 取出，出现位置和重复显示均由 Markdown 决定。图片资源本身需要新增存储，消息记录无需新增附件字段。
- 草稿已有的字符串保存足以保留上传后的图片引用；publicationId 重放对原始 content 的比较也已覆盖图片 URL 和顺序，无须另加一套比较规则。
- 纯图片消息的 content 是图片 Markdown，并非空字符串，现有必填规则可沿用；6000 字符限制继续计算完整 Markdown。只有 Skill、没有正文或图片时的现有禁发规则不变。
- 发布前识别正文中真实的 Markdown image token，验证其中的本房间受管图片存在且可用。代码块、行内代码、转义示例和普通图片链接文本不应触发原生图片输入。应采用 Markdown 解析结果，避免用全局 URL 正则把示例当图片；后端解析器依赖在计划中确定。
- 只将规范的本房间图片 API 路径解析为本地资源；其他房间的受管引用拒绝，外部网站图片不因路径相似而被当作本地文件，也不由 API 自动抓取。
- 已上传图片可在同房间多次引用。消息保留每次显示位置；原生投递按首次出现顺序去重。编辑、撤销或移除 Markdown 不立即物理删除文件，避免影响已保存消息和仍在排队的读取。

## Tagify impact / 对 Tagify 的影响

高级开发在 `0156` 已基于正在实现的代码确认以下接入事实：

1. SkillMessageEditor 的 paste/drop 在 input capture 阶段执行 preventDefault 和 stopImmediatePropagation。当前图片文件不会自动成为上传；仅挂父级普通冒泡监听不足以接管。
2. 在 `.capability-input` 或 form 等真实祖先 DOM 注册 capture，可早于编辑器识别文件并处理。组件 inheritAttrs=false，不能假设把原生监听写到组件标签就会透传；也可在后续明确增加文件事件或钩子。
3. 现有公开 `selection()`、`replace({start,end}, text, skills?)` 支持同步插入普通 Markdown；replace 已接入长度检查、撤销、正文与身份同步，且拒绝 disposed/disabled/composing。
4. 图片 Markdown 保持普通文本，Skill 仍显示原子标签；首版编辑器无需增加图片节点。发送前图片预览可由 RoomComposer 的独立区域展示，发送后由 Markdown 在正文位置显示。

### 异步上传的插入策略

| 方式                                               | 接入代价与体验                                                                         |
| -------------------------------------------------- | -------------------------------------------------------------------------------------- |
| 上传完成后按添加顺序追加 Markdown 到最新正文末尾   | 可复用现有 replace，避免保存旧下标；用户可再编辑 Markdown 的位置。建议作为首版最小接入 |
| 在粘贴或拖入时建立唯一锚点，完成后替换仍存在的锚点 | 能保留原插入位置，但要新增锚点生命周期与撤销合并；撤销后不能复活没有任务的“上传中”占位 |

不能在上传完成后直接重用上传前的字符范围，因为用户可能已经增删文字或移动 Skill 标签。首版若采用末尾追加，应读取完成时的最新正文，按用户添加顺序统一插入，以一次事务进入撤销；并非把旧正文加上 Markdown 后整段回写。

回调还应捕获发起时的 roomId 和具体 editor 实例，并核对房间、可编辑状态、冻结发布、输入法状态；切房间或实例已销毁时不能写入新编辑器。已上传但未能自动插入的结果留在预览区供用户选择位置，不强行抢焦点或丢弃结果。原位插入是否必需是尚未确定的体验选择。

### 输入事件与预览

- 外层 capture 优先识别 ClipboardEvent/DataTransfer 中的实际图片文件，接管图片上传；普通文本与现有 Skill 自定义剪贴板继续交给编辑器。混合数据需要明确分发，只处理一次。
- 文件拖入还需在 dragover 阶段允许 drop；纯 URL/HTML 的拖拽不能伪装为已上传图片，也不增加远程抓取。
- 展示上传中、失败、已完成待插入状态；存在未处理的上传时不发布，用户可重试或移除。刷新中断且没有完成插入的文件需要重新选择，已保存正文中的图片 Markdown 可直接恢复。
- 已插入图片的预览从当前正文解析，删除 Markdown 时预览同步消失；从预览移除时，通过编辑器事务删除对应的 Markdown 出现位置。不能只删除预览而把仍会发送的图片引用留在正文中。
- 本地 object URL 仅用于临时预览，移除或卸载时释放；最终图片来源是 API。

## Rendering and delivery / 展示与投递

- MessageTimeline 继续经 messageMarkdown 渲染正文，在 Markdown 写入的位置显示图片，不另维护正文下方一份附件顺序。补充图片尺寸、比例、失败态和点击大图查看。
- 复制正文保留可复用的 Markdown 图片引用；回复及队列摘要可提取 alt 文本或“图片”描述，避免长 URL 占据摘要。
- DeliveryService 从有效图片引用取得图片 ID，交给应用层图片读取能力解析；基础设施 adapter 最终获得 API 管理的本地文件路径，在 queue 和 steer 共用的输入构建中加入 localImage。
- Markdown 正文保持原值，并随同一次投递发送；仅在 Markdown 中放 URL 不能证明模型已看图。继续沿用现有 clientUserMessageId、查回和未知结果处理。
- member_context 的 content 已包含图片标识与 URL。历史按需看图还需图片读取入口；如 MCP 要直接返回图像，需要专用 ImageContent 返回，不能只复用当前返回 TextContent JSON 的包装后声称已读图。

## Non-goals / 非目标

- 图片生成、OCR、裁剪标注、相册管理和图床服务。
- SVG、动图、音视频、PDF 和通用附件输入。
- 将图片二进制写入正文、Tagify mixed JSON 或 sessionStorage，或为图片改用另一套富文本编辑器。
- 自动抓取任意远程图片链接、历史图片迁移、跨机器文件同步。
- 改造现有浏览器存储异常处理。

## Acceptance criteria / 验收标准

- A01：Web/WebView 粘贴或拖入实际图片文件后完成上传；普通文字与 Skill 剪贴板不被重复处理或吞掉。
- A02：MCP 和 CLI 能上传各自进程可读取的图片，API 本地保存并返回相同的稳定 ID、URL、Markdown；随后可经现有消息发布入口回传图片。
- A03：图文、纯图片 Markdown 均可按既有目标规则发布；没有正文且仅有 Skill 时仍禁发。
- A04：多图和重复图片在正文 Markdown 所在位置显示；刷新后图片及大图仍能读取，代码示例不变成图片输入。
- A05：上传成功并插入的 Markdown 随草稿恢复；待确认发布保持原正文，查回与重试不产生第二条消息。
- A06：上传期间编辑正文、移动 Skill、切换房间、开始输入法或进入冻结状态时，不覆盖新输入、不向其他房间插入、不抢焦点；撤销/重做保持一致。
- A07：实际以空闲与活跃 Codex 会话验证 queue 和 steer，确认真实图片可识别；协议支持本身不算通过。
- A08：图片格式与大小错误有明确反馈；不存在或跨房间的受管图片被拒绝，API 不接受客户端指定的任意磁盘路径。
- A09：已有消息和 Skill 渲染不回归；复制、回复、队列摘要及历史按需读取有明确结果；WebView 交互由人工验证。

## Workload assessment / 工作量评估

这一方向收敛了消息模型：不再增加附件发布字段或改写草稿格式。工作量仍为中等，主要在图片资源与二进制上传、CLI/MCP 客户端接入、Markdown 引用识别、Tagify 事件接管及真实图片投递。首版采用末尾插入时，编辑器影响较小；要求保留粘贴原位时，需要额外处理锚点、选区和撤销，不能当作简单字符串拼接。

建议进入计划时拆成三个交付：

| 候选工作                | 主要产物与范围                                                   | 初始依赖与验收                                                                          |
| ----------------------- | ---------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 图片资源与上传入口      | API 本地存图、读取、元数据及 CLI/MCP 上传，返回统一 ID/Markdown  | 冻结图片路径和响应契约；对应 A02、A08                                                   |
| Markdown 解析与原生投递 | 本房间图片引用校验、代码示例识别、queue/steer 原生输入、历史读取 | 依赖稳定图片资源；对应 A03、A07，并支持 A04、A09                                        |
| Tagify 接入与展示       | 外层事件接管、异步插入、预览及图片展示，草稿/发布回归            | 依赖上传契约；共享 RoomComposer，等 Tagify 交付后串行接入；对应 A01、A04、A05、A06、A09 |

此处是候选边界，不建立任务分配，也不启动实现。验证复用现有 Node/Python 工具，聚焦上传契约、Markdown 引用识别和原生输入构建；真实图片识别与 WebView 交互由人工验证。

本次用项目已安装的 markdown-it 实际解析标准 API 相对 URL 图片，得到相应 img；反引号内的相同内容仍为 code。另核对当前 Tagify 的事件处理、公开 replace/selection，以及 JSON 客户端约束。未安装图片依赖或做浏览器/真实上传与投递验证。

## Open questions / 待定问题

- 图片上传后，首版是否要求保留粘贴/拖入的原光标位置？目前建议先按添加顺序追加 Markdown 到最新正文末尾；若要求原位，需要采用锚点方案。
- 文件大小、数量、像素限制及持久文件的清理策略在计划落实；不把此前建议值当作用户已确定要求。

## Decisions / 决策

- 用户已授权 Tagify 实现并指定高级开发接手；架构师不再修改其 package/lock、编辑器组件、RoomComposer 或行内 Skill 文档。
- 用户 `0154` 已确定 MCP/CLI 上传回传、API 本地存图、Markdown 消息展示。此前“Agent 回传留待以后”和“单独 attachmentIds 发布列表”的建议被此方向替代。
- 建议继续 content 字符串作为消息输入；图片资源新增独立持久化，不提前改动高级开发正在交付的编辑器。
- 当前只完成评估与协议核对，不安装图片处理依赖、不启动图片实现、不执行 Git 暂存或提交。

## User review notes / 用户审查记录

- `0149` 原文：“将实现工作移交给高级开发，架构师 要开始负责评估图片输入和展示 需求”。
- `0150` 已向高级开发交接 Tagify 的共享改动与约束；`0151` 高级开发确认接收，且不改图片范围；`0152` 补充准确授权原文。
- `0154` 原文：“预期可以粘贴、拖入图片，通过 mcp/cli 上传回来拿回图片标识，图片存储在 api 本地，消息中以 markdown 渲染，以这个方向评估。也要考虑对 tagify 的影响”。
- `0155` 已向高级开发请求只读接入评估；`0156` 确认祖先 capture 可接管，公开 replace/selection 可插入 Markdown，并指出异步旧选区与跨房间回写的约束。本次没有要求其追加图片实现。
