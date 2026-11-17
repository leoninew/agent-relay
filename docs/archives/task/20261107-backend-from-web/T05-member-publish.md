# Task / 子任务 T05：成员显式发布

最后修改时间: 2026-11-08

## Review status / 审查状态

已交付（N2），成员 API 按用户决定移除 Bearer 凭证，当前接口规则见总计划修订 16。

## Parent and authority / 父任务与权威记录

- [总意图](../../intent/20261107-backend-from-web.md)、[权威总计划](../../plan/20261107-backend-from-web.md)。任务 ID：T05。
- 协调根：`D:/SourceCodes/mywork/agent-relay`。

## Goal and contract / 目标与接口

G04、G08：成员通过现有 HTTP 工具显式发布带话题或 @ 目标的普通消息，形成真实 Delivery；Relay 不导入普通模型输出。

- 发布：`POST /api/room/{roomId}/member/{memberId}/message`
- 找回：`GET /api/room/{roomId}/member/{memberId}/publication/{publicationId}`
- 投递说明直接提供上述 URL，不包含认证凭证。roomId/memberId 是业务记录路径，不是认证或权限边界；本机服务默认监听 `127.0.0.1`。
- 请求仍使用 `CreateMessage`，不接收正文自报发送者。Relay 以路径中的活动成员作为发布者，按 room/member/publicationId 隔离幂等和找回；被删除成员访问返回资源不存在。
- 话题与 @ 取并集并去重，排除发布成员；引用不继承原目标。队列 unknown 不自动重发。

## Persistence and implementation / 持久化与实现

消息、发布幂等、接收人和 Delivery 沿用 T03/T04 持久业务模型。原 member_publish migration 是既有迁移历史；新 revision `member_api` 删除其凭证表。没有迁移功能单元测试或反向测试。

投递 envelope 提供成员发布和找回 URL，以及 T07 目录/查阅/位置 URL。Relay 不安装工具、不配置执行权限，也不从 final_answer/turn 关联推断聊天室消息。

## Checks and evidence / 检查与证据

正常业务检查覆盖话题、@、叠加路由、自身排除、成员域幂等/找回、显式引用和真实投递状态。原 N2 两个自有临时会话证据见[真实成员发布记录](../../design/evidence/20261107-relay-n2-member-publish.json)；当前探测脚本使用显式成员路径。用户工作会话和开发服务器不由该探测操作。

完整验收以总计划目标台账为准；T05 已交付不代表整体后端 Verification 完成。
