# Verification / 验证：聊天 Skill 引用与投递
最后修改时间: 2026-11-12 08:16:13

## Review status / 审查状态

Draft

## Intent alignment / 意图对齐

- 按最新需求，`$` 只展示 Skill；房间打开时预载目录，本地搜索、键盘选择和引用标签已接通，用户确认“界面测试无问题”。
- 引用随消息 JSON 保存、重放及恢复；服务端解析为原生输入。后端已有 MCP 引用契约继续兼容，前端不查询或展示 MCP 候选。

## Plan alignment / 计划对齐

- 采用计划修订 6：按用户授权就地合并未发布迁移，保留最终 head；测试仅保留单层单测，迁移使用离线 SQL 核对。
- 审查基线为 HEAD `10cbb78045d0d7dd09cf197d36007af01df8fb11` 上的未提交工作区；未执行 Git 暂存、提交或推送。

## Task deliveries and integration / 子任务交付与集成

| ID | 当前有效交付位置 | 必要检查与审查证据 | 集成与基线核对 | 验收归属与结果 |
| --- | --- | --- | --- | --- |
| T01 | application/capabilities、Codex catalog、HTTP capability routes | 目录转换、安全字段与错误单测 | T03/T04 使用同一目录及 ID 契约 | A02、A03 通过 |
| T02 | message/domain/persistence、0002_capabilities_json | 消息规范化、重放单测及离线 SQL | `capabilities` 沿消息和投递契约传递 | A04 通过，数据库不在本轮测试范围 |
| T03 | RoomComposer、RoomPage、useRoomCapabilities、CapabilityTags | 轻量目录/API 单测、build、用户界面验收 | 与 T01/T02 类型一致；仅列 Skill | A01、A02、A04 通过 |
| T04 | delivery ports/service、Codex driver | 14 项能力投递 adapter 单测及应用单测 | 根据已存引用生成原生输入 | A05、A06、A07 在替身验证范围通过 |

## Corrections and scope / 修复与范围

| 对齐依据 | 发现的偏差 | 实际修复 | 复验结果与证据 |
| --- | --- | --- | --- |
| A01、A04 | 连续 v-model 更新覆盖已选引用 | 正文和引用一次写入草稿，再恢复光标 | 用户界面验收通过 |
| 用户 `$` 仅列 Skill | 候选及预载包含 MCP | 删除前端 MCP 请求、缓存、候选及提示 | 类型、lint、build 与界面验收通过 |
| 用户合并未发布迁移 | 0002 先建关系表，0003 再转 JSON | 合并为 0002，直接增加 JSON 列，head 不变 | history/heads 只有一个 head，离线 SQL 无中间表操作 |
| 用户测试边界 | 剩余集成脚手架依赖已删除 support，使全量类型检查失败 | 删除 4 份失效脚手架及无用 marker，保留单测 | 全量 mypy、Ruff 和 177 项单测通过，未增加忽略规则 |

- 未恢复已删除的数据库测试、共享支持目录或 UI 测试；README、迁移指南及架构测试入口同步清理。

## Acceptance results / 验收结果

| 验收 ID | 结果 | 证据或未满足原因 |
| --- | --- | --- |
| A01 | 通过 | 用户确认界面无问题，Tab/Enter 选择丢引用问题已修复 |
| A02 | 通过 | 项目缓存、预载、部分失败与重试由轻量目录单测覆盖 |
| A03 | 通过 | catalog 单测核对稳定 ID、安全工具摘要及敏感字段不外泄 |
| A04 | 通过，限本轮范围 | 契约/规范化/重放单测和源码读写映射核对；JSON 约束、默认值经离线 SQL 核对，不运行数据库测试 |
| A05 | 通过，单测范围 | 原生 Skill/mention 载荷、Relay Skill 去重、拒绝与 unknown 分类由内存 RPC 替身验证 |
| A06 | 通过，单测范围 | 每个目标身份、状态、CWD 及能力重新核验；失败不重复 add/start |
| A07 | 通过 | 以下检查全部完成，遵守无真实 SQLite、跨层及 UI 测试约束 |

## Check results / 检查结果

| 命令 / 检查 | 实际结果 | 未运行原因 |
| --- | --- | --- |
| `uv run --locked pytest tests/unit` | 177 passed，1.78s | — |
| `uv run --locked mypy src tests migrations` | 140 files 通过 | — |
| `uv run --locked ruff check .` / `ruff format --check .` | 通过，220 个 Python 文件格式正确 | — |
| `alembic history` / `heads` / `upgrade queue_deleted_20261110:head --sql` | 基线直接到唯一 head，仅增加消息列并更新版本 | — |
| `corepack pnpm build` | vue-tsc 与生产构建通过 | — |
| `corepack pnpm lint` / `format` | 无错误，格式通过；1 条既有 v-html 警告 | — |
| 目录逻辑及 roomApi 轻量单测 | 同一前端版本此前 13 passed，17ms | 前端代码未再变化，不重复执行 |
| 用户界面验收 | 用户反馈“界面测试无问题” | — |
| SQLite/跨层/自动 UI/真实 Codex 队列测试 | 未运行 | 用户限制及既定授权边界 |
| `git diff --check` | 通过 | — |

## Risks and incomplete items / 风险与未完成项

- 保留既有 Markdown v-html lint 警告及 589kB 构建 chunk 提示；未扩大本轮功能范围处理。
- 本轮迁移仅离线核对，不对真实数据库执行；已到最终 head 的开发库版本标记保持兼容。真实队列提交未主动操作，替身测试不作为真实环境运行承诺。

## Conclusion / 结论

- T01–T04 的既定开发和验证工作完成，用户界面验收通过；修复后源码、迁移和单测检查通过。
