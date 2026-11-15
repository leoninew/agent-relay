# Plan / 计划：忙碌成员打断
最后修改时间: 2026-11-15 22:08:31

## Review status / 审查状态

Accepted

## Intent basis / 意图依据

- [意图](../intent/20261115-member-interrupt.md)，验收 A01—A05。
- 工作基线：`2f6fb02dcced74d2143a3382883057cba7a9c813`，开始时工作区干净。

## Technical decisions / 技术设计与决策

- 新增 `POST /api/room/{room_id}/channel/{channel_id}/member/{member_id}/interrupt`，无请求正文。沿用频道范围 `MemberServiceDependency`、独立 RoomStore 和统一异常处理。
- 返回自然 DTO `{status, turnId}`：`interrupted` 为匹配目标轮次已确认中断；`not_running` 为会话已空闲或目标已自然完成/失败。未定位轮次时 turnId 为 null；不提供中间成功状态。
- `MemberService` 查找本频道未删除 Agent 及其 session_id，退出读取作用域后调用扩展的 SessionDriver；CodexDriver 复用目标身份/目录/可用性校验和 `_active_turn`。不信任前端 presence，不写本地假状态。
- 只调用一次 `turn/interrupt`。明确不支持或拒绝转成 409 稳定错误码；写入前读取失败为 503 元数据不可用；提交超时/断连为 503 `session_interrupt_unknown`，不自动重试。
- 空回执后在同一连接同步检查最近 20 个轮次，确认总预算为 min(RPC timeout, 5 秒)，单次确认 RPC 最长一秒，检查间隔 0.1 秒；始终匹配原 turnId。确认读取失败或预算耗尽仍无法确认时返回 503 `session_interrupt_unknown`；不依赖当前 ProxyRpc 丢弃的通知，不自动中断新轮次。
- 前端抽取 `useMemberInterrupt` 管理按房间/频道/成员隔离的提交防重、反馈和状态刷新。文字按钮作为成员筛选按钮的兄弟节点，定位在原状态位置；仅行 hover 或打断按钮自身 focus-visible 时隐藏“忙碌”并显示“打断”，整行 focus-within 不触发动作显示，选中状态无影响。文字始终不变，保留无障碍名称，复用设计 token，不改变筛选与排序，不追加图标或“打断中”。
- “打断”固定使用 destructive 红色，背景透明，无悬浮背景变化；去掉按钮水平内边距，按状态文本右边缘对齐。成员行内切换鼠标目标时维持原有行悬浮背景，避免经过兄弟按钮时背景反复淡入淡出。
- 禁用样式只改变 cursor，不单独设置 opacity，避免在非悬浮状态覆盖默认隐藏导致“忙碌”和“打断”重影。
- 成功/已空闲分别显示不同提示，未知通过错误契约反馈。完成后读取会话和元数据刷新真实 presence；刷新失败单独反馈，不把已完成打断报告为发送失败。页面切换后忽略旧操作反馈。
- HTTP 错误复用现有契约和日志；不返回上游异常原文，不扩展认证或限流范围。

## Implementation steps / 实施步骤

1. 扩展动作 DTO、SessionDriver 和 MemberService；新增频道 HTTP 路由（A02、A03）。
2. 实现 Codex 单次中断、有界目标确认和错误分类（A02、A03）。
3. 接入前端 API、composable、忙碌成员按钮、样式与中英文提示（A01、A04）。
4. 补充关键业务、适配、HTTP 与前端状态测试并运行已有检查入口，登记开发交付（A05）。

## Files to change / 修改范围

- `src/agent_relay/application/{dto/members.py,members/sessions.py,members/service.py}`。
- `src/agent_relay/infrastructure/codex/driver.py`、`src/agent_relay/interfaces/http/rooms/routes.py`。
- `web/src/services/roomApi.ts`、`web/src/domains/room/{MemberPanel.vue,RoomPage.vue,useMemberInterrupt.ts,room.css}`、中英文词典。
- 对应 `tests/unit`、`web/tests`、本功能三阶段文档及现有 Codex 能力说明。

## Tasks and coordination / 子任务与协调

不适用；单会话直接实施。接收、进展与交付写入本计划，不建立 DAG 或额外 task；重要结论经 Agent Relay 发给用户。

## Verification plan / 检查与验证安排

