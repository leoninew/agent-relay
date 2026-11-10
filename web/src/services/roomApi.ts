import { apiClient } from "@/services/api";

export type Topic = {
  id: string;
  name: string;
  description: string;
  messageCount: number;
  createdAt: string | null;
  deletedAt: string | null;
};

export type Member = {
  id: string;
  kind: "human" | "agent";
  sessionId: string | null;
  name: string;
  initials: string;
  presence: "available" | "busy" | "offline" | "unknown";
  activity: string;
  activitySource: string;
  observedAt: string | null;
  topicIds: string[];
  deletedAt: string | null;
};

export type Delivery = {
  id: string;
  targetMemberId: string;
  targetSessionId: string;
  clientMessageId: string;
  status: "pending" | "submitting" | "queued" | "received" | "rejected" | "unknown";
  deletedAt?: string | null;
  updatedAt: string;
  queuedAt: string | null;
  receivedAt: string | null;
  receivedItemId: string | null;
  receivedTurnId: string | null;
  activationAttemptedAt: string | null;
  note: string | null;
  queuedSubmissionId: string | null;
  receipt: Record<string, unknown> | null;
  error: string | null;
};

export type RoomMessage = {
  id: string;
  publicationId: string | null;
  seq: number;
  senderId: string;
  senderName: string;
  content: string;
  topicIds: string[];
  mentionedMemberIds: string[];
  recipientIds: string[];
  replyToMessageId: string | null;
  createdAt: string;
  deliveries: Delivery[];
};

export type TopicPosition = {
  memberId: string;
  topicId: string;
  seq: number;
  updatedAt: string | null;
  laterCount: number;
};

export type RoomMetadata = {
  room: Room;
  topics: Topic[];
  members: Member[];
  sessions: Session[];
  positions: TopicPosition[];
  eventId: number;
  summary: {
    totalMessages: number;
    queuedCount: number;
    receivedCount: number;
    pendingCount: number;
    submittingCount: number;
    rejectedCount: number;
    unknownCount: number;
  };
};

export type MessagePage = {
  messages: RoomMessage[];
  hasMore: boolean;
  nextBeforeSeq: number | null;
  hasNewer: boolean;
};

export type RoomSnapshot = RoomMetadata & MessagePage;
export type MessageQueuePage = {
  messages: RoomMessage[];
  totalMessages: number;
  hasMore: boolean;
  nextBeforeSeq: number | null;
};
export type MessageQueueScope = {
  topicId?: string;
  memberId?: string;
};
export type ClearMessageQueueResult = {
  removedMessages: number;
};
export type MessageQueueQuery = MessageQueueScope & {
  beforeSeq?: number;
  limit?: number;
};

export type MessageQuery = {
  topicId?: string;
  memberId?: string;
  keyword?: string;
  beforeSeq?: number;
  limit?: number;
};
export type RoomEvent = {
  eventId: number;
  kind: "room" | "topic" | "member" | "session" | "message" | "delivery" | "position";
  entityId: string;
  messageId: string | null;
};
export type RoomEventPage = {
  events: RoomEvent[];
  nextEventId: number;
  hasMore: boolean;
  resyncRequired: boolean;
};

export type CreateMessage = {
  publicationId: string;
  content: string;
  topicIds: string[];
  mentionedMemberIds: string[];
  replyToMessageId?: string;
};

export type MessageDraft = Omit<CreateMessage, "publicationId">;

export type Room = {
  id: string;
  name: string;
  projectPath: string;
  description: string;
};

export type CreateRoom = { name: string; projectPath: string };
export type UpdateMember = { name: string; topicIds: string[] };
export type CreateMember = UpdateMember & { sessionId: string };
export type Session = {
  id: string;
  name: string;
  provider: string;
  projectPath: string;
  presence: Member["presence"];
  observedAt: string | null;
};
export type SessionCandidate = Session & {
  archived: boolean;
  memberId: string | null;
  usable: boolean;
  unavailableReason: string | null;
};
export type CreateTopic = { name: string; description: string };
export type ChangedMember = Member & { metadata: RoomMetadata };
export type CreatedMember = ChangedMember & { session: Session };
export type ChangedTopic = Topic & { metadata: RoomMetadata };

export async function fetchRooms(): Promise<Room[]> {
  const { data } = await apiClient.get<Room[]>("/api/room");
  return data;
}

export async function createRoom(request: CreateRoom): Promise<Room> {
  const { data } = await apiClient.post<Room>("/api/room", request);
  return data;
}

export async function deleteRoom(roomId: string): Promise<void> {
  await apiClient.delete(`/api/room/${encodeURIComponent(roomId)}`);
}

function queryParams(query: MessageQuery) {
  return {
    topic_id: query.topicId,
    member_id: query.memberId,
    keyword: query.keyword,
    before_seq: query.beforeSeq,
    limit: query.limit,
  };
}

