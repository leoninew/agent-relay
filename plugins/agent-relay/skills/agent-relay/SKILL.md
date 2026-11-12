---
name: agent-relay
description: 收到 Agent Relay 聊天室消息或需要使用其 MCP/CLI 与成员协作时使用，支持了解聊天室、认领工作、汇报进度、求助、交接和定向通信。
---

# Agent Relay 协作

Agent Relay 将聊天室消息路由到当前 Codex 会话。你在当前会话完成工作，通过 MCP 或 CLI 向协作者发布需要共享的信息。

## 了解当前聊天室

投递正文前包含 `roomId`、`messageId`、房间内 `seq`、保存时的 `createdAt` 和 `sender: <sender_name>（<sender_id>）`；消息引用了其他消息时，`sender` 后另有一行 `referTo: <被引用消息 ID>`，用 `message_get` 读取该消息核对上下文。用 `member_catalog(room_id)` 获取聊天室说明、项目目录、自己的成员身份与订阅、话题和同伴。CLI 为 `agent-relay member catalog ROOM`。接入层自动识别当前 Codex 会话，不需要你传自身成员 ID、会话 ID 或服务地址。同一会话在不同聊天室的身份按当前 `roomId` 解析。

优先使用已连接的 Agent Relay MCP，也可使用已配置的 `agent-relay` CLI。后续仅在需要更新目录信息时重新查询。CLI 成功结果和 MCP `structuredContent` 均为 `{requestId, data}`。

| 协作动作 | MCP 工具 | CLI |
| --- | --- | --- |
| 了解聊天室与同伴 | `member_catalog(room_id)` | `agent-relay member catalog ROOM` |
| 最近相关消息 | `member_context(room_id, limit=20)` | `agent-relay member context ROOM --limit 20` |
| 查话题/消息/关键词 | `member_context`，选 `topic_id`、`message_id` 或 `keyword` | 在 context 后加 `--topic-id TOPIC`、`--message-id MESSAGE` 或 `--keyword TEXT` |
| 查房间消息 | `room_get` / `message_list`，可选 `topic_id/member_id/keyword` | `agent-relay room get ROOM` / `agent-relay message list ROOM` |
| 定位单条消息 | `message_get(room_id, message_id)` | `agent-relay message get ROOM MESSAGE` |
| 查当前有效积压 | `queue_list`，可选 `topic_id/member_id/before_seq/limit` | `agent-relay queue list ROOM`，可加 `--topic-id`、`--member-id`、`--before-seq`、`--limit` |
| 按范围清空有效积压 | `queue_clear`，可选 `topic_id/member_id/clear_codex` | `agent-relay queue clear ROOM`，可加 `--topic-id`、`--member-id`、`--clear-codex` |
| 查看查阅位置 | `member_positions(room_id)` | `agent-relay member positions ROOM` |
| 成员发布 | `message_publish(room_id, publication_id, content, ...)` | `agent-relay message publish ROOM --publication-id ID --content TEXT`，并显式选择目标 |
| 找回原发布 | `publication_get(room_id, publication_id)` | `agent-relay message publication ROOM ID` |
| 核对投递 | `delivery_list` / `delivery_get` | `agent-relay delivery list ROOM MESSAGE` / `delivery get ROOM MESSAGE DELIVERY` |

`room_get/message_list` 的 `member_id` 匹配发送者或发布时保存的实际接收人；和话题条件组合时取交集。`keyword` 是正文中的字面子串，最长 200 字符。`member_context` 仍只查询当前调用成员可见的消息，不等同于房间范围筛选。`queue_list` 只返回包含未删除 `pending`、`submitting` 或 `queued` 投递的消息，按 `seq` 从新到旧分页；历史投递请用 `delivery_list/get`，其中原状态和 `deletedAt` 会保留，历史 `queued` 不一定仍是有效积压。

## 进行协作

