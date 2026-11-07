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
      { id: "summary", name: "汇总", description: "协作约定", messageCount: 0, deletedAt: null },
      { id: "frontend", name: "前端", description: "聊天室界面", messageCount: 1, deletedAt: null },
      { id: "backend", name: "后端", description: "接口契约", messageCount: 1, deletedAt: null },
    ],
    members: [
      {
        id: "frontend-worker",
        sessionId: "session-frontend",
        name: "前端 Worker",
        initials: "FE",
        presence: "busy",
        activity: "正在处理消息",
        deletedAt: null,
        topicIds: ["frontend"],
      },
      {
        id: "backend-worker",
        sessionId: "session-backend",
        name: "后端 Worker",
        initials: "BE",
        presence: "available",
        activity: "可接收消息",
        deletedAt: null,
        topicIds: ["backend"],
      },
      {
        id: "test-worker",
        sessionId: "session-test",
        name: "测试 Worker",
        initials: "QA",
        presence: "available",
        activity: "同时订阅前后端",
        deletedAt: null,
        topicIds: ["frontend", "backend"],
      },
    ],
    sessions: [
      {
        id: "session-frontend",
        name: "前端会话",
        provider: "codex",
        projectPath: "D:/work/agent-relay",
        presence: "busy",
        observedAt: null,
      },
    ],
    messages: [
      {
        id: "msg-0001",
        seq: 1,
        senderId: null,
        senderName: "控制台",
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
        recipientIds: ["test-worker"],
        replyToMessageId: null,
        createdAt: "2026-11-06T10:01:00Z",
        deliveries: [
          {
            id: "msg-0002:test-worker",
            targetMemberId: "test-worker",
            status: "delivered",
            updatedAt: "2026-11-06T10:01:00Z",
          },
        ],
      },
    ],
    summary: { totalMessages: 2, deliveredCount: 2, queuedCount: 1, pendingCount: 0 },
  };
}
