import type { RoomSnapshot } from "@/services/roomApi";

export function roomFixture(): RoomSnapshot {
  return {
    room: {
      id: "agent-relay",
      name: "Agent Relay 开发室",
      projectPath: "D:/work/agent-relay",
      description: "项目讨论",
    },
    topics: [
      { id: "summary", name: "汇总", description: "协作约定", messageCount: 0 },
      { id: "frontend", name: "前端", description: "聊天室界面", messageCount: 1 },
      { id: "backend", name: "后端", description: "接口契约", messageCount: 1 },
    ],
    members: [
      {
        id: "frontend-worker",
        sessionId: "session-frontend",
        name: "前端 Worker",
        role: "前端开发",
        initials: "FE",
        presence: "busy",
        activity: "正在处理消息",
        topicIds: ["frontend"],
      },
      {
        id: "backend-worker",
        sessionId: "session-backend",
        name: "后端 Worker",
        role: "后端开发",
        initials: "BE",
        presence: "available",
        activity: "可接收消息",
        topicIds: ["backend"],
      },
      {
        id: "test-worker",
        sessionId: "session-test",
        name: "测试 Worker",
        role: "集成测试",
        initials: "QA",
        presence: "available",
        activity: "同时关注前后端",
        topicIds: ["frontend", "backend"],
      },
    ],
    messages: [
      {
        id: "msg-0001",
        seq: 1,
        senderId: "frontend-worker",
        senderName: "前端 Worker",
        content: "前端讨论内容",
        topicIds: ["frontend"],
        mentionedMemberIds: [],
        recipientIds: ["frontend-worker", "test-worker"],
        replyToMessageId: null,
        createdAt: "2026-11-06T10:00:00Z",
        deliveries: [
          {
            id: "msg-0001:frontend-worker",
            targetMemberId: "frontend-worker",
            status: "queued",
            updatedAt: "2026-11-06T10:00:00Z",
          },
          {
            id: "msg-0001:test-worker",
            targetMemberId: "test-worker",
            status: "delivered",
            updatedAt: "2026-11-06T10:00:00Z",
          },
        ],
      },
      {
        id: "msg-0002",
        seq: 2,
        senderId: "backend-worker",
        senderName: "后端 Worker",
        content: "后端讨论内容",
        topicIds: ["backend"],
        mentionedMemberIds: ["test-worker"],
        recipientIds: ["backend-worker", "test-worker"],
        replyToMessageId: null,
        createdAt: "2026-11-06T10:01:00Z",
        deliveries: [
          {
            id: "msg-0002:backend-worker",
            targetMemberId: "backend-worker",
            status: "delivered",
            updatedAt: "2026-11-06T10:01:00Z",
          },
          {
            id: "msg-0002:test-worker",
            targetMemberId: "test-worker",
            status: "delivered",
            updatedAt: "2026-11-06T10:01:00Z",
          },
        ],
      },
    ],
    summary: { totalMessages: 2, deliveredCount: 3, queuedCount: 1 },
  };
}
