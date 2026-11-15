# Plan / 计划：单选成员模型展示与切换
最后修改时间: 2026-11-16 07:45:09

## 审查状态

Accepted，方案修订 5。依据用户“拆分任务，推进实现”及 seq259/261–263/267–270 接受修订意图与全部 task 方案。

## 意图与技术决策

- 意图：[单选成员模型展示与切换](../intent/20261115-member-model-selection.md)。
- 本机共享 daemon 0.169.0 的 schema 明确 `thread/read.model` 是已加载会话当前配置，非轮次遥测；可直接确认后续轮次设置，无需缓存通知。只读实测当前目录会话返回 provider `magpie`、model `group/gpt-6.1`、effort `xhigh`，按该 provider 查询返回 13 个非隐藏模型；默认 provider 列表曾返回 14 个，故必须按目标 provider 查询，不硬编码。
- GET `/api/room/{room}/channel/{channel}/member/{member}/model` 返回 `{sessionId, provider, currentModel, models:[{id, model, displayName, description}]}`。保留原始目录 ID 与模型值，以 `model` 进行选中和切换。处理分页、隐藏、重复身份和非法游标，未知当前模型保持 null 或原始真实值。
- PATCH 同路径，输入 `{sessionId, model}`，禁止多余字段；使用所选绑定 ID 防止成员重绑后切错会话。检查成员、频道、原会话 ID、目录、可用状态和 provider 目录后，只发一次 `thread/settings/update`。保留目标模型支持的当前 effort，否则随模型一起设置目录提供的默认 effort。不得操作轮次、输入或队列。
- 空回执不代表成功：更新后重新 `thread/read` 核对会话、目录、provider、model 与 effort；不匹配/超时返回 503 `session_model_update_unknown`。明确 RPC 拒绝为 409；读目录失败为 503，安全摘要与原始异常分离，沿用 `{code,error,requestId}`。
- 前端在 composer 的话题、成员之后加模型区域，模型按钮使用单选 `aria-pressed`，复用现有字号/选中色。目标只由直接选择的唯一有效 Agent + sessionId 决定；话题、左侧筛选和最终 recipients 不参与目标计算。
- seq259 修订：模型作为同一 flex 行的第三块，复用 routing-row 分隔符和 routing-choice，窄屏沿用原路由自适应换行；删除强制独占整行、额外标题和后续轮次描述。失败通过 Toast（保留 requestId），成功仅更新选中状态，无现场错误。
- seq261/262 及修订 5：只展示目录前 4 项，超过 4 项用“...”触发 Reka Popover + Portal 展示完整可选列表（沿用列表项样式）。支持悬浮/焦点/点击打开，触发与浮窗之间延迟关闭；选择或操作目标改变时关闭。不显示刷新图标或“当前”字样。实际选中在前 4 项内高亮该项，否则高亮“...”，完整浮窗高亮实际项；未知或目录外值保持真实，不选默认值。目录失败后下一次移入模型区域可重新读取，仍只读、不重试写入。
- 只读调用新适配发现 `group/ds` 合法返回空 supportedReasoningEfforts 且默认 `none`；目录不能因其为空而失败。无 effort 选项时发送实际目录默认值，非空时检查默认属于支持集合。此兼容性修正纳入 T01。
- 使用独立 composable 管理加载、读取刷新、点击提交、错误、更新提示；作用域由 room/channel/member/session 组成，变化同步清空，代次令牌丢弃旧结果（包括 A→B→A）；禁止重复提交，失败只自动读取，不自动重试写入。未知更新结果明确提示并显示重新读取的真实模型。

## 实施步骤与修改范围

修订 5 确定：页面主文本和切换/选中值使用 model，tip 仅 displayName，目录原始 id 不替换成 model。T01 局部返工仍由 `model-T01-01` 执行并复验，T02 原执行者集成。Popover 替代 HoverCard 是因为后者会剥夺列表按钮 Tab 焦点。模型区出现时取消成员与模型 routing-row 的 flex-grow，保留同话题/成员的分隔符、项目间距及字号。选中态在同一个 CSS 选择器内共享背景和边框样式；不单独改变字色。

1. T01 修改 application DTO/port/service、Codex driver 与目录适配、频道 HTTP 路由及后端测试，输出上述接口。
2. 接受 T01 交付后，T02 修改 roomApi、模型 composable/模型行、composer、room.css、双语文案及前端非 UI 单元测试。
3. 接受 T02 后，T03 运行项目既有检查、核对 diff 与记录，形成实现交付及待用户 UI 检查说明。

## 子任务与协调

- 方案修订：5。
- 权威协调根：`D:/SourceCodes/mywork/agent-relay`。
- 仲裁会话：当前主会话（成员 `member-441729f2deb0`）。
- 阶段授权：用户最新“拆分任务，推进实现”；含 Implementation 必要检查，不启动子 agent、UI 测试或 Git 写操作。所有接收/交付记录由本会话写各 task。

| ID | 任务文档 | 直接前置任务与要求 | 预期交付与验收 | 意图验收归属 |
| --- | --- | --- | --- | --- |
| T01 | [会话模型接口](../task/20261115-member-model-selection/T01-session-model-api.md) | 无 | 安全读写接口、provider 分页、原始字段、真实确认及后端测试通过 | A02、A03、A04、A10 接口字段 |
| T02 | [输入框模型选择](../task/20261115-member-model-selection/T02-composer-model-picker.md) | T01 工作区接口经审查接受，后端针对性测试通过 | 原始 model 主文本、displayName tip、前四项/悬浮列表、紧凑对齐、共享选中态、Toast 及逻辑测试 | A01、A04、A05、A07–A11 |
| T03 | [集成开发检查](../task/20261115-member-model-selection/T03-development-checks.md) | T02 及传递前置均 accepted，最新工作区可读取 | 必要检查通过、实际风险与未运行项落盘 | A06 |

