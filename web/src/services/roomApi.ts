import { apiClient } from "@/services/api";
import { roomResourcePath } from "@/domains/channel/channelRoutes";

export type Topic = {
  id: string;
  name: string;
  description: string;
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

export type MemberInterruptResult = {
  status: "interrupted" | "not_running";
  turnId: string | null;
};

export type SessionModelCatalog = {
  sessionId: string;
  provider: string;
  currentModel: string | null;
  models: { id: string; model: string; displayName: string; description: string }[];
};

export async function fetchMemberModels(
  roomId: string,
  memberId: string,
  channelId: string,
): Promise<SessionModelCatalog> {
  const { data } = await apiClient.get<SessionModelCatalog>(
    roomResourcePath(roomId, channelId, `/member/${encodeURIComponent(memberId)}/model`),
  );
  return data;
}

export async function updateMemberModel(
  roomId: string,
  memberId: string,
  channelId: string,
  request: { sessionId: string; model: string },
): Promise<SessionModelCatalog> {
  const { data } = await apiClient.patch<SessionModelCatalog>(
    roomResourcePath(roomId, channelId, `/member/${encodeURIComponent(memberId)}/model`),
    request,
  );
  return data;
}

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
  submissionMethod?: "queue" | "steer" | null;
  steeredTurnId?: string | null;
  receipt: Record<string, unknown> | null;
  error: string | null;
};

export type SkillReference = {
  type: "skill";
  id: string;
  name: string;
};

export type UploadedImage = {
  id: string;
  url: string;
  markdown: string;
  mediaType: string;
  size: number;
};

export async function uploadRoomImage(
  roomId: string,
  file: File,
  signal: AbortSignal,
  channelId: string,
): Promise<UploadedImage> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post<UploadedImage>(
    roomResourcePath(roomId, channelId, "/image"),
    form,
    { signal },
  );
  return data;
}

export type McpServerReference = {
  type: "mcp_server";
  id: string;
  name: string;
};

export type CapabilityReference = SkillReference | McpServerReference;

export type CatalogIssue = { code: string; error: string };
export type SkillOption = SkillReference & {
  displayName: string;
  description: string;
  scope: "user" | "repo" | "system" | "admin";
  source: "plugin" | "user" | "repo" | "system" | "admin";
  pluginId: string | null;
  enabled: boolean;
};
export type SkillCatalog = { skills: SkillOption[]; errors: CatalogIssue[] };

export async function fetchRoomSkills(
  roomId: string,
  forceReload = false,
  signal: AbortSignal | undefined,
  channelId: string,
): Promise<SkillCatalog> {
  const { data } = await apiClient.get<SkillCatalog>(
    roomResourcePath(roomId, channelId, "/skills"),
    { params: { force_reload: forceReload }, signal },
  );
  return data;
}

