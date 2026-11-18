import type { MessageQuery, RoomSnapshot } from "@/services/roomApi";

export function messageQueryKey(
  roomId: string | undefined,
  channelId: string | undefined,
  query: MessageQuery,
): string {
  return JSON.stringify([
    roomId,
    channelId,
    query.topicId || null,
    query.memberId || null,
    query.keyword?.trim() || null,
  ]);
}

export function mergeRefreshedSnapshot(
  previous: RoomSnapshot,
  incoming: RoomSnapshot,
): RoomSnapshot {
  const firstSeq = incoming.messages[0]?.seq;
  const incomingIds = new Set(incoming.messages.map((message) => message.id));
  if (firstSeq === undefined || !previous.messages.some((message) => incomingIds.has(message.id))) {
    return incoming;
  }
  const older = previous.messages.filter((message) => message.seq < firstSeq);
  if (!older.length) {
    return incoming;
  }
  return {
    ...incoming,
    messages: [...older, ...incoming.messages],
    hasMore: previous.hasMore,
    nextBeforeSeq: previous.nextBeforeSeq,
  };
}
