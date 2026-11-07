import { apiClient } from "@/services/api";

export type Topic = {
  id: string;
  name: string;
  description: string;
  messageCount: number;
  deletedAt: string | null;
};

export type Member = {
  id: string;
  sessionId: string;
  name: string;
  initials: string;
  presence: "available" | "busy" | "offline";
  activity: string;
  topicIds: string[];
  deletedAt: string | null;
};

export type Delivery = {
  id: string;
  targetMemberId: string;
  status: "pending" | "queued" | "delivered";
  updatedAt: string;
};

export type RoomMessage = {
  id: string;
  seq: number;
  senderId: string | null;
  senderName: string;
  content: string;
  topicIds: string[];
  mentionedMemberIds: string[];
  recipientIds: string[];
  replyToMessageId: string | null;
  createdAt: string;
  deliveries: Delivery[];
};

export type RoomSnapshot = {
  room: Room;
  topics: Topic[];
  members: Member[];
  sessions: Session[];
  messages: RoomMessage[];
  summary: {
    totalMessages: number;
    deliveredCount: number;
    queuedCount: number;
    pendingCount: number;
  };
};

export type CreateMessage = {
  content: string;
  topicIds: string[];
  mentionedMemberIds: string[];
  replyToMessageId?: string;
};

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
};
export type CreateTopic = { name: string; description: string };

export async function fetchRooms(): Promise<Room[]> {
  const { data } = await apiClient.get<Room[]>("/api/room");
  return data;
}

export async function createRoom(request: CreateRoom): Promise<Room> {
  const { data } = await apiClient.post<Room>("/api/room", request);
  return data;
}

export async function fetchRoom(roomId: string, topicId?: string): Promise<RoomSnapshot> {
  const { data } = await apiClient.get<RoomSnapshot>(`/api/room/${encodeURIComponent(roomId)}`, {
    params: topicId ? { topic_id: topicId } : undefined,
  });
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

export async function addRoomMember(
  roomId: string,
  request: CreateMember,
): Promise<Member & { session: Session }> {
  const { data } = await apiClient.post<Member & { session: Session }>(
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
): Promise<Member> {
  const { data } = await apiClient.patch<Member>(
    `/api/room/${encodeURIComponent(roomId)}/member/${encodeURIComponent(memberId)}`,
    request,
  );
  return data;
}

export async function addRoomTopic(roomId: string, request: CreateTopic): Promise<Topic> {
  const { data } = await apiClient.post<Topic>(
    `/api/room/${encodeURIComponent(roomId)}/topic`,
    request,
  );
  return data;
}

export async function updateRoomTopic(
  roomId: string,
  topicId: string,
  request: CreateTopic,
): Promise<Topic> {
  const { data } = await apiClient.patch<Topic>(
    `/api/room/${encodeURIComponent(roomId)}/topic/${encodeURIComponent(topicId)}`,
    request,
  );
  return data;
}

export async function deleteRoomTopic(roomId: string, topicId: string): Promise<Topic> {
  const { data } = await apiClient.delete<Topic>(
    `/api/room/${encodeURIComponent(roomId)}/topic/${encodeURIComponent(topicId)}`,
  );
  return data;
}

export async function deleteRoomMember(roomId: string, memberId: string): Promise<Member> {
  const { data } = await apiClient.delete<Member>(
    `/api/room/${encodeURIComponent(roomId)}/member/${encodeURIComponent(memberId)}`,
  );
  return data;
}
