# Task / 子任务 T04：添加成员表单角色单选
最后修改时间: 2026-11-18 22:25:42

## 审查状态

Accepted。方案接受与交付接受分别记录。

## 父任务与权威记录

- [总意图](../../intent/20261118-member-role-prompts.md)；[权威总计划](../../plan/20261118-member-role-prompts.md)；方案修订 1。

## 目标与验收

A03/A06：添加成员时可选择一个角色或清空；角色目录为空、加载失败或选中角色失效时，能恢复或不选角色继续。其他表单字段、既有成员编辑和消息状态展示保持不变。

## 范围与输入

- 消费 T02 已接受并可访问的 `MemberRole`、`listMemberRoles()` 和角色错误翻译，以及 T03 的 `roleId` 创建契约；派发时记录版本。
- 修改范围：`RoomSetupDialog.vue`、必要的 `RoomPage.vue` 接线、`roomApi.ts` 创建类型、角色选择的中英文文案和 Web 测试。复用角色 API 客户端，不改设置页或后端。

## 技术设计与实施

1. 仅在添加成员模态窗展示角色单选，含「不选择角色」选项；默认不选。用现有表单风格的单选控件，选择值是一个角色 ID，不传正文，不在前端另发消息。
2. 角色目录随添加模态窗打开独立加载；加载失败在角色区域展示可重试状态，未选角色仍可提交。无角色时显示空状态；关闭或切换目标频道时丢弃旧选择和晚到的读取结果。
3. 选中角色时追加 `roleId`，未选时省略该字段。服务器返回 `member_role_not_found` 时保留其余输入并刷新可选角色，允许重选或清空后提交；继续使用现有「成员已添加」成功提示，不增加提示词反馈。

## 检查与风险

- Web 定向测试：角色选择、清空、正确请求体、未选兼容、目录为空或加载失败、被删除时保留输入、关闭或切换后清理状态。运行 Vitest、`typecheck` 和改动范围 ESLint/Prettier。
- 整体验收确认角色提示词通过原有聊天更新出现，不从成员创建响应生成第二条消息；不改变归档会话的过滤。

## 交接、进展与交付

- 分配 `MRP-T04-01`，执行者高级开发 `member-afabe09f28af`，方案修订 1，授权 #321。实际工作区 `D:/SourceCodes/mywork/conflua`，基线 `315b40b` 加总计划中已接受的 T01、T02、T03 指纹。先读总计划和协作契约，在本文写接收记录；只修改成员选择及其文案、类型和测试。
- 接收（22:11:11）：已核对 #346、总计划登记、T02 的角色列表客户端和双语错误以及 T03 的 `roleId` 字段与错误响应。仅修改添加成员表单和相关客户端类型、文案、定向用例；不另发消息，不改投递状态、不暂存或提交。
- 检查候选：`web/src/domains/room/RoomSetupDialog.vue`、`RoomPage.vue`、`useMemberRolePicker.ts`，`web/src/services/roomApi.ts`，`web/src/i18n/en.ts`/`zh-CN.ts`（仅追加 `setup` 键，保留 T02 文案），`web/tests/domains/room/useMemberRolePicker.test.ts` 和 `web/tests/services/roomApi.test.ts`。
- A03/A06：添加时独立加载角色目录，单选、默认不选且可清空；目录为空、请求失败或仍在加载不阻止无角色提交；失效角色保留其他字段、提示并刷新目录。通过创建成员请求传角色 ID，不另发消息或展示提示词专属状态。关闭或切换频道丢弃选择与旧响应。
- 建议运行新增选择逻辑用例、`tests/services/roomApi.test.ts`、`tests/i18n.test.ts`、Web typecheck、八文件 ESLint/Prettier；`git diff --check` 通过，等待中级开发复核。整体验收由架构师协调。
- 交付（`MRP-T04-01`）：上述八文件，基线 `315b40b` 加总计划中已接受的 T01、T02、T03；八文件组合 SHA256 `fad84fa9dcec4a4fcbb16243c46b0e9df9782ce672353b282ecc887c0a8de503`（逐文件 SHA256、双空格和相对路径，按 #351 中八行顺序换行拼接）。未暂存或提交；两个语言文件在已接受的 T02 版本上各增两个 `setup` 键。
- 复验依据 #351：中级开发按 #350 仅调整 `RoomSetupDialog.vue` 的属性顺序并格式化该文件及 `roomApi.test.ts`；三个 Vitest 文件 22 项通过，Web typecheck、八文件 ESLint/Prettier 和 diff check 全通过。#352 全量复验使用 Makefile 等价命令：后端 pytest 524 项通过，Ruff lint/format、Mypy 通过；Web Vitest 250 项通过，typecheck、ESLint、Prettier 通过。Windows 缺少 `make`，`uv run --locked` 同步缺失的锁定依赖后脚本启动器失败，检查直接用 `.venv` / `pnpm` 完成；没有锁文件变更。
- 未在真实 Codex 会话投递或修改在用数据库；小屏、双语、键盘和浏览器集成由架构师在整体验收记录。提交成功时继续由既有消息更新机制显示提示词，不另建或发送消息。
- 本文用于接收、进展、阻塞和交付记录；交付附实际变更、对应验收证据、可访问版本、检查及剩余风险。
