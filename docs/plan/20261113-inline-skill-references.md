# Plan / 计划：行内 Skill 与编辑器演进

最后修改时间: 2026-11-13 14:32:00

## Review status / 审查状态

Accepted

方案修订 4。用户 `0162` 已授权尝试 Tiptap + Mention，由架构师重新评估并交高级开发实施。Tagify 工作已完整暂存，作为本次试切的保留基线；当前执行以 [Tiptap 消息编辑器计划](20261113-tiptap-message-editor.md) 为准，后文 Tagify 和结构核对记录保留历史意义。替换不改变第一步已交付的 `content + capabilities` 契约。

## Previous implementation / 先前 Tagify 实施（修订 3）

用户 0147“改为 Tagify mixed-content 方案实现”，0149“将实现工作移交给高级开发，架构师 要开始负责评估图片输入和展示 需求”授权此前第二步；准确原文由架构师消息 0152 补充。下述依赖、手写历史及 DOM adapter 属于待替换基线，不要求在 Tiptap 实现中继续保留。

- 独立 `SkillMessageEditor.vue` 使用 Tagify mixed-content、允许重复标签，复用现有候选 UI；原文通过 text nodes 写入，标签由 `createTagElem` 创建，禁止把用户原文传给 `parseMixTags` 或 innerHTML。
- DOM adapter 继续输出原始 `[名称](skill:ID)` 字符串；capabilities 以 ID 去重，保留原始 marker、代码／转义示例、换行及草稿/API/数据库契约。Tagify mixed JSON 不进入模型。
- 自有编辑历史覆盖普通输入、候选插入、标签删除、清空与剪贴板；相同模型回写不重建 DOM 或选区，外部正文替换清空旧历史。编辑器随 roomId 重建，禁用或冻结时拒绝回写。
- 候选按键先于发送；统一拦截 Tagify 的异步 Enter 处理，Enter 发送、Shift+Enter 换行，输入法组合确认不发送。6000 按序列化正文长度检查，仅标签禁发。
- 内部剪贴板携带正文和身份，粘贴时按当前已知／可用 ID 核对；外部纯文本使用可读 `$名称`，不凭名称加载 Skill。上方不重复显示正文中已有的 Skill。
- 高级开发独占 editor、RoomComposer、package/lock、行内 Skill 文档、必要样式和测试。架构师仅评估图片需求，不并行改这些文件。本轮不自动暂存、提交或启动浏览器／开发服务器。
- Node 单测覆盖序列化、原子范围、历史、长度及剪贴板身份规则；实际 DOM、鼠标选区、输入法和系统剪贴板由用户人工测试，单测不作为这些行为的通过证据。

实施接收：2026-11-13 13:36 +08:00，高级开发按 0150/0152 接手；实际基线 HEAD `73e0033bad1451d5a43c66f54e47ee7c6075e68e`，已有未提交 package.json、pnpm-lock.yaml、skillEditorModel.ts、skillEditorDom.ts 四项初稿。依赖为 Tagify 4.39.0、类型 4.27.0；接收时尚未接入组件。当前进入实现与验证，完成事实见后续交付记录。

## Previous structure review / 先前结构核对（修订 2）

## Gap assessment / 差距评估

| 目标                 | 已有结果                                                                  | 本轮结论                                     |
| -------------------- | ------------------------------------------------------------------------- | -------------------------------------------- |
| 准确位置与重复引用   | `[名称](skill:ID)` 标记随 content 保存，消息正文原位渲染                  | 结构已满足；前文增删无需维护独立位置下标     |
| Skill 身份与实际加载 | capabilities 保存去重的 type、id、name；DTO 校验标记与身份对应            | 结构已满足；不凭名称推断身份                 |
| API、数据库与草稿    | 使用 content 字符串和 capabilities 数组；数据库已有 TEXT 与 JSON 引用存储 | 无需新增字段、迁移或草稿格式                 |
| 编辑框内彩色整体标签 | textarea 显示文本标记，尚无整体标签编辑行为                               | 真实差距，按 0133 留待后续第二步，本轮不实现 |

判断：现有结构已经为未来编辑器保留位置和身份。未来可以只改变显示与编辑事务，继续序列化成相同字段；本轮不需要生产代码变更。

## Technical decisions / 技术设计与决策

