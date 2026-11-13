# Plan / 计划：行内 Skill 数据结构兼容核对

最后修改时间: 2026-11-13 12:56:59

## Review status / 审查状态

Accepted

方案修订 2。依据 [已接受的意图](../intent/20261113-inline-skill-references.md) 与用户消息 `room-a2493e542ba3-msg-0133`，本轮停止于数据结构兼容核对，不实现第二步编辑器。修订 1 的第二步实施安排已被覆盖。

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