export async function fetchRoom(
  roomId: string,
  query: MessageQuery = {},
  signal?: AbortSignal,
): Promise<RoomSnapshot> {
  const { data } = await apiClient.get<RoomSnapshot>(`/api/room/${encodeURIComponent(roomId)}`, {
    params: queryParams(query),
    signal,
  });
  return data;
}

export async function fetchRoomMessages(
  roomId: string,
  query: MessageQuery,
  signal?: AbortSignal,
): Promise<MessagePage> {
  const { data } = await apiClient.get<MessagePage>(
    `/api/room/${encodeURIComponent(roomId)}/message`,
    { params: queryParams(query), signal },
  );
  return data;
}

export async function fetchRoomMessage(
  roomId: string,
  messageId: string,
  signal?: AbortSignal,
): Promise<RoomMessage> {
  const { data } = await apiClient.get<RoomMessage>(
    `/api/room/${encodeURIComponent(roomId)}/message/${encodeURIComponent(messageId)}`,
    { signal },
  );
  return data;
}

export async function fetchMessageQueue(
  roomId: string,
  query: MessageQueueQuery = {},
  signal?: AbortSignal,
): Promise<MessageQueuePage> {
  const { data } = await apiClient.get<MessageQueuePage>(
    `/api/room/${encodeURIComponent(roomId)}/queue`,
    {
      params: {
        topic_id: query.topicId,
        member_id: query.memberId,
        before_seq: query.beforeSeq,
        limit: query.limit ?? 50,
      },
      signal,
    },
  );
  return data;
}

export async function clearMessageQueue(
  roomId: string,
  scope: MessageQueueScope = {},
): Promise<ClearMessageQueueResult> {
  const { data } = await apiClient.delete<ClearMessageQueueResult>(
    `/api/room/${encodeURIComponent(roomId)}/queue`,
    { params: { topic_id: scope.topicId, member_id: scope.memberId } },
  );
  return data;
}

export async function fetchRoomMetadata(
  roomId: string,
  signal?: AbortSignal,
): Promise<RoomMetadata> {
  const { data } = await apiClient.get<RoomMetadata>(
    `/api/room/${encodeURIComponent(roomId)}/metadata`,
    { signal },
  );
  return data;
}

export async function fetchRoomEvents(
  roomId: string,
  afterEventId: number,
  signal?: AbortSignal,
): Promise<RoomEventPage> {
  const { data } = await apiClient.get<RoomEventPage>(
    `/api/room/${encodeURIComponent(roomId)}/event`,
    { params: { after_event_id: afterEventId }, signal },
  );
  return data;
}

export async function postRoomMessage(
  roomId: string,
  message: CreateMessage,
): Promise<RoomMessage> {
  const { data } = await apiClient.post<RoomMessage>(
    `/api/room/${encodeURIComponent(roomId)}/message`,
    message,
  );
  return data;
}

export async function fetchPublication(
  roomId: string,
  publicationId: string,
): Promise<RoomMessage> {
  const { data } = await apiClient.get<RoomMessage>(
    `/api/room/${encodeURIComponent(roomId)}/publication/${encodeURIComponent(publicationId)}`,
  );
  return data;
}

export async function addRoomMember(roomId: string, request: CreateMember): Promise<CreatedMember> {
  const { data } = await apiClient.post<CreatedMember>(
    `/api/room/${encodeURIComponent(roomId)}/member`,
    request,
  );
  return data;
}

export async function fetchRoomSessions(roomId: string): Promise<SessionCandidate[]> {
  const { data } = await apiClient.get<SessionCandidate[]>(
    `/api/room/${encodeURIComponent(roomId)}/session`,
  );
  return data;
}

export async function updateRoomMember(
  roomId: string,
  memberId: string,
  request: UpdateMember,
): Promise<ChangedMember> {
  const { data } = await apiClient.patch<ChangedMember>(
    `/api/room/${encodeURIComponent(roomId)}/member/${encodeURIComponent(memberId)}`,
    request,
  );
  return data;
}

export async function addRoomTopic(roomId: string, request: CreateTopic): Promise<ChangedTopic> {
  const { data } = await apiClient.post<ChangedTopic>(
    `/api/room/${encodeURIComponent(roomId)}/topic`,
    request,
  );
  return data;
}

export async function updateRoomTopic(
  roomId: string,
  topicId: string,
  request: CreateTopic,
): Promise<ChangedTopic> {
  const { data } = await apiClient.patch<ChangedTopic>(
    `/api/room/${encodeURIComponent(roomId)}/topic/${encodeURIComponent(topicId)}`,
    request,
  );
  return data;
}

export async function deleteRoomTopic(roomId: string, topicId: string): Promise<ChangedTopic> {
  const { data } = await apiClient.delete<ChangedTopic>(
    `/api/room/${encodeURIComponent(roomId)}/topic/${encodeURIComponent(topicId)}`,
  );
  return data;
}

export async function deleteRoomMember(roomId: string, memberId: string): Promise<ChangedMember> {
  const { data } = await apiClient.delete<ChangedMember>(
    `/api/room/${encodeURIComponent(roomId)}/member/${encodeURIComponent(memberId)}`,
  );
  return data;
}
