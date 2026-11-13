# Plan / 计划：Tiptap 消息编辑器与图片引用

最后修改时间: 2026-11-13 15:05:00

## Review status / 审查状态

Accepted

用户消息 `room-a2493e542ba3-msg-0162`：变更已经暂存，决定尝试 Tiptap + `@tiptap/extension-mention`，以支持消息文本框 Skill 及图片粘贴、拖入；架构师重新评估后交付高级开发实施。本计划记录架构师的范围收敛和交接，不表示实现或交互验证已完成。

用户 `0172` 修订 `$` 的前置规则：保留边界限制，将原来的“开头、空白或括号”扩展为“开头、空白或符号”，覆盖先前允许紧接普通中英文正文的要求。以下实施与验收已据此更新。

## Baseline and ownership / 基线与分工

- HEAD 为 `73e0033bad1451d5a43c66f54e47ee7c6075e68e`。用户已暂存 Tagify 相关 14 个文件；开始本次评估时工作树没有额外未暂存差异。`0164` 中高级开发独立确认了这一事实。
- 架构师负责本计划、旧意图与旧计划的生效范围整理，以及后续架构核对；不并行改产品代码、package/lock 或暂存区。
- 高级开发接手编辑器、RoomComposer、依赖、必要样式/i18n、最小图片 API 和实施验证文档，按下面两个工作包串行推进。
- 现有暂存区保留为试切前快照。后续修改先留在工作树，不自动重新暂存、提交、回退或清理；删除已淘汰文件也应是可审阅的工作树差异。

## Assessment / 重新评估

当前 Tagify 封装自行维护 DOM 到字符串位置映射、自建历史、标签删除和剪贴板，并在输入后重建部分 DOM。复杂度已经集中到编辑核心。此次替换的价值是让 ProseMirror 成为文档、选区、事务和历史的唯一负责人，而不是在 Tiptap 外继续维护一套字符串选区和历史。

Tiptap Mention 的稳定版源码已经提供 `inline: true`、`atom: true`、`id/label` 属性、Suggestion 接入和 Backspace 行为。图片只需行内引用节点，无须引入文档排版、图片缩放或整套富文本工具栏。Vditor 的 Markdown/图片上传功能完整，但其补全接口不等同于稳定的自定义原子节点模型；当前需求优先选择 Tiptap。

已查询 npm：`@tiptap/extension-mention` 当前稳定版为 `3.33.1`，要求 `@tiptap/core`、`@tiptap/pm`、`@tiptap/suggestion` 同为 `3.33.1`。实施时所有 Tiptap 包使用同一精确版本，并核对实际安装源码；本文没有测量新的生产包体，也不以 npm 解包大小代表增量。

## Scope / 本次范围

| 工作包            | 本次交付                                                                                                                | 完成边界                                                                      |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| W1 编辑器替换     | Tiptap + Mention，保留现有 Skill 候选外观、原子标签、文本/身份同步和草稿/发送行为                                       | 移除 Tagify 专用实现，类型与构建检查可通过，提供人工交互步骤                  |
| W2 图片输入与展示 | Web/WebView 图片文件粘贴、拖入；最小上传与读取 API；API 本地持久保存；原位插入图片标签并序列化为 Markdown；消息显示图片 | 实际图片文件能上传、随消息保存并在刷新后读取；仅有 Skill 时仍禁发，纯图片可发 |

W1 完成后继续 W2，无需再次申请技术选型许可。图片上传接口尚不存在，不能把仅安装 FileHandler 或仅抛出文件事件报告为 W2 完成。

MCP/CLI 图片上传、Codex queue/steer 的原生图片输入、历史按需看图保留在 [图片需求评估](../intent/20261113-message-images.md)，不在本次首轮实施范围。当前仅传递 Markdown URL，不代表 Agent 已收到可识别的图像；交付必须说明这一实际限制。此次也不实施对象存储、附件管理、图片加工或自动文件清理。

## Editor decisions / 编辑器决策

### 文档和依赖