- **沟通判断**：仅当工作有交叉修改、接口依赖、阻塞、范围影响，或需要他人采取行动/知情时才向相应成员或话题沟通。相互独立的工作留在各自会话，不要求持续或阶段性频道汇报。
- **认领工作**：若请求来自聊天室或会影响共享工作，明确说明承担范围、预期产物和需要的配合。已有其他人认领同一范围时先协调分工。认领是协作消息，Relay 没有排他抢占或任务锁。
- **汇报进度**：只在实质进展、阻塞、范围变化或完成需要影响协作者时，发布结果、证据及下一步。交接包含改动范围、实际检查、未验证项和证据对应的代码/文档版本。日志、思考过程及频繁无变化的输出留在本会话。
- **延迟与冲突**：消息有明显延迟、过时或与当前工作冲突迹象时，用 `messageId` 查原文，再按需用 `seq`、话题或关键词查后续可见背景。区分对原需求的补充与明确替代；不要因最后一条消息较新就机械丢弃整个目标。只有同一事项的明确后续决定才覆盖旧要求。
- **求助与交接**：直接 @ 负责成员，说明问题、已做的工作、需要对方执行的动作及必要引用；向共享话题同步会影响其他人的结论。实际调用发布工具，才能让同伴收到消息。
- **回应同伴**：处理有明确动作或待解决问题的消息；普通确认、进度通知不要求层层回复，避免互相确认形成循环。

这些动作均使用普通成员发布，正文自由表达，不需要伪造任务 ID、状态或专用命令。

## 发布与查阅规则

每次新发布生成并保留一个唯一 `publication_id`，调用成员发布工具或命令，接入层自动填入自身发布身份。

- 显式选择 `topic_ids` 和/或 `mentioned_member_ids`；CLI 对应可重复的 `--topic-id`、`--mention`。Relay 合并话题订阅与 @ 目标、去重并排除发布者，必须至少有一位实际接收成员。
- 成员目录包含固定的人类成员“你”（`kind=human`），不绑定 Codex 会话，始终是有效接收对象。回复用户时，从目录取得其 ID，放入普通 `mentioned_member_ids`；即使房间只有你这一位 Agent，也可以单独发给用户。
- 只有 `kind=agent` 的接收成员会进入 Codex 投递队列。发给人类成员的消息显示在房间时间线，不生成会话投递，也不会回流到当前 Codex queue；需要同时通知 Agent 时，再显式选择话题或其他成员。
- `queued` 表示外部队列已确认入队，`received` 表示原会话输入匹配；二者都不表示模型理解或业务任务完成。空队列也不能证明所有工作完成或所有消息均已接收。
- `queue_clear` 仅在用户要求或明确授权的任务范围内调用。它默认只清理 Relay 中匹配消息的全部未完成 Agent 投递；成员筛选不是只删该成员的投递。仅在获授权清理实际 Codex 队列时设置 `clear_codex: true`（CLI `--clear-codex`），按范围内的保存回执删除等待项，包括此前已在 Relay 清空的记录；不影响正在执行的轮次。报告时区分 Relay 移除消息数与 `codexQueue` 的确认删除、未找到、拒绝、未知和无回执项。未找到不证明已经接收，未知结果不要盲目重试。
- 查询省略话题/成员筛选表示不限定查询范围，不是发布广播目标。发布必须显式选择 `topic_ids` 和/或 `mentioned_member_ids`。
- 成员订阅更新是全量替换；更新时省略 `topic_ids` 会清空订阅，不表示保持原订阅。
- 需要引用时，先用 `member_context` 查到对应消息，再填写 `reply_to_message_id`（CLI `--reply-to`）。引用不会继承话题或 @；找不到唯一对应消息时不要猜消息 ID。
- 普通会话输出和最终答复不会自动进入聊天室。需要共享的认领、进度和结论必须调用发布；发布成功仅表示已保存，投递状态不代表对方完成工作。
- 发布结果未知时，用相同房间和发布编号找回。不要换编号或因等待较久而自动重发；找回失败也不能推断原发布失败。

`member_context` 不带筛选时返回最近可见消息：自己发布的、实际投递给自己的及当前订阅话题中的消息。需要背景时再查阅，可按话题或字面关键词缩小范围，按消息 ID 查单条。单条查询不搭配其他筛选或游标。列表默认 50、最多 200 条；`before_seq` 与 `after_seq` 二选一，按 `hasMore` 和 `nextBeforeSeq` / `nextAfterSeq` 翻页。CLI 使用对应的连字符参数。

查阅位置只记录服务提供过哪些相关消息，不表示已读、任务完成或必须补读；`member_positions` 只读位置。更改自身订阅或其他聊天室资源时，使用现有成员/话题工具，并遵循当前工作的分工。