| ID | 执行状态 | 执行者 | 分配编号 | 工作基线 / 交付位置 | 仲裁结论 / 当前阻塞 |
| --- | --- | --- | --- | --- | --- |
| T01 | accepted | 主会话 | model-T01-01 | HEAD `9bb93db0f6f0b05d00b6e493862e739dc81d6b3a` + 修订 5 T01 diff | 07:44 最新字段/调用链复审接受；后端全套 428 tests、mypy、ruff 通过，见 T01 |
| T02 | accepted | 主会话 | model-T02-01 | 同 HEAD + 修订 5 T01/T02 diff | 07:44 接口/逻辑/共享样式复审接受；前端全套 177 tests、类型/lint/format/build 通过，见 T02 |
| T03 | accepted | 主会话 | model-T03-01 | 同 HEAD + 已接受 T01/T02 最新 diff 与收尾高度变量修正 | 07:45 开发检查和最终差异审查通过；样式格式/生产构建复验通过，Draft 验证记录已整理，见 T03 |

DAG：T01 → T02 → T03；ID 唯一，无自依赖、无环，A01–A11 均有归属。全部主会话串行写入；总计划与最终集成由主会话负责。

| 时间 | ID | 分配编号 | 执行者 | 动作与依据 |
| --- | --- | --- | --- | --- |
| 2026-11-15 22:37:30 | T01 | model-T01-01 | 主会话 | 用户授权覆盖；全部方案 Accepted，前置为空，分配并接收 |
| 2026-11-15 22:42:00 | T01 | model-T01-01 | 主会话 | running → submitted → accepted，34 tests/mypy/ruff 通过，调用链审查符合范围 |
| 2026-11-15 22:42:00 | T02 | model-T02-01 | 主会话 | unassigned → assigned → running，前置 T01 工作区可读且已接受 |
| 2026-11-15 22:48:00 | T01 | model-T01-01 | 主会话 | accepted → running，修订 2 兼容真实目录的空 effort；原执行者继续 |
| 2026-11-15 22:48:00 | T02 | model-T02-01 | 主会话 | 修订 2 接受 A07，暂停产品修改等待 T01 兼容修正复验后继续 |
| 2026-11-15 22:50:30 | T01 | model-T01-01 | 主会话 | submitted → accepted，35 tests 及新 driver 实际只读查询通过 |
| 2026-11-15 22:50:30 | T02 | model-T02-01 | 主会话 | 前置修订 2 已接受，恢复实施 |
| 2026-11-15 22:53:00 | T02 | model-T02-01 | 主会话 | 同执行者接收修订 3（seq261/262，A08）；T01 设计/交付不变仍有效，T03 检查涵盖新增前端范围 |
| 2026-11-15 23:15:00 | T01 | model-T01-01 | 主会话 | 修订 5，同执行者返工原始 id/model DTO；running，复验后接受 |
| 2026-11-15 23:15:00 | T02 | model-T02-01 | 主会话 | 修订 5，继续按 seq267/268/270 集成原始模型字段、区间距及共享选中态；待 T01 复验 |
| 2026-11-16 07:44:00 | T01 | model-T01-01 | 主会话 | 恢复后补齐修订 5 交付，依据全套 428 后端 tests、字段契约及调用链审查，submitted → accepted |
| 2026-11-16 07:44:00 | T02 | model-T02-01 | 主会话 | 核对最新前置，补齐最终交付；依据 177 前端 tests 及类型/lint/format/build，submitted → accepted；UI 未测 |
| 2026-11-16 07:44:00 | T03 | model-T03-01 | 主会话 | 前置已接受且工作区可读；unassigned → assigned → running，记录已有全套检查事实，复验收尾样式并完成交付记录 |
| 2026-11-16 07:45:09 | T03 | model-T03-01 | 主会话 | submitted → accepted；前置版本/最终 diff 核对通过，浮层高度变量对应 Popover，Prettier/build 复验通过；全套检查证据见 T03 与 Draft verification |

## 检查与恢复

- T01：pytest 新增应用/适配/HTTP 测试，覆盖无效目标、provider 分页、effort、拒绝/未知、安全契约；不改真实会话。
- T02：Vitest node 环境检查单选目标、A→B→A 过期响应、重复点击、失败后只读刷新、编码路由；不做 UI 测试。
- T03：`uv run --locked pytest tests/unit`、mypy、ruff check/format；web 的 typecheck、lint、format、test、build。只修复本次引入的问题。
- HTTP 契约复用现有统一 writer、typed client；新路由不引入认证/限流/网关边界。整体 Verification 和 UI 体验交由后续用户审查，必要开发检查照常完成。
- 风险：未修改真实会话验证模型切换，协议确认依赖本机 schema 与模拟测试；其他客户端可在读取后再次变更设置。回退本次局部 diff 即可，无数据库迁移；已成功切换的外部模型应通过相同入口显式恢复。

## 实现交付

T01–T03 修订 5 的实现交付均已接受。后端 428 tests、mypy 213 files、ruff check/format，前端 177 tests（25 files）、typecheck/lint/format/build 通过；最后的 Popover 高度变量修正另经格式检查和生产构建通过。构建保留主 bundle 大于 500kB 的警告，未扩大本次范围。没有 UI 测试、真实会话模型写入或 Git 写操作；已有暂存内容保持原状。整体 Verification 状态为 Draft，详见[验证记录](../verification/20261115-member-model-selection.md)，UI 体验由用户检查。