- 最小节点为 Document、单个承载行内内容的正文节点、Text、HardBreak、Skill Mention 和图片引用；按需引入 UndoRedo。正文使用保留空白的规则，连续换行与尾部换行必须可表示。
- 引入 `@tiptap/vue-3`、core、pm、mention、suggestion 及实际用到的基础扩展；文件事件可以使用 FileHandler，也可用已有 editorProps。只保留一种 paste/drop 入口。
- 本轮正文仍按 Markdown 源文输入，基础标点、列表、代码围栏、HTML 字面量都是文本。按需装配扩展，不自动启用 Markdown input rules、整套 StarterKit、完整 Image 排版节点或富文本粘贴。
- 源文输入通过文本/JSON 节点构造，不能把用户字符串交给 HTML `setContent/insertContent` 后声称保真；本轮无需 `@tiptap/markdown`。

### Skill 与父组件接口

- 编辑器拥有 Mention 的查询范围、候选替换和事务。保留父级现有候选列表的展示和目录过滤；可通过查询事件和 `insertSkill(reference)` 等业务命令连接，不继续让父级维护字符串坐标并调用通用 `replace`。
- 现有 `selection/setSelection/replace` 没有跨组件稳定 API 承诺；仓库调用集中在 RoomComposer，可随集成移除。保留引用消息之后的 `focus` 能力。
- `$` 前必须为开头、空白或符号；符号包括 Unicode 标点和符号类别（`\p{P}`、`\p{S}`），不限于括号。紧接普通中英文或数字不触发。前置判断按 Unicode 码点处理，匹配器与共享查询函数采用同一规则，保留 ProseMirror 的位置与事务；代码与转义排除继续生效。
- 查询位于词中间时替换整个查询后缀，不能遗留半个名称。代码、转义文本中的引用识别沿用既有约定；候选的触发也应尊重这些上下文。
- 按 ID 保存身份，显示名称来自已绑定引用；同一 Skill 可重复出现，capabilities 按正文首次出现顺序去重。删除最后一处后移除引用，撤销能恢复身份。
- Mention 原子删除应删除整个标签，不在 Backspace 后遗留 `$`；按安装版本核对 `deleteTriggerWithBackspace`。边界移动、跨节点删除和撤销使用原生事务，不再自建快照历史或 DOM Range 映射。
- 候选按键优先于发送；输入法确认不发送，Enter 发送，Shift+Enter 换行。保留 ready/locked/sending、字段反馈、清空、无变化不回写、replyToMessageId 和目标选择保护。

### 序列化与无损边界

| 内容           | 导入/导出规则                                                                                                                                   |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| 普通文本       | 中英文、emoji、空白、Markdown 标点、HTML 字面量原样保存；普通模型回写不触发整段 `setContent`                                                    |
| 换行           | 已有 content 原样恢复，包括 CR/LF 输入的既有内容；新粘贴的外部 CRLF/CR 沿用当前行为转成 LF；连续空行、首尾换行不丢失                            |
| Skill          | 复用 inlineSkills 识别规则；仅把有效且已绑定 ID 的标记变为节点，保留原始 marker 以免无编辑时重写名称/转义；新选 Skill 使用 formatSkillReference |
| 代码及转义示例 | 行内代码、围栏代码、缩进代码及转义标记保留文本；未知身份不能凭显示名升级成 Skill                                                                |
| 图片           | 受管图片引用节点保留 ID、URL、alt 和原始 Markdown；新上传用 API 返回的规范 Markdown，普通图片链接及示例不因形状相似而自动绑定                   |
| 外部同步       | 同一已输出模型回传不重置选区或历史；切房间、明确恢复外部正文时使用新的实例/历史，不把旧状态写入新房间                                           |

编码解码是 Markdown 字符串与少量业务节点的适配，不是完整 Markdown 富文本转换。草稿/API/数据库继续只有 `content: string` 与既有 `capabilities`，不保存 Tiptap JSON 或二进制。字符串长度按最终序列化 content 计算，仍是 6000；节点计数或 `getText()` 长度不能替代。

若用户在编辑中添加/删除代码分隔符，使既有引用落入或离开代码上下文，应在现有事务机制内协调节点与文字，不整段重建文档或清空历史。Skill 身份只来自明确选择、草稿或校验过的内部剪贴板。

