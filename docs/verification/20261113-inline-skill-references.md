# 行内 Skill 引用：第一步交付

日期：2026-11-13。依据聊天室消息 `room-a2493e542ba3-msg-0116`，先实现位置保存与消息正文渲染，编辑框中的彩色标签后续实现。

## 已实现

- 选择 Skill 时在现有 textarea 的光标位置插入 `[名称](skill:ID)`，名称中的反斜杠和方括号转义；引用顺序由正文保存，前文增删不会产生下标偏移。
- 正文输入、清空和移除 Skill 时同步 capabilities；同一 Skill 可以重复插入，实际引用按正文首次出现顺序去重。已选身份暂存供文本撤销后的引用恢复使用。
- 新消息按 Markdown 的行内引用规则原位显示标签，使用与选中 Skill 一致的主色、边框及 Sparkles 图标；依据用户消息 `0125`，正文标签不设置背景色。已在正文展示的 Skill 不重复出现在正文上方。
- 格式扫描保留围栏代码、行内代码和转义示例；未绑定身份的标记不渲染为 Skill 标签。
- 复制正文、回复预览、队列摘要及投递正文转换为 `$名称`；数据库和待确认发布 payload 保留原始正文，Codex 原生 Skill 输入继续使用结构化引用。
- 仅有 Skill 标记而没有正文时禁用发送；超长插入和失去身份的引用通过字段反馈/发送提示说明。后端也校验引用身份和空正文。
- 沿用现有 content/capabilities 字段，无新增依赖或数据库迁移。历史数据没有回填或改写。

## 与草稿功能的协作边界

架构师消息 `0118` 已交接 RoomComposer。增量保留 ready 属性、元数据过滤中的 ready/locked/sending 保护、无变化时不回写，以及 quote/submit/reset 的 draft.replyToMessageId 行为。

本次未修改 RoomPage、rooms、useRoomDraft 或 messageDrafts。正文和 capabilities 通过同一次模型更新交给已有的同步草稿保存逻辑，冻结请求不经过编辑归一化。

## 实际验证

| 目录               | 命令/范围                                                                  | 结果                                                            |
| ------------------ | -------------------------------------------------------------------------- | --------------------------------------------------------------- |
| `web`              | `vue-tsc --noEmit`                                                         | 通过                                                            |
| `web`              | `vitest run --reporter=default --silent=false --no-color`                  | 16 个文件、106 个测试通过，包含并行交付的草稿测试               |
| 仓库根目录         | `uv run --locked pytest tests/unit/domain tests/unit/application -q`       | 111 个测试通过                                                  |
| 仓库根目录         | `uv run --locked mypy src tests`                                           | 180 个文件检查通过                                              |
| 仓库根目录         | Ruff check、Ruff format --check：新增格式模块及改动的 DTO、投递和相关测试  | 通过                                                            |
| `web`              | ESLint：改动的房间组件、格式/Markdown 模块、中英词条及新增测试             | 0 errors；MessageTimeline 保留原有的 1 条 vue/no-v-html warning |
| 仓库根目录及 `web` | Prettier --check：本次前端代码、共用 JSON 样例和过程文档；git diff --check | 通过                                                            |
| `web`              | `vite build --mode prod`                                                   | 通过；输出 JS 708.34 kB，存在大于 500 kB 的构建提示             |

最后将标签图标与现有 Sparkles 对齐后，重新运行了行内 Skill 的 13 个测试和生产构建，均通过。未启动开发服务器、运行真实浏览器/WebView 或提交 Git。

前后端通过 `tests/fixtures/inline_skills.json` 共用格式样例，检查引用顺序、重复引用、代码与转义示例。额外测试覆盖原位 HTML、显示名称转义、身份校验、空正文和投递文本转换后保存正文保持原值。

## 用户人工验证步骤

1. 在正文中间输入 `$` 并选中一个 Skill，再继续输入文本。当前编辑框应显示完整文本引用；发送后，标签应出现在同一段文字的相同位置。
2. 在标记之前增加或删除文字、换行，再发送和重新加载消息；标签位置应随正文保留。同一个 Skill 插入两次时，正文展示两处，选择列表只保留一个引用。
3. 删除一处重复标记后，另一处仍有效；删除最后一处或点击上方 Skill 的移除按钮后，不再携带该 Skill。仅保留 Skill 标记时发送按钮禁用。
4. 在行内代码、围栏代码中放入引用示例，发送后仍显示代码。复制一条正常的行内引用消息，正文中的引用应变为可读的 `$名称`；回复预览和队列摘要同样检查。
5. 保存包含标记的未发送草稿，切换房间或刷新后继续发送；正文、Skill 身份和引用消息上下文应保留。中文输入法确认、Enter 发送和 Shift+Enter 换行继续使用现有 textarea 行为。

编辑框内的彩色整体标签、标签边界选区和专门的剪贴板交互归第二步，未将本次 Node 检查作为这些交互的验收证据。

## 用户测试修正：正文后直接输入美元符号

用户消息 `0121` 报告正文输入后 `$` 无法展开候选。原因是旧查询正则要求 `$` 前面为开头、空白或括号，直接紧接中英文正文时匹配失败。

已去掉前置分隔要求，将光标处查询提取为生产代码调用的 `skillQueryAt`。选中后仅替换 `$` 查询范围，保留之前的正文及查询之后的内容。

新增 7 个轻量回归用例，覆盖紧接中文、英文、标点/emoji、多行正文，以及光标位于查询名称中间时的完整替换范围。相关 Vitest 共 20 个测试通过；Vue 类型检查、改动范围 ESLint（0 errors、0 warnings）、Prettier 和 diff 空白检查通过。实际列表展开效果继续由用户验证。

用户随后通过消息 `0124` 发送了真实 Skill 测试消息；member_context 返回的正文包含原位的 Skill 标记，capabilities 中包含匹配 ID 和名称的 dev-check 引用，投递消息也携带了该技能。消息 `0125` 确认“渲染出来了”，并要求移除正文 Skill 背景色，已据此调整样式。

该测试实际触发 dev-check 后，按现有 Makefile 检查范围完成以下只读检查：

- 仓库根目录：`uv run --locked mypy src tests` 通过（180 个文件）；`uv run --locked ruff check .` 通过；`uv run --locked ruff format --check .` 通过（296 个文件）。
- `web`：本地 `vue-tsc --noEmit` 和 `prettier --check .` 通过；`eslint .` 为 0 errors、20 条既有 warnings，涉及 Vue 模板格式及 v-html。
- 仓库根目录：本次两份行内 Skill 文档的 Prettier 检查及 `git diff --check` 通过。
