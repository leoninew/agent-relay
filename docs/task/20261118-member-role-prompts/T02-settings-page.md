# Task / 子任务 T02：角色与提示词设置页
最后修改时间: 2026-11-18 22:01:31

## 审查状态

Accepted。方案接受与交付接受分别记录。

## 父任务与权威记录

- [总意图](../../intent/20261118-member-role-prompts.md)；[权威总计划](../../plan/20261118-member-role-prompts.md)；方案修订 1。

## 目标与验收

A02：从齿轮打开角色配置页，展示不分页表格；能新增、编辑、确认删除，能返回原频道，并保留齿轮现有功能。

## 范围与输入

- 消费 T01 已接受并可访问的迁移和角色 CRUD API；派发时记录实际版本。
- 修改范围：`AppMenu.vue`、路由、`web/src/domains/settings`、`web/src/services/memberRoleApi.ts`、角色相关中英文文案和 Web 测试。本任务拥有通用角色错误文案，不改添加成员表单或后端。

## 技术设计与实施

1. `/settings` 挂载角色设置页，从齿轮菜单进入。用路由状态传原频道的房间和频道 ID，返回时只构造站内命名路由；无原频道记录则返回聊天首页。保留语言和关于入口。
2. 使用现有设计 token 和表格样式：名称、提示词摘要、操作三列；摘要截断仅用于展示，编辑器加载完整正文。提供加载、空列表、失败和重试；不分页。
3. 复用 `AppDialog`、`AppInput` 和 `AppButton`。新增和编辑表单显示名称、提示词的字段错误、必填与多行输入；删除用现有确认样式，失败不移除列表行。提交期间阻止重复操作，成功后以服务端返回值更新列表并保持排序。
4. `memberRoleApi.ts` 导出 `MemberRole`、`listMemberRoles()` 及 CRUD 客户端，沿用 `apiClient`；本任务补齐 `member_role_name_conflict`、`member_role_not_found` 的 Web 翻译供 T04 使用。

## 检查与风险

- Web 定向测试：客户端请求、保存/删除错误与表格状态；运行 Vitest、`typecheck` 和改动范围 ESLint/Prettier。在整体验收中检查双语、长正文、小屏和模态窗键盘行为。
- 不让列表摘要替换原始正文，不从浏览器本地存储构造角色目录。

## 交接、进展与交付

- 分配 `MRP-T02-01`，执行者高级开发 `member-afabe09f28af`，方案修订 1，授权 #321。实际工作区 `D:/SourceCodes/mywork/conflua`，基线 `315b40b` 加 T01 已接受交付（19 文件指纹 `907909580a59bfbb78cdd0545e45bb83d22ee073`）。先读总计划和协作契约，在本文写接收记录。
- 接收（21:36:07）：已核对 #333、总计划登记及 T01 已接受版本。只修改设置页、导航、角色 Web 客户端、文案及定向用例；按协调安排先冻结 T03 检查候选，再实施 T02。
- 检查候选：`web/src/components/AppMenu.vue`、`web/src/router/index.ts`、`web/src/domains/settings/SettingsPage.vue`/`useMemberRoleSettings.ts`、`web/src/services/memberRoleApi.ts`、`web/src/i18n/en.ts`/`zh-CN.ts`、`web/tests/domains/settings/useMemberRoleSettings.test.ts`、`web/tests/services/memberRoleApi.test.ts`。齿轮新增「角色与提示词」，保留语言及关于；设置路由通过浏览器历史状态返回原频道，直接打开返回首页。
- A02 证据：角色无分页表格、载入/空/失败重试状态、全量正文编辑、字段校验和删除确认；定向用例检查 API 协议、保存和删除结果、失败后保留草稿/列表项。建议上述两项测试加 `tests/i18n.test.ts`，运行 Web `typecheck`、九文件 ESLint/Prettier；`git diff --check` 已通过，尚未收到独立复验。
- 交付（`MRP-T02-01`）：上述九文件，基线 `315b40b` 加 T01 已接受指纹 `907909580a59bfbb78cdd0545e45bb83d22ee073`；九文件组合 SHA256 `ceaded473dfd022cad808300a9e2dbd28edcf9f13404433ce940fa0bc0d26e76`（逐文件 SHA256、双空格和相对路径，按 #344 中九行顺序换行拼接）。未暂存或提交。
- 复验依据 #344：中级开发按 #343 仅用 Prettier 格式化两个设置页文件；三个 Vitest 文件 6 项通过，Web typecheck、九文件 ESLint/Prettier 及 diff check 通过。全量检查、构建与浏览器双语、小屏、键盘验收留待整体阶段。
- T04 可直接使用 `MemberRole`、`listMemberRoles(signal?)` 及 `errors.member_role_not_found`、`errors.member_role_name_conflict` 中英文翻译。
- 本文用于接收、进展、阻塞和交付记录；交付附实际变更、对应验收证据、可访问版本、检查及剩余风险，明确提供 T04 所需的客户端与文案。
