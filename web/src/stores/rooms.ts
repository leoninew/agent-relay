import { defineStore } from "pinia";
import { ref } from "vue";

import { useChannelsStore } from "@/stores/channels";
import { snapshotScope } from "@/domains/channel/channelRoutes";
import { roomCacheKey } from "@/services/cacheKeys";
import { removeRoomCacheStorage } from "@/services/cacheStorage";

import {
  addRoomTopic,
  clearRoom,
  createRoom,
  deleteRoom,
  fetchRooms,
  updateRoom,
} from "@/services/roomApi";
import type {
  ClearedRoom,
  CreateRoom,
  CreateTopic,
  MessagePage,
  MessageQuery,
  Room,
  RoomActivity,
  RoomMessage,
  RoomMetadata,
  RoomSnapshot,
  Topic,
  UpdateRoom,
} from "@/services/roomApi";

function orderedMessages(messages: RoomMessage[]): RoomMessage[] {
  return [...new Map(messages.map((message) => [message.id, message])).values()].sort(
    (left, right) => left.seq - right.seq,
  );
}

export const useRoomsStore = defineStore("rooms", () => {
  const rooms = ref<Room[]>([]);
  const recentRoomId = ref<string>();
  const createOpen = ref(false);
  const snapshots = ref<Record<string, RoomSnapshot>>({});
  const metadataVersions: Record<string, number> = {};
  const activityVersions: Record<string, number> = {};
  let pending: Promise<Room[]> | undefined;

  async function load(): Promise<void> {
    pending ??= fetchRooms();
    try {
      rooms.value = await pending;
    } finally {
      pending = undefined;
    }
  }

  async function create(request: CreateRoom): Promise<Room> {
    const room = await createRoom(request);
    rooms.value.push(room);
    return room;
  }

  async function remove(roomId: string): Promise<void> {
    await deleteRoom(roomId);
    for (const key of Object.keys(snapshots.value)) {
      if (key.startsWith(`${roomCacheKey(roomId)}:channel:`)) {
        delete snapshots.value[key];
      }
    }
    for (const key of Object.keys(metadataVersions)) {
      if (key.startsWith(`${roomCacheKey(roomId)}:channel:`)) {
        delete metadataVersions[key];
      }
    }
    for (const key of Object.keys(activityVersions)) {
      if (key.startsWith(`${roomCacheKey(roomId)}:channel:`)) {
        delete activityVersions[key];
      }
    }
    useChannelsStore().reset(roomId);
    removeRoomCacheStorage(roomId);
    rooms.value = rooms.value.filter((room) => room.id !== roomId);
    if (recentRoomId.value === roomId) {
      recentRoomId.value = undefined;
    }
  }

  async function update(roomId: string, request: UpdateRoom): Promise<Room> {
    const room = await updateRoom(roomId, request);
    updateRoomName(room);
    for (const [scope, snapshot] of Object.entries(snapshots.value)) {
      if (scope.startsWith(`${roomCacheKey(room.id)}:channel:`)) {
        snapshot.room = room;
      }
    }
    return room;
  }

  async function clear(roomId: string, channelId: string): Promise<ClearedRoom> {
    const result = await clearRoom(roomId, channelId);
    sync(
      {
        ...result.metadata,
        messages: [],
        hasMore: false,
        hasNewer: false,
        nextBeforeSeq: null,
      },
      channelId,
    );
    return result;
  }

  function snapshotKey(roomId: string, channelId: string): string {
    return snapshotScope(roomId, channelId);
  }

  function sync(snapshot: RoomSnapshot, channelId: string): void {
    const scope = snapshotScope(snapshot.room.id, channelId);
    snapshots.value[scope] = snapshot;
    metadataVersions[scope] = snapshot.eventId;
    activityVersions[scope] = snapshot.eventId;
    updateRoomName(snapshot.room);
  }

  function updateRoomName(room: Room): void {
    const index = rooms.value.findIndex((candidate) => candidate.id === room.id);
    if (index !== -1) {
      rooms.value.splice(index, 1, room);
    }
  }

  function syncMetadata(metadata: RoomMetadata, channelId: string): void {
    const scope = snapshotScope(metadata.room.id, channelId);
    const snapshot = snapshots.value[scope];
    if (!snapshot || metadata.eventId < (metadataVersions[scope] ?? 0)) {
      return;
    }
    metadataVersions[scope] = metadata.eventId;
    snapshot.room = metadata.room;
    snapshot.topics = metadata.topics;
    snapshot.members = metadata.members;
    snapshot.sessions = metadata.sessions;
    syncActivity(metadata.room.id, metadata, channelId);
    updateRoomName(metadata.room);
  }

  function syncActivity(roomId: string, activity: RoomActivity, channelId: string): void {
    const scope = snapshotScope(roomId, channelId);
    const snapshot = snapshots.value[scope];
    if (!snapshot || activity.eventId < (activityVersions[scope] ?? 0)) {
      return;
    }
    activityVersions[scope] = activity.eventId;
    snapshot.positions = activity.positions;
    snapshot.summary = activity.summary;
  }

  function prependPage(roomId: string, page: MessagePage, channelId: string): void {
    const scope = snapshotScope(roomId, channelId);
    const snapshot = snapshots.value[scope];
    snapshot.messages = orderedMessages([...page.messages, ...snapshot.messages]);
    snapshot.hasMore = page.hasMore;
    snapshot.nextBeforeSeq = page.nextBeforeSeq;
  }

  function applyMessages(
    roomId: string,
    messages: RoomMessage[],
    query: MessageQuery,
    channelId: string,
  ): void {
    const scope = snapshotScope(roomId, channelId);
    const snapshot = snapshots.value[scope];
    const included = new Set(snapshot.messages.map((message) => message.id));
    const newestSeq = snapshot.messages.at(-1)?.seq ?? 0;
    const updates = messages.filter(
      (message) =>
        included.has(message.id) ||
        (!snapshot.hasNewer &&
          message.seq > newestSeq &&
          (!query.topicId || message.topicIds.includes(query.topicId)) &&
          (!query.memberId ||
            message.senderId === query.memberId ||
            message.recipientIds.includes(query.memberId)) &&
          (!query.keyword || message.content.includes(query.keyword))),
    );
    snapshot.messages = orderedMessages([...snapshot.messages, ...updates]);
  }

  async function createTopic(
    roomId: string,
    request: CreateTopic,
    channelId: string,
  ): Promise<Topic> {
    const topic = await addRoomTopic(roomId, request, channelId);
    syncMetadata(topic.metadata, channelId);
    return topic;
  }

  return {
    rooms,
    recentRoomId,
    createOpen,
    snapshots,
    snapshotKey,
    load,
    create,
    update,
    remove,
    clear,
    sync,
    syncMetadata,
    syncActivity,
    prependPage,
    applyMessages,
    createTopic,
  };
});
