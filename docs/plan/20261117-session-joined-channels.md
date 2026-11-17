# Plan：添加成员时展示会话已加入的频道
最后修改时间: 2026-11-17 20:34:25

## 审查状态与依据

Accepted。依据 [意图](../intent/20261117-session-joined-channels.md) 与本次实施请求。

## 技术设计与修改范围

- 在 `application/dto/members.py` 定义仅含 ID、名称的频道引用，候选会话新增 `joinedChannels` 数组，保留当前频道 `memberId` 的原有语义。
- 在 RoomRepository 及 SQLAlchemy 读取实现新增按当前聊天室批量读取活跃成员的频道归属。通过频道和成员的聊天室、频道复合条件关联，排除已移除成员及非活跃频道；默认频道优先，其余按现有频道顺序返回。
- MemberService 在候选读取的同一 read scope 获取当前频道成员及跨频道归属，不增加 Codex 请求，不逐会话查询。
- 前端同步类型，在 `RoomSetupDialog.vue` 的可加入会话卡片增加辅助文本与可换行频道标签，补齐中英文空状态；不可用会话不显示频道归属，所有会话卡片不显示会话 ID。ID 仍用于选中和提交。
- 补充应用层归属映射、持久化查询范围及 API 数据保留测试；无 schema 或 HTTP 错误契约变更。

## 实施步骤

1. 扩展候选 DTO、Repository 端口、SQL 查询与服务映射，覆盖 A01、A03、A04。
2. 按用户后续要求调整会话卡片展示，覆盖 A02、A05，保持既有选择和去重规则。
3. 运行相关后端与前端单测，再执行项目既有类型、lint、格式检查，记录实际结果。

## 子任务与协调

不适用。当前会话直接实施，在本计划记录交付与开发检查，不启动子 agent。

## 检查、风险与恢复

- 使用项目已有 `uv run --locked pytest` 与 `corepack pnpm test` 入口运行相关单测，随后执行 `make check` 和常规单测。
- 对照实际 diff 检查标签换行及辅助文字层级；浏览器检查视本地服务是否可用，不将静态检查宣称为交互验证。
- 保持单次批量查询、聊天室隔离、当前频道 `memberId` 语义；撤回本次字段、读取和展示即可回滚，无迁移或数据写入要求。

## 实施交付

- 第一轮已完成 DTO、Repository 端口、单次跨频道查询与候选映射；当前频道去重与加入请求保持原样。后续用户要求仅在可加入会话展示频道，并从两类会话中移除 ID，现按该要求调整展示。
- 当前工作区交付，无数据库迁移，未暂存或提交。工作区同时存在其他会话的 macOS 打包相关改动，本任务未修改其实现。
- 后端：`uv run --locked python -m pytest tests/unit` 476 项通过；`uv run --locked python -m mypy src tests` 209 个文件通过；`uv run --locked python -m ruff check .` 及 `ruff format --check .` 通过。本机虚拟环境的 pytest/mypy 脚本 shebang 仍指向旧目录，因此使用同环境的 `python -m` 调用，未修改或安装依赖。
- 前端（`web/`）：`corepack pnpm test --reporter=default --silent=false --no-color` 216 项通过，无测试警告；`corepack pnpm run typecheck`、`lint`、`format` 通过。`git diff --check` 通过。
- 浏览器开发检查：在现有本地服务打开添加成员模态窗，确认可加入与不可用会话的真实空状态；使用一次性前端响应替身展示 API、Web 和长名称三个标签，截图确认换行正常。替身已自行注销并刷新恢复真实数据，未创建或添加任何成员、频道。
- 范围无偏差；Implementation 及必要开发检查完成，独立整体 Verification 阶段未启动。
- 后续展示调整已完成：仅可加入会话展示频道，两类会话均不展示 ID；选择仍以 ID 绑定，未修改提交逻辑。浏览器确认可加入、不可用及已选择状态的实际展示；前端 216 项测试、typecheck、lint、format 和 `git diff --check` 均通过，未重新运行与本轮无关的后端检查。