剪贴板保留两层语义：外部纯文本输出可读的 `$名称` 与图片 Markdown；内部载荷保留引用原文和身份，粘贴时按当前房间目录/已绑定 ID 校验。ProseMirror HTML 或外部 HTML 的 data-id 不自动成为可信身份。

RoomComposer 现有发送时 trim 属于既有发布行为；编辑器、外部模型同步及草稿阶段不得额外 trim 或格式化。

## Image integration / 最小图片链路

### 上传与读取

- `POST /api/room/{roomId}/image`：每个请求一个 `multipart/form-data` 的 `file`，成功为 201 JSON，按项目既有 DTO 返回 `{id, url, markdown, mediaType, size}`。
- `GET /api/room/{roomId}/image/{imageId}`：按房间和 API 生成的 ID 返回实际图片二进制与正确 Content-Type；`img.src` 直接读取，不走强制 JSON 的 apiClient 解码。
- 文件保存在 API 持久数据目录，开发和桌面的路径解析沿用 bootstrap 规则，不能放 web/dist 或安装资源目录。文件及所需最小元数据由图片资源管理，消息表无需附件字段。
- API 生成不可覆盖的稳定 ID，验证房间存在、大小及真实图片格式，拒绝客户端指定磁盘路径和跨房间文件读取。首轮 PNG/JPEG/WebP、每张最大 10 MiB，作为工程初始值集中声明；需要内容识别依赖时选用成熟库，不自行实现图片解码。
- 复用现有错误响应和 requestId；上传错误在输入处反馈。图片上传不是消息发布，不改变 publicationId、待确认请求或未知结果不自动重发规则。
- 不自动抓取 HTML/远程 URL 中的图片，不把 base64/blob URL 当成最终资源引用。

### 文件事件与异步位置

- paste/drop 仅在实际图片 files 存在时接管；普通文本和内部 Skill 剪贴板仍进入同一编辑器事务。浏览器同时携带 file、HTML、text 时只插入一次，不再追加重复 HTML 图片。
- 在粘贴/拖入时按文件原顺序创建临时上传锚点，使用 ProseMirror 插件状态/Decoration 的事务映射定位；完成后在仍有效的锚点插入图片引用节点。使用官方上传示例的机制，不保留上传前的裸字符下标，也不统一改成末尾追加。
- 上传锚点和任务不进入 content/草稿；存在上传中任务时禁发。失败移除临时锚点并给出反馈，用户可重新选择文件；上传中的文件在刷新后需要重新粘贴。
- 用户移除锚点、清空、切房间、实例销毁后，任务不能重新插入。回调捕获具体 editor 和 roomId，并校验 ready/locked/sending；输入法组合期间先保留完成结果，组合结束后再验证锚点，不抢焦点。
- 多图完成顺序不改变原插入顺序。上传完成的替换使用编辑事务，已插入图片支持删除、撤销/重做；撤销或重做不能复活没有任务的“上传中”占位。
- 输入框用行内图片标签表达引用，不要求在框内排版大图或维护第二套有序附件列表。消息经现有 Markdown 展示图片，补充合理的图片宽高限制与加载失败反馈；图片标记本身满足非空正文，纯图片可发。

## Work steps / 实施步骤

1. 接收并记录暂存基线；安装同版 Tiptap 最小依赖，替换编辑内核和 Skill 事务，接通现有候选列表。
2. 完成源文/节点 codec、剪贴板、长度和身份同步；移除 Tagify 依赖、packageExtensions、专用 DOM adapter 和自建历史。若旧测试依赖已删除实现，同步移除失效部分，保留现有独立引用规则覆盖。
3. 核对 W1 类型、格式、生产构建，记录交互待人工验证；继续最小图片 API、持久文件和受管 URL。
4. 接通文件事件、事务锚点、行内图片引用及消息图片展示；核对草稿、切房间和冻结状态。
5. 更新 `docs/verification/20261113-tiptap-message-editor.md`，列出实际执行命令、未验证项、包体变化和用户人工步骤，再交架构师核对最终差异。

