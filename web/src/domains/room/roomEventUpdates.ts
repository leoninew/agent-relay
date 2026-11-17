import { fetchRoomActivity, fetchRoomMessageUpdates, fetchRoomMetadata } from "@/services/roomApi";
import type {
  MessageQuery,
  RoomActivity,
  RoomEvent,
  RoomMessage,
  RoomMetadata,
} from "@/services/roomApi";

export async function loadRoomEventUpdates(
  roomId: string,
  channelId: string,
  events: RoomEvent[],
  query: MessageQuery,
  retainedIds: Set<string>,
  signal?: AbortSignal,
): Promise<{ state: RoomActivity | RoomMetadata; messages: RoomMessage[] }> {
  const messageIds = [
    ...new Set(events.flatMap((event) => (event.messageId ? [event.messageId] : []))),
  ];
  const resourcesChanged = events.some((event) =>
    ["room", "topic", "member", "session"].includes(event.kind),
  );
  const [state, messages] = await Promise.all([
    resourcesChanged
      ? fetchRoomMetadata(roomId, signal, channelId)
      : fetchRoomActivity(roomId, signal, channelId),
    messageIds.length
      ? fetchRoomMessageUpdates(
          roomId,
          {
            messageIds,
            retainedIds: messageIds.filter((id) => retainedIds.has(id)),
            topicId: query.topicId,
            memberId: query.memberId,
            keyword: query.keyword,
          },
          signal,
          channelId,
        )
      : Promise.resolve([]),
  ]);
  return { state, messages };
}
