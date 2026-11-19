# Task / 子任务 T03：添加成员时写入普通消息
最后修改时间: 2026-11-18 21:48:19

## 审查状态

Accepted。方案接受与交付接受分别记录。

## 父任务与权威记录

- [总意图](../../intent/20261118-member-role-prompts.md)；[权威总计划](../../plan/20261118-member-role-prompts.md)；方案修订 1。

## 目标与验收

A04/A05：添加带角色的成员时，原子保存成员和一条普通定向消息，只向该成员发送。不选角色、添加失败或重复绑定时不产生额外消息；角色变更不改写历史。

## 范围与输入

- 消费 T01 已接受并可访问的角色表与 `MemberRoleService.get(role_id)` 请求事务读取；派发时记录版本。
- 修改范围：成员 DTO、成员创建应用流程、创建路由依赖、必要的普通发布逻辑提取及测试。不得改投递 worker、Codex driver、消息状态、Web 或迁移。

## 技术设计与实施

1. 在 `CreateMember` 添加可空 `roleId`，不改 `UpdateMember` 或 `CreatedMember`。只将创建成员路由切换为请求级 `RoomStore`，保留其他成员操作及独立服务依赖。
2. 继续按现有流程读取并复核可用会话，完成外部只读核验后进入数据库写入；在写作用域复核添加条件，若有 `roleId` 则读取角色当前版本。用角色模板正文创建 `CreateMessage`，发布 ID 由服务端生成，不接受客户端正文。
3. 先写成员，再在同一写作用域执行普通发布。将 `MessageService.post_message` 的写入体提取为接受当前 `RoomData` 的应用层方法，普通入口仍使用原有 `store.write()` 包装。创建成员直接传入当前作用域，避免独立或嵌套提交；用默认固定用户身份、仅新成员的 `mentionedMemberIds` 和空 `topicIds`。
4. 继续使用普通消息的持久化、事件和待投递记录。任何数据库写入失败都回滚整次请求；添加成功后由现有后台逻辑处理，不等待 Codex，也不增加专用反馈字段。

## 检查与风险

- 使用真实 SQLite 请求事务的集成用例证明：成功只生成一条消息且只有新成员为投递目标；同话题其他成员及其他频道不收到；模拟消息写入失败时成员、消息、待投递项和事件都回滚；重复提交同一会话不重复发送。
- 覆盖 `roleId` 缺省/为空、错误类型、角色删除、会话不可用，以及编辑成员不触发发送。跑 `tests/unit/application/test_member_binding.py`、`tests/unit/application/test_message_service.py` 和新增 HTTP 事务用例，及 Ruff/Mypy；普通发布行为保持原样。

## 交接、进展与交付

- 分配 `MRP-T03-01`，执行者高级开发 `member-afabe09f28af`，方案修订 1，授权 #321。实际工作区 `D:/SourceCodes/mywork/conflua`，基线 `315b40b` 加 T01 已接受交付（19 文件指纹 `907909580a59bfbb78cdd0545e45bb83d22ee073`）。先读总计划和协作契约，在本文写接收记录。
- 接收（21:36:07）：已核对 #333、总计划登记及 T01 提供的请求事务读取。只修改 `CreateMember`、创建成员请求范围、普通发布写作用域和后端用例；不改既有投递、Web、迁移或无关 CLI。
- 检查候选：`src/conflua/application/dto/members.py`、`src/conflua/application/members/service.py`、`src/conflua/application/messages/service.py`、`src/conflua/interfaces/http/members/dependencies.py`、`src/conflua/interfaces/http/rooms/routes.py` 和 `tests/unit/interfaces/test_member_role_binding.py`。创建路由使用同一请求事务，角色在写作用域中读取，`MessageService.post_in_scope` 复用普通发布逻辑。
- 验收用例覆盖当前模板正文、仅新成员和当前频道投递、历史不随模板变化、缺省/空角色、错误类型、删除、会话不可用、重复绑定、编辑不发送，以及 SQLite 在待投递事件写入时失败导致整次回滚。建议检查新增用例、`test_member_binding.py`、`test_message_service.py` 和 T01 `test_member_roles.py`，再跑上述六文件 Ruff/Mypy。`git diff --check` 已通过；尚未收到独立检查结果。
- 交付（`MRP-T03-01`）：上述六文件，基线 `315b40b` 加 T01 已接受指纹 `907909580a59bfbb78cdd0545e45bb83d22ee073`；交付组合 SHA256 `ec3461acf621623014bf2c7f36606fd3c78a77eae82dd95a1263f372eabdd05e`（逐文件 SHA256、双空格和相对路径，按 #338 中六行顺序换行拼接）。未暂存或提交。
- 复验依据 #338：中级开发按 #337 只格式化新增事务测试，四文件 pytest 37 项通过，六文件 Ruff lint/format、Mypy 及 `git diff --check` 全通过。未运行全量检查、在用数据库迁移或真实 Codex 投递；临时库确认普通消息、待投递记录及事件原子保存。
- T04 提交契约：创建时可省略 `roleId` 或提供一个角色 ID；`null` 不发消息；过期角色返回 `404/member_role_not_found`，请求不落库；成功继续使用原成员响应，不另发提示词。
- 本文用于接收、进展、阻塞和交付记录；交付附实际变更、对应验收证据、可访问版本、检查及剩余风险，明确提供 T04 所需的提交契约与错误响应。
