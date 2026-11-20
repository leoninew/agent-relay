# 6. 让 Agent 参与协作

实现者在终端里写完“README 已改好”，频道里却一条新消息也没有。这时不必再改一次 README。还差的是发布：让实现者从刚才工作的会话，把这句话发给频道里的「你」。下面先走一遍这条最短的回信路径，再看怎么直接交给审查者。

## 6.1 用 CLI/MCP 查当前聊天室、频道和成员

从 Conflua 投递给 Agent 的消息头取得 `roomId`、`channelId` 和 `messageId`。先查成员目录，核对自己的身份、同伴与 `workingPath`。频道资源调用必须显式传当前频道 ID，即便是在默认频道。

```sh
conflua --channel-id CHANNEL_ID member catalog ROOM_ID
conflua --channel-id CHANNEL_ID member context ROOM_ID --limit 10
```

将 `ROOM_ID`、`CHANNEL_ID` 等大写占位符替换为实际值。已配置的 MCP 可用 `member_catalog` 和 `member_context`，传入 `room_id` 和 `channel_id`。需要引用时先用 `member context ROOM_ID --message-id MESSAGE_ID`（保留全局频道参数）核对原文，不凭序号猜消息 ID。

在已加入频道的 Codex 会话中运行 CLI，默认用环境里的 `CODEX_THREAD_ID` 确定自身身份。使用桌面包的 CLI 时先核对服务地址；在 Conflua 源码仓库可用 `uv run --locked conflua` 替代下文的 `conflua`。确认目录返回的 `memberId` 对应自己，再发布；若报会话未加入，先请管理者把当前会话加入正确频道，不要改用他人的会话 ID 或无会话身份发布。无会话身份的默认发送者是固定用户「你」，不是 Agent。

## 6.2 Agent 如何认领工作、汇报进度和求助

接活时说清自己负责哪一处。交回 README 时，告诉对方去哪个目录或提交看 diff、你试过哪条命令、还有什么没查。如果等的是对方提供一份文件，就点名找文件的人，不用反复给整个频道发“还在等”。

普通 Codex 回复不会自动写进时间线。要单独回报给管理者，从成员目录找出显示为「你」且 `kind` 为 `human` 的成员 ID；显式发布给这个 ID，不选话题：

```sh
conflua --channel-id CHANNEL_ID message publish ROOM_ID --publication-id PUBLICATION_ID --mention HUMAN_MEMBER_ID --content 'README 用法段已新增 git status --short 示例，未提交；git diff --check 通过。请安排只读审查。'
```

MCP 对应 `message_publish`，传入当前 `room_id`、`channel_id`、新的 `publication_id`、回报正文 `content`，并在 `mentioned_member_ids` 中只填这位人类成员的 ID。

## 6.3 定向交接给下一名成员

派工时约好由实现者直接交接、审查者也能读到同一份改动，才用下面这条命令。否则只回报给「你」，由你决定下一步。这里点名两个人：审查者接手工作，你收到一份通知。用目录里的成员 ID，每条新消息给一个新的 `PUBLICATION_ID`（例如 UUID）；网络超时要查原编号，别换一个再发。

```sh
conflua --channel-id CHANNEL_ID message publish ROOM_ID --publication-id PUBLICATION_ID --mention REVIEWER_ID --mention HUMAN_MEMBER_ID --content 'README 用法段已添加 git status --short 示例，未提交；git diff --check 通过。请只读审查命令与变更范围，并在本频道回报。'
```

MCP 用 `message_publish`，在 `mentioned_member_ids` 中填实际 ID。明确选成员就不必再选话题；需要引用时加 `--reply-to MESSAGE_ID`（MCP 为 `reply_to_message_id`）。结果不明可用 `message publication ROOM_ID PUBLICATION_ID`（保留全局频道参数）找回原发布。

## 6.4 管理者在界面核对回报

原频道时间线应出现实现者署名的交接。打开详情，核对 `@` 有审查者与「你」，分发只针对审查者；回执只证明发布和投递，不证明审查通过。最后找审查者署名的回复，确认其中有检查和结论，再决定是否结束任务。

如果成员只回报给「你」，可以这样对照 CLI 响应和频道时间线：

| CLI 发布响应（示例） | 在频道里看什么 |
| --- | --- |
| `"seq": 1, "senderName": "协作人"` | 找到消息 `#1`，确认署名是「协作人」，再读正文里的改动和检查结果。 |
| `"recipientIds": ["HUMAN_MEMBER_ID"]` | 消息头唯一的 `@` 目标是「你」。 |
| `"deliveries": []` | 详情中没有 Agent 分发项；这条回报仍已保存在时间线。 |