按用户既有要求，本轮不新增或运行自动化测试，不自动启动浏览器、开发服务器或 WebView。可运行既有类型检查、改动范围 lint/format 和生产构建；涉及 Python 时做对应静态检查。若静态检查发现实际必要问题，修复本轮改动，不顺带清理无关问题。

## Acceptance checklist / 人工验收清单

- 在开头、空格/换行、括号、中英文标点或 Unicode 符号后输入 `$`，候选可展开，选中后标签原位显示；`正文$dev`、`text$dev`、`123$dev` 不触发。词中间的查询替换完整，候选 Enter 不误发，输入法确认不发送。
- 标签前后移动、拖选、整体删除、连续输入、换行、清空和撤销/重做保持一致；重复 Skill 删除最后一处才移除身份。
- 草稿保存/恢复及无变化回写保留正文、转义、emoji、空白、代码示例、引用消息和目标；编辑器不会在普通更新时跳到末尾。
- 复制粘贴 Skill 保留经过校验的身份；外部 HTML/普通同名文本不能携带未经选择的 Skill；未知引用和代码示例保持文字。
- 实际截图粘贴及文件拖入完成真实上传，标签位于原位置；上传期间增删文字、移动标签或多图乱序完成不覆盖正文，不重复插入。
- 上传中禁发；失败、清空、移除锚点、切房间、冻结/发送、输入法组合结束后的回调有确定结果；撤销不复活未完成任务。
- 图文和纯图片消息发布后按 Markdown 位置显示；API 重启/页面刷新后仍可读取，图片标记随草稿恢复，超长标记和无正文仅 Skill 仍受校验。
- 记录静态验证与人工验证的区别，不把类型检查、Node 逻辑或文件事件触发当作真实剪贴板、WebView、上传及 Agent 看图成功证据。

## Handoff / 交接记录

架构师已完成方案与仓库接入核对，下一责任人为高级开发 `member-bdc147ac1ce6`。`0164` 已确认其等待本计划，并建议由新编辑器拥有 ProseMirror 位置与 Mention 事务，本计划采纳。正式交接通过 Agent Relay 定向发布；高级开发接收后在本节追加时间、实际依赖版本和开始状态。当前没有产品实现或新验证通过的结论。

- 2026-11-13 14:34，高级开发依据用户 `0162` 与架构师 `0165` 接收 W1→W2，实际 HEAD 仍为 `73e0033`，原 14 文件暂存快照保留。架构师的四份文档变更位于工作树；开始安装同版 3.33.1 最小 Tiptap 依赖与实现，不自动暂存、提交或运行测试。
- 2026-11-13 15:03，W1/W2 产品代码已完成，实际依赖为 Tiptap 全部 3.33.1、Pillow 12.3.0、python-multipart 0.0.33。架构师 `0171` 只读核对确认 P1 插件键和 P2 输入法提交顺序已修正，未发现其他阻止源码交付的问题。实际静态结果、类型检查既有失败及人工待验项见 [验证记录](../verification/20261113-tiptap-message-editor.md)。尚未做真实浏览器/WebView、上传与刷新重读验证，未自动暂存或提交。

## References / 依据

- [Tiptap Mention](https://tiptap.dev/docs/editor/extensions/nodes/mention) 与 [v3.33.1 Mention 源码](https://github.com/ueberdosis/tiptap/blob/v3.33.1/packages/extension-mention/src/mention.ts)：原子节点、身份属性、Suggestion 和删除行为。
- [Tiptap Schema](https://tiptap.dev/docs/editor/core-concepts/schema)：按需节点和严格文档结构。
- [Tiptap FileHandler](https://tiptap.dev/docs/editor/extensions/functionality/filehandler)：文件事件支持，不包含服务端上传。
- [ProseMirror 上传示例](https://prosemirror.net/examples/upload/)：通过随事务映射的占位定位异步结果。
- [Tiptap Markdown](https://tiptap.dev/docs/editor/markdown)：完整 Markdown 桥当前标为 Beta，本轮无需引入。