- 保留 `content: string` 和 `capabilities: CapabilityReference[]`；不新增字符下标、富文本文档或冗余位置字段。
- content 保留原始标记顺序和重复出现，capabilities 按 ID 保存唯一身份；现有编解码、代码示例识别、可读文本转换及后端校验继续生效。
- 草稿同步保存同一次模型更新中的正文、身份、目标和引用消息；恢复后原文不变，待确认发布仍保持原始 payload。
- 通过现有轻量单测补齐草稿与行内引用的联动证据；未来编辑器继续遵守相同契约，其选区、撤销、输入法和剪贴板交互不由本轮测试证明。

## Scope and files / 范围与文件

- 本轮产物：本意图与计划、`web/tests/domains/room/useRoomDraft.test.ts` 中新增的一项集成回归用例。
- 保留第一步和草稿的共享工作区改动；本轮未修改生产代码、manifest 或 lock，未引入编辑器组件或依赖。
- 不处理浏览器存储故障、历史迁移、服务端草稿或自动重发。

## Implementation steps / 实施步骤

1. 核对前端类型、标记编解码、草稿、API／DTO 和数据库存储，确认位置和身份已有完整承载。
2. 增加一次完整草稿保存／恢复用例，覆盖多行、emoji、重复 Skill 标记和引用消息。
3. 运行定向检查，收敛第二步安排并记录结论；不启动编辑器实现。

## Coordination and authorization / 协调与授权

- 当前有效范围为用户消息 0133；架构师完成结构核对和回归收尾，无须拆分 task。
- 核对基线为 `09556edc00750526ec54da94192f5cd5c31b4bb3` 加第一步与草稿的共享改动；结构核对时未暂存、未提交。
- 后续用户消息 `0138` 确认“测试有效”，并授权按功能拆分暂存和提交。先提交草稿，再提交行内 Skill 及其联动回归；本轮不启动第二步编辑器。
- 架构师消息 `0134` 已停止第二步安排；高级开发消息 `0135` 确认只写过接收记录，没有产生第二步代码、依赖或 RoomComposer 接入。

## Checks and acceptance / 检查与验收

- 格式、引用同步、草稿保存／恢复和房间发送状态的定向单测通过；正文及身份恢复一致。
- 后端行内格式、DTO 引用约束和可读投递转换的现有单测通过。
- Vue 类型检查、新增测试与文档的 Prettier 检查及 `git diff --check` 通过。
- 不运行真实浏览器、WebView 或数据库集成测试；不将现有 Node／Python 测试作为未来编辑器交互的验收证据。

## Risks / 风险

结构核对无待确认问题。未来第二步仍需单独处理编辑器选区、输入法、剪贴板和事务一致性；本轮不声称这些行为已完成。当前工作区保留第一步及草稿的未提交改动。

## Implementation reception and progress / 实施接收与进展

2026-11-13 12:43:56 +08:00，高级开发曾按架构师消息 `0132` 接收第二步；接收时基线为上述共享工作区，尚无 CodeMirror 依赖或第二步编辑器代码。

用户消息 0133 随后覆盖该安排；0134 已要求停止，高级开发在 0135 确认仅写了接收记录，没有产品或依赖改动。原“接收后进入编辑器组件与事务实现”不再生效，执行收敛为数据结构核对，无需第二步实现。

## Integration review / 架构师集成核对

已读取第一步的编解码、渲染、RoomComposer、后端校验和现有草稿模块，确认未来编辑器可沿用 content/capabilities，无须增加字段或重做草稿。

- 新增一个集成回归用例：含 emoji、多行、重复行内标记的正文与去重 Skill 身份、引用消息一起同步保存并在新的草稿实例恢复，原始文本保持不变。
- `pnpm test tests/domains/room/inlineSkills.test.ts tests/domains/room/useRoomDraft.test.ts tests/stores/messageDrafts.test.ts tests/stores/rooms.test.ts`：4 files、46 tests passed。
- `pnpm typecheck` 通过。
- `uv run --locked pytest tests/unit/domain/test_inline_skills.py tests/unit/application/test_request_contracts.py tests/unit/application/test_delivery_actions.py -q`：29 tests passed。
- 新增测试与两份过程文档的 Prettier 检查、新增测试的 ESLint 检查、`git diff --check` 通过。
- 这些结果证明第一步／草稿的当前集成规则，不是第二步整体标签、DOM／剪贴板或输入法的实测结论。

## Delivery and review / 交付与审查

本轮数据结构兼容核对完成，现有结构满足要求，无需生产代码、字段或迁移变更。第二步未实施，相关差距留在意图的后续参考中；第一步交付及其 [验证记录](../verification/20261113-inline-skill-references.md) 保留。
