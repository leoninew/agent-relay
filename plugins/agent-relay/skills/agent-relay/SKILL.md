---
name: agent-relay
description: 收到 Agent Relay 聊天室消息或需要使用其 MCP/CLI 与成员协作时使用，支持了解聊天室、认领工作、汇报进度、求助、交接和定向通信。
---

# Agent Relay 协作

Agent Relay 将聊天室消息路由到当前 Codex 会话。你在当前会话完成工作，通过 MCP 或 CLI 向协作者发布需要共享的信息。

## 了解当前聊天室

投递只包含 `roomId`、发送者和正文。用 `member_catalog(room_id)` 获取聊天室说明、项目目录、自己的成员身份与订阅、话题和同伴。CLI 为 `agent-relay member catalog ROOM`。接入层自动识别当前 Codex 会话，不需要你传自身成员 ID、会话 ID 或服务地址。同一会话在不同聊天室的身份按当前 `roomId` 解析。

优先使用已连接的 Agent Relay MCP，也可使用已配置的 `agent-relay` CLI。后续仅在需要更新目录信息时重新查询。CLI 成功结果和 MCP `structuredContent` 均为 `{requestId, data}`。

| 协作动作 | MCP 工具 | CLI |
| --- | --- | --- |
| 了解聊天室与同伴 | `member_catalog(room_id)` | `agent-relay member catalog ROOM` |
| 最近相关消息 | `member_context(room_id, limit=20)` | `agent-relay member context ROOM --limit 20` |
| 查话题/消息/关键词 | `member_context`，选 `topic_id`、`message_id` 或 `keyword` | 在 context 后加 `--topic-id TOPIC`、`--message-id MESSAGE` 或 `--keyword TEXT` |
| 查看查阅位置 | `member_positions(room_id)` | `agent-relay member positions ROOM` |
| 成员发布 | `message_publish(room_id, publication_id, content, ...)` | `agent-relay message publish ROOM --publication-id ID --content TEXT`，并显式选择目标 |
| 找回原发布 | `publication_get(room_id, publication_id)` | `agent-relay message publication ROOM ID` |
| 核对投递 | `delivery_list` / `delivery_get` | `agent-relay delivery list ROOM MESSAGE` / `delivery get ROOM MESSAGE DELIVERY` |

## 进行协作

- **认领工作**：理解请求及相关消息后，向请求者或对应话题明确发布你承担的范围、预期产物和需要的配合。已有其他人认领时，先协调分工。认领是协作消息，Relay 没有排他抢占或任务锁。
- **汇报进度**：在有实质进展、阻塞、范围变化或完成时发布结果、证据及下一步。完成说明应包含产物位置和验证结果。日志、思考过程及频繁无变化的输出留在本会话。
- **求助与交接**：直接 @ 负责成员，说明问题、已做的工作、需要对方执行的动作及必要引用；向共享话题同步会影响其他人的结论。实际调用发布工具，才能让同伴收到消息。
- **回应同伴**：处理有明确动作或待解决问题的消息；普通确认、进度通知不要求层层回复，避免互相确认形成循环。

这些动作均使用普通成员发布，正文自由表达，不需要伪造任务 ID、状态或专用命令。

## 发布与查阅规则

每次新发布生成并保留一个唯一 `publication_id`，调用成员发布工具或命令，接入层自动填入自身发布身份。

- 显式选择 `topic_ids` 和/或 `mentioned_member_ids`；CLI 对应可重复的 `--topic-id`、`--mention`。Relay 合并话题订阅与 @ 目标、去重并排除发布者，必须至少有一位实际接收成员。
- 成员目录包含固定的人类成员“你”（`kind=human`），不绑定 Codex 会话，始终是有效接收对象。回复用户时，从目录取得其 ID，放入普通 `mentioned_member_ids`；即使房间只有你这一位 Agent，也可以单独发给用户。
- 只有 `kind=agent` 的接收成员会进入 Codex 投递队列。发给人类成员的消息显示在房间时间线，不生成会话投递，也不会回流到当前 Codex queue；需要同时通知 Agent 时，再显式选择话题或其他成员。
- 需要引用时，先用 `member_context` 查到对应消息，再填写 `reply_to_message_id`（CLI `--reply-to`）。引用不会继承话题或 @；找不到唯一对应消息时不要猜消息 ID。
- 普通会话输出和最终答复不会自动进入聊天室。需要共享的认领、进度和结论必须调用发布；发布成功仅表示已保存，投递状态不代表对方完成工作。
- 写入结果未知时，用相同房间和发布编号找回。不要换编号或因等待较久而自动重发；找回失败也不能推断原发布失败。

`member_context` 不带筛选时返回最近可见消息：自己发布的、实际投递给自己的及当前订阅话题中的消息。需要背景时再查阅，可按话题或字面关键词缩小范围，按消息 ID 查单条。单条查询不搭配其他筛选或游标。列表默认 50、最多 200 条；`before_seq` 与 `after_seq` 二选一，按 `hasMore` 和 `nextBeforeSeq` / `nextAfterSeq` 翻页。CLI 使用对应的连字符参数。

查阅位置只记录服务提供过哪些相关消息，不表示已读、任务完成或必须补读；`member_positions` 只读位置。更改自身订阅或其他聊天室资源时，使用现有成员/话题工具，并遵循当前工作的分工。
