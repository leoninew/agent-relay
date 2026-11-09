# 计划：固定用户成员与统一消息路由
最后修改时间: 2026-11-09 16:08:16

## 审查状态

Accepted

## 意图依据与授权

依据 [意图](../intent/20261109-user-member.md) 的 A01–A06。用户已授权记录任务后实施；本计划覆盖必要开发检查，不额外推进独立的整体验证阶段。

## 技术设计

- Member 增加 kind，区分 human 与 agent；human 不绑定 sessionId，agent 必须绑定有效会话。房间内固定用户 ID 为 user，名称为“你”，不可编辑或删除。
- SQLite 新增前向迁移，允许用户成员的空 session_id，补齐现有房间用户；重建成员表时先复制所有直接引用表，再按子表到父表顺序替换，始终启用外键，并恢复唯一索引和事件触发器。旧空发送者与 console_recipient 消息转换为 user 成员引用，保持 publication_id 的幂等查找。
- 消息统一使用 senderId、mentionedMemberIds 和 recipientIds；移除新引入的 consoleRecipient/to_console 特例。接收对象验证涵盖所有成员，Delivery 只为 kind=agent 且绑定会话的接收人创建。
- 成员目录返回成员类型，Codex 会话发现和观测仅处理 Agent。用户在成员列表置顶，只显示“你”；发送框不提供给自己发消息的选项，详情按真实接收人展示，用户无会话投递状态。
- 发给用户的消息在房间时间线可见；保留既有话题筛选时显示明确发给用户消息的行为。Agent 上下文继续遵守原订阅与接收范围。

## 实施步骤与预期文件

1. 记录意图与计划，补充迁移、成员类型和固定用户；范围为 migrations、room_models、room_store、room_queries、room_service。
2. 调整 Agent 路由、会话发现、成员目录、CLI/MCP 与 skill，删除独立 console 接收字段；范围为 member_*、client、cli、mcp_server、delivery_service 和插件 skill。
3. 调整 MemberPanel、MemberAvatar、RoomComposer、MessageTimeline、MessageDetails、前端 API 类型与必要样式，统一称谓。
4. 补齐用户固定性、单独与混合接收、实际队列调用隔离、目录和界面回归；执行项目已有检查入口并记录结果。按用户后续要求不新增迁移单元测试。

## 子任务与协调

不适用；当前会话执行单任务，不分配其他会话。保留已有暂存的 pnpm/Node 迁移及其他未提交修改，不进行 Git 提交。

## 开发检查

- 后端运行成员、路由、持久化、目录、API、CLI/MCP 和队列相关 pytest，以及 mypy、Ruff。
- 前端执行现有 pnpm test、typecheck、lint、format 入口；复核真实开发页面时只执行读取和必要界面操作，不向真实 Codex 会话发送测试投递。
- 重点证据：用户专属消息没有 deliveries，worker 无可认领任务，混合消息仅调用真实 Agent 会话；历史数据库迁移后通过 foreign_key_check。

## 风险与回滚

迁移前备份实际开发数据库；使用实际开发库升级及 dbtalk 外键检查确认 schema。API 与 MCP 契约变化需重新加载对应进程后生效，不自动重启当前 Codex。数据库采用已有仅向前迁移约定；需要回退时恢复迁移前备份及对应代码。

## 实施记录

2026-11-09 15:49:18：意图与计划已按用户授权记录并接受，开始实现。开发检查和实际偏差将在完成后补充。

2026-11-09 16:06:17：实现及必要开发检查完成。

- 实际变更覆盖计划模块，并补充 `docs/design/terminology.md` 与迁移目录手册的对应契约；未扩展根 README，未修改 Node 版本、全局配置或独立浏览器 MCP 项目。
- 固定用户在房间创建时持久化，历史房间通过迁移补齐；成员模型和数据库约束禁止用户绑定会话，业务层禁止编辑或移除用户。
- 仅发给用户的消息具有真实 recipientIds，但没有 Delivery；混合接收只为 Agent 创建 Delivery。队列认领额外要求目标为 Agent 且会话绑定一致。
- 前端成员列表置顶“你”，隐藏会话状态和管理操作；用户署名、头像、引用和 @ 展示统一，发送框排除自己。详情不为用户生成会话投递状态。
- 新增 `tests/test_user_members.py` 的三项业务回归，覆盖固定用户、单 Agent 发给用户时零队列调用、混合接收仅向其他 Agent 入队一次；不包含迁移单元测试。

## 开发检查结果

| 范围与命令 | 结果 |
| --- | --- |
| 项目根 `uv run --locked pytest`，选择 routing、store、member_sessions、member_context、member_publish、delivery_service、room_api、room_queries、cli、mcp_server 十个相关测试文件 | 首次 92/94 通过；一项旧成员数预期已更新，另一项出现 SQLite database is locked，见下方复跑 |
| 项目根 `uv run --locked pytest tests/test_room_api.py::test_member_creation_rejects_foreign_topic_and_duplicate_name tests/test_delivery_service.py::test_web_publications_reach_original_sessions_and_results_survive_restart -q` | 2/2 通过；锁竞争问题未扩大为本次修复范围 |
| 项目根 `uv run --locked pytest tests/test_user_members.py -q` | 3/3 业务回归通过 |
| 项目根 `uv run --locked mypy src tests` | 63 个源文件通过 |
| 项目根 `uv run --locked ruff check .` 与 `uv run --locked ruff format --check .` | 通过，107 个文件符合格式 |
| web 下 `corepack pnpm --config.engine-strict=false test` | 22 个测试文件、79 项测试通过 |
| web 下同一 pnpm 入口的 `typecheck`、`lint`、`format` | 全部通过；仅覆盖本次检查命令的 engine-strict 配置，未改变项目或运行环境 |
| `git diff --check` | 通过 |
| dbtalk 检查实际开发库 | revision 为 user_member，foreign_key_check 无违规；原有 2 个房间、7 条消息、6 条投递保留，成员由 1 增加为 3（每个房间新增固定用户） |
| 已运行 API 与 Chrome 页面读取 | 成员列表置顶“你”，旧用户消息署名及引用为“你”，第 7 条 Agent 消息显示 @你、recipientIds=[user] 且 deliveries=[]；页面不显示管理员或独立 console 接收标签 |
| `uv run --locked python scripts/install.py plugin check/apply/list --codex`（分别执行） | 本地 Agent Relay 插件预检、刷新、安装状态核对通过，已安装 skill 与仓库源文件哈希一致 |

## 交付边界

API 与前端已在运行中的开发服务上生效。MCP 工具定义及 skill 已更新，并通过原生插件入口同步到本地 Codex；已加载的 MCP 进程和会话说明需重新加载后采用新参数，本次没有重启当前 Codex 会话。未创建 Git 提交。未进入独立的整体 Verification 阶段。
