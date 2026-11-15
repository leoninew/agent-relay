# Verification / 验证：单选成员模型展示与切换
最后修改时间: 2026-11-16 07:45:09

## Review status / 审查状态

Draft。本记录整理 Implementation 的开发检查与交付证据，未宣布整体 Verification 完成。用户自行进行 UI 测试；本会话未操作浏览器，也未切换真实会话模型。

## Intent alignment / 意图对齐

依据[意图](../intent/20261115-member-model-selection.md) A01–A11，实现直接单选 Agent 成员的模型目录和后续轮次模型配置。保留话题与成员多选路由；目标不受侧栏筛选或话题接收者影响。模型区域与话题/成员同排，前 4 项加“...”悬浮完整列表，显示 model、tip 为 displayName，选中背景共享话题/成员规则。请求失败走 Toast。

## Plan alignment / 计划对齐

依据[计划](../plan/20261115-member-model-selection.md)修订 5，实现 provider 范围目录分页、原始 id/model 分离、原会话身份/cwd 校验、兼容 effort、一次更新后读取确认。Popover + Portal 保留列表按钮焦点；成员区出现模型时不再 flex-grow。未增加消息发送、轮次控制、队列操作或数据库迁移。

## Task deliveries and integration / 子任务交付与集成

交付基线为 HEAD `9bb93db0f6f0b05d00b6e493862e739dc81d6b3a` 加本工作区 staged/unstaged 总 diff；两部分均属于交付，不改动已有 index。

| ID | 当前有效交付版本 / 位置 | 必要检查与审查证据 | 集成与基线核对 | 验收归属与结果 |
| --- | --- | --- | --- | --- |
| T01 | model-T01-01、修订 5，[任务记录](../task/20261115-member-model-selection/T01-session-model-api.md)及 backend diff | 后端 428 tests、mypy、ruff；不同 id/model 的 HTTP 与目录用例 | 无前置，API 与 typed client 字段一致；主会话接受 | A02–A04、A10 字段：开发证据通过；真实写入未测 |
| T02 | model-T02-01、修订 5，[任务记录](../task/20261115-member-model-selection/T02-composer-model-picker.md)及 web diff | 14 个模型状态测试、API 测试，全套 177 tests、typecheck/lint/format/build | T01 最新原始字段已集成；主会话接受 | A01、A04–A05、A07–A11：已实现，界面由用户确认 |
| T03 | model-T03-01、修订 5，[任务记录](../task/20261115-member-model-selection/T03-development-checks.md)及过程记录 | 全套开发检查及高度变量收尾复验，git diff --check | T01/T02 当前 diff 已核对；主会话接受 | A06：开发检查通过，无 UI 测试 |

## Corrections and scope / 修复与范围

以下是 Implementation 中完成的修正，不作为已执行整体验证的声明。

| 对齐依据 | 发现的偏差 | 实际修复 | 复验结果与证据 |
| --- | --- | --- | --- |
| A02、T01 | 真实目录允许空 supportedReasoningEfforts | 空列表接受实际默认 effort，非空列表继续校验 | 目录适配单测与真实 provider 只读查询通过 |
| A10、修订 5 | 目录 ID 与模型值曾合并 | API 分别返回 id/model；按钮、切换和选中使用 model，tip 使用 displayName | 原始字段不同的后端/前端用例通过 |
| A09、A11 | 成员 flex-grow 造成空白，模型需共享选中态 | 模型出现时取消增长，选中背景使用同一 CSS 选择器 | 格式/构建通过，视觉效果待用户确认 |
| T02 浮窗方案 | HoverCard 会剥夺列表按钮 Tab 焦点；样式残留其高度变量 | 改 Popover + Portal，使用对应 available-height 变量及 fallback | 类型检查、构建与最终 CSS Prettier 通过，交互未做 UI 测试 |

最终范围为产品/测试 19 文件，过程记录 6 文件，共 25 文件；无授权范围外的产品改动。未执行 Git 写入。

## Acceptance results / 验收结果

| 验收 ID | 结果 | 证据或待确认项 |
| --- | --- | --- |
| A01 | 已实现，UI 未验证 | 直接单选目标逻辑测试通过，composer 第三块集成 |
| A02 | 开发检查通过 | provider 分页/隐藏/游标/空值测试；实际只读查询返回 13 项 |
| A03 | 开发检查通过，真实写入未验证 | 成员绑定、会话身份/cwd、effort 测试；调用链无轮次/队列操作 |
| A04 | 开发检查通过，真实写入未验证 | 拒绝/未知/读取确认及失败只读刷新测试 |
| A05 | 开发检查通过 | 作用域变化、A→B→A、重复写保护测试，发送路由保持原有实现 |
| A06 | 通过 | 后端/前端全套开发检查，UI 测试按用户要求不运行 |
| A07 | 已实现，UI 未验证 | 同行及共享 routing 样式，Toast 测试，无额外后续轮次描述 |
| A08 | 已实现，UI 未验证 | 前四项及额外项选中计算测试；Popover 完整列表，无刷新/“当前” |
| A09 | 已实现，UI 未验证 | 模型区域出现时覆盖成员行 flex-grow |
| A10 | 开发检查通过，tip 体验未验证 | API 原始四字段，model 标签与 displayName title |
| A11 | 已实现，UI 未验证 | 模型与话题/成员选中态共用背景/边框规则 |

## Check results / 检查结果

全套检查完成于 2026-11-16 07:41；最后一行样式修正的格式/构建复验完成于 07:45。

| 命令 / 检查 | 实际结果 | 未运行原因 |
| --- | --- | --- |
| uv run --locked pytest tests/unit -q | 428 passed | — |
| uv run --locked mypy src tests | 213 files 无问题 | — |
| uv run --locked ruff check . | 通过 | — |
| uv run --locked ruff format --check . | 355 files 已格式化 | — |
| web: pnpm run typecheck / lint / format | 均通过 | — |
| web: pnpm run test -- --reporter=default --silent=false --no-color | 25 files、177 tests 通过，无测试警告 | — |
| web: pnpm run build | 全套及收尾复验均通过；有主 chunk 体积警告 | — |
| web: pnpm exec prettier --check src/domains/room/room.css | 最终样式通过 | — |
| git diff --check | 通过 | — |
| 浏览器/UI 测试 | 未运行 | 用户要求自行测试 |
| 真实会话模型更新 | 未运行 | 避免开发检查改变用户工作会话，实际写入尚待确认 |

## Risks and incomplete items / 风险与未完成项

- 悬浮浮窗、紧凑间距、选中样式及 tip 的实际观感待用户 UI 检查。
- 真实会话的空闲/忙碌状态模型切换未实测。协议依据本机 0.169.0 schema；只读目录已经实测，模拟测试覆盖后续轮次配置和确认路径。
- 其他客户端仍可在确认读取后再次修改模型，当前选中反映最后一次确认的配置。
- 生产构建主 chunk 约 1102kB，保留大于 500kB 的既有警告；未在本功能中改造打包。

## Conclusion / 结论

Implementation 已完成，T01–T03 交付均接受，必要开发检查通过。整体 Verification 保持 Draft，待用户审查界面与实际会话使用结果；本记录不包含 UI 或真实模型写入的通过承诺。
