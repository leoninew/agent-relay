# Task / 子任务 T07：按需查阅与话题位置

最后修改时间: 2026-11-08

## Review status / 审查状态

N3 已交付。成员 API 复用显式 roomId/memberId 路径，不使用 Bearer 凭证；整体 Verification 仍按总计划台账逐项完成。

## Parent and authority / 父任务与权威记录

- [总意图](../../intent/20261107-backend-from-web.md)、[权威总计划](../../plan/20261107-backend-from-web.md)。任务 ID：T07，当前接口规则见总计划修订 16。
- 协调根：`D:/SourceCodes/mywork/agent-relay`。

## Goal and contract / 目标与接口

G10、G11：成员按需读取 Relay 已持久化的消息，记录服务成功提供的返回位置；位置不是已读、任务进度、投递游标或重试状态。

- `GET /api/room/{roomId}/member/{memberId}/catalog`
- `POST /api/room/{roomId}/member/{memberId}/context`
- `GET /api/room/{roomId}/member/{memberId}/position`

这些是本机成员调用接口，URL 用于指定业务房间和成员，不提供认证或访问控制。活动成员状态在请求处理时核对。

Context 支持按 messageId 查单条、按当前订阅 topicId 查阅、按正文 keyword 字面搜索。列表默认 50、最多 200，beforeSeq/afterSeq 游标互斥，返回按 seq 正序。话题查询要求当前订阅；单条和跨话题搜索限于该成员实际收到或命中当前订阅的话题。@ 和引用不扩展历史查阅范围。

非空响应持久记录 queryId、返回消息及提供时间，并按实际返回范围单调推进成员×话题位置。跳读与回查允许；位置推进取 max(old, returnedSeq)。Web 通过房间元数据和事件显示当前订阅位置及位置后的消息数。

## Implementation and checks / 实现与检查

`member_context` revision 保存查阅提供记录及成员×话题位置，位置变化沿用 room_events。后端正常检查覆盖双向分页、字面搜索、订阅范围、直接 @、跳读/回查、订阅变化、并发位置推进和持久事件；Web 使用轻量 API/状态/组件检查。未增加迁移功能测试、反向测试或复杂页面生命周期测试。

N3 交付细节、检查结果和仍未完成的目标见[总计划](../../plan/20261107-backend-from-web.md)。