export type RoomMessage = {
  id: string;
  publicationId: string | null;
  seq: number;
  senderId: string;
  senderName: string;
  content: string;
  capabilities?: CapabilityReference[];
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
export type ChannelRoomSnapshot = RoomSnapshot & {
  channelId: string;
  workingPath: string;
};
export type ClearedRoom = {
  removedMessages: number;
  removedMembers: number;
  metadata: RoomMetadata;
};
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
export type QueueRemovalResult = {
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
  kind: "room" | "topic" | "member" | "session" | "message" | "delivery" | "position" | "clear";
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
  capabilities?: CapabilityReference[];
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
export type UpdateRoom = { name: string };
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
  unavailableReasonCode?: string | null;
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

export async function updateRoom(roomId: string, request: UpdateRoom): Promise<Room> {
  const { data } = await apiClient.patch<Room>(`/api/room/${encodeURIComponent(roomId)}`, request);
  return data;
}

export async function deleteRoom(roomId: string): Promise<void> {
  await apiClient.delete(`/api/room/${encodeURIComponent(roomId)}`);
}

export async function clearRoom(roomId: string, channelId: string): Promise<ClearedRoom> {
  const { data } = await apiClient.post<ClearedRoom>(roomResourcePath(roomId, channelId, "/clear"));
  return data;
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
  signal: AbortSignal | undefined,
  channelId: string,
): Promise<RoomSnapshot> {
  const { data } = await apiClient.get<RoomSnapshot>(roomResourcePath(roomId, channelId), {
    params: queryParams(query),
    signal,
  });
  return data;
}

export async function fetchRoomMessages(
  roomId: string,
  query: MessageQuery,
  signal: AbortSignal | undefined,
  channelId: string,
): Promise<MessagePage> {
  const { data } = await apiClient.get<MessagePage>(
    roomResourcePath(roomId, channelId, "/message"),
    { params: queryParams(query), signal },
  );
  return data;
}

export async function fetchRoomMessage(
  roomId: string,
  messageId: string,
  signal: AbortSignal | undefined,
  channelId: string,
): Promise<RoomMessage> {
  const { data } = await apiClient.get<RoomMessage>(
    roomResourcePath(roomId, channelId, `/message/${encodeURIComponent(messageId)}`),
    { signal },
  );
  return data;
}

export async function fetchMessageQueue(
  roomId: string,
  query: MessageQueueQuery = {},
  signal: AbortSignal | undefined,
  channelId: string,
): Promise<MessageQueuePage> {
  const { data } = await apiClient.get<MessageQueuePage>(
    roomResourcePath(roomId, channelId, "/queue"),
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

export async function deleteQueueMessage(
  roomId: string,
  messageId: string,
  channelId: string,
): Promise<QueueRemovalResult> {
  const { data } = await apiClient.delete<QueueRemovalResult>(
    roomResourcePath(roomId, channelId, `/queue/${encodeURIComponent(messageId)}`),
  );
  return data;
}

export async function fetchRoomMetadata(
  roomId: string,
  signal: AbortSignal | undefined,
  channelId: string,
): Promise<RoomMetadata> {
  const { data } = await apiClient.get<RoomMetadata>(
    roomResourcePath(roomId, channelId, "/metadata"),
    { signal },
  );
  return data;
}

export async function fetchRoomEvents(
  roomId: string,
  afterEventId: number,
  signal: AbortSignal | undefined,
  channelId: string,
): Promise<RoomEventPage> {
  const { data } = await apiClient.get<RoomEventPage>(
    roomResourcePath(roomId, channelId, "/event"),
    { params: { after_event_id: afterEventId }, signal },
  );
  return data;
}

export async function postRoomMessage(
  roomId: string,
  message: CreateMessage,
  channelId: string,
): Promise<RoomMessage> {
  const { data } = await apiClient.post<RoomMessage>(
    roomResourcePath(roomId, channelId, "/message"),
    message,
  );
  return data;
}

export async function fetchPublication(
  roomId: string,
  publicationId: string,
  channelId: string,
): Promise<RoomMessage> {
  const { data } = await apiClient.get<RoomMessage>(
    roomResourcePath(roomId, channelId, `/publication/${encodeURIComponent(publicationId)}`),
  );
  return data;
}

export async function addRoomMember(
  roomId: string,
  request: CreateMember,
  channelId: string,
): Promise<CreatedMember> {
  const { data } = await apiClient.post<CreatedMember>(
    roomResourcePath(roomId, channelId, "/member"),
    request,
  );
  return data;
}

export async function fetchRoomSessions(
  roomId: string,
  signal: AbortSignal | undefined,
  channelId: string,
): Promise<SessionCandidate[]> {
  const { data } = await apiClient.get<SessionCandidate[]>(
    roomResourcePath(roomId, channelId, "/session"),
    { signal },
  );
  return data;
}

export async function interruptRoomMember(
  roomId: string,
  memberId: string,
  channelId: string,
): Promise<MemberInterruptResult> {
  const { data } = await apiClient.post<MemberInterruptResult>(
    roomResourcePath(roomId, channelId, `/member/${encodeURIComponent(memberId)}/interrupt`),
  );
  return data;
}

export async function updateRoomMember(
  roomId: string,
  memberId: string,
  request: UpdateMember,
  channelId: string,
): Promise<ChangedMember> {
  const { data } = await apiClient.patch<ChangedMember>(
    roomResourcePath(roomId, channelId, `/member/${encodeURIComponent(memberId)}`),
    request,
  );
  return data;
}

export async function addRoomTopic(
  roomId: string,
  request: CreateTopic,
  channelId: string,
): Promise<ChangedTopic> {
  const { data } = await apiClient.post<ChangedTopic>(
    roomResourcePath(roomId, channelId, "/topic"),
    request,
  );
  return data;
}

export async function updateRoomTopic(
  roomId: string,
  topicId: string,
  request: CreateTopic,
  channelId: string,
): Promise<ChangedTopic> {
  const { data } = await apiClient.patch<ChangedTopic>(
    roomResourcePath(roomId, channelId, `/topic/${encodeURIComponent(topicId)}`),
    request,
  );
  return data;
}

export async function deleteRoomTopic(
  roomId: string,
  topicId: string,
  channelId: string,
): Promise<ChangedTopic> {
  const { data } = await apiClient.delete<ChangedTopic>(
    roomResourcePath(roomId, channelId, `/topic/${encodeURIComponent(topicId)}`),
  );
  return data;
}

export async function deleteRoomMember(
  roomId: string,
  memberId: string,
  channelId: string,
): Promise<ChangedMember> {
  const { data } = await apiClient.delete<ChangedMember>(
    roomResourcePath(roomId, channelId, `/member/${encodeURIComponent(memberId)}`),
  );
  return data;
}