- 后端：目标与频道绑定、删除/人类成员、无事务跨 RPC、空闲/运行/身份目录异常、明确拒绝、提交未知、原轮次确认与新轮次并发边界。
- HTTP：通过真实路由与依赖注入检查频道作用域、成功 DTO、404/409/503 及 requestId/安全消息。
- 前端：按目标防重、不同成员独立操作、切换频道隔离、同步结果和未知错误不重试、状态刷新失败独立反馈；沿用 i18n 键一致性检查。
- 必要开发检查：项目已有 pytest、vitest、mypy、ruff、vue-tsc、ESLint、Prettier 与前端构建；先聚焦改动，再执行相关全量入口一次。
- 不将随机不存在会话探测或 mock 测试表述为真实运行轮次中断成功；用户明确自行进行 UI 测试，代理不执行 UI 测试。真实宿主中断行为尚未实测。

## Risks and recovery / 风险与恢复

- Codex 请求与轮次结束存在竞态；始终提交原 turnId，返回实际可确认状态，不承诺队列停止或副作用回滚。
- 不增加数据库迁移；回滚本次接口和 UI 改动即可恢复此前行为。

## User review notes / 用户审查记录

- 2026-11-15：按用户“记录任务并实现”的授权接受本计划并进入 Implementation；无额外产品取舍。

## Implementation delivery / 开发交付

- 已完成 Implementation，未进行 Git 提交。交付为基线 `2f6fb02dcced74d2143a3382883057cba7a9c813` 上的本功能工作区差异，含新增文件。
- 后端已接入频道范围同步打断接口、成员绑定校验、单次原轮次中断、同步确认以及安全错误分类；确认读取异常保留 cause 供日志诊断。
- 前端已接入原状态位置的红色“打断”文字：仅鼠标悬浮或动作自身键盘焦点显示，无背景、无中间文案；成员选中不触发替换；禁用只防重，避免透明度规则使隐藏动作显露。
- 状态刷新与打断结果分开反馈，按房间/频道隔离旧结果；未清空队列或乐观设置空闲。
- 新增后端应用/适配/HTTP 契约测试和前端 composable 测试，扩展 API 路径序列化用例；未添加 UI 自动化测试。
- 实现过程中用户明确自行负责 UI 测试；代理仅检查用户提供的重影截图及代码，没有运行浏览器或 UI 测试。真实运行轮次中断、宿主后续队列行为仍未实测。
- 同期工作区出现 RoomSwitcher、频道选择与 channels store 等其他变更，保持原样，不计入本功能交付范围。

### 开发检查证据

| 时间 / 命令 | 结果 |
| --- | --- |
| 21:54 `uv run --locked pytest tests/unit -q` | 392 passed |
| 21:54 `uv run --locked ruff check .`、`ruff format --check .` | 通过；345 个文件格式符合 |
| 21:52 `uv run --locked mypy src tests` | 通过；208 个源文件 |
| 21:54 `pnpm run test -- --reporter=default --silent=false --no-color` | 23 个测试文件、159 项通过，无测试警告 |
| 21:52—21:54 `pnpm run typecheck`、`pnpm run lint`、`pnpm run format` | 全部通过 |
| 22:08 `uv run --locked pytest tests/unit/infrastructure/codex/test_interrupt.py -q` | 确认异常保留 cause 后复验：15 passed |
| 22:08 适配层 `ruff check` / `ruff format --check`、`git diff --check` | 通过 |
| 22:08 `pnpm exec prettier --check src/domains/room/room.css`、`pnpm run build` | 重影修复后通过；构建仍提示主 JS chunk 超过 500 kB，不属于本次范围 |

- HTTP 错误契约增量检查通过：新动作的 404/409/503、requestId 生成/透传、响应头和正文一致性、上游异常不泄露均有测试；前端继续使用既有 typed error 归一化。认证、限流和代理边界未变更，仍由既有基础设施负责。
- 最终关键源文件 SHA-256：`MemberPanel.vue` = `D6EE424BCA2AF44A24D5964ACCF4DA996235F2136D3D605F3AF464DA1C6234AC`；`room.css` = `8A867FCAE6340F8963145C2768861CBDC18AA94886459B879AD61AEC029912FC`；`driver.py` = `3FD640D7D91F2E02E6CF6F7D9A35D1B96CA8F3206D8BEEC1504FAD63A49CB3C7`。
- 当前无待修复的开发检查失败。整体 Verification 未启动；UI 测试由用户自行完成，后续结论写入验证记录。
