import { defineStore } from "pinia";
import { ref } from "vue";

import { createMessageDraftStorage } from "@/stores/messageDrafts";
import { snapshotScope } from "@/domains/channel/channelRoutes";

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
  const loaded = ref(false);
  const recentRoomId = ref<string>();
  const createOpen = ref(false);
  const snapshots = ref<Record<string, RoomSnapshot>>({});
  const metadataVersions: Record<string, number> = {};
  let pending: Promise<Room[]> | undefined;

  async function load(): Promise<void> {
    if (loaded.value) return;
    pending ??= fetchRooms();
    try {
      rooms.value = await pending;
      loaded.value = true;
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
      if (key.startsWith(`${roomId}:`)) {
        delete snapshots.value[key];
        createMessageDraftStorage().remove(key);
      }
    }
    for (const key of Object.keys(metadataVersions)) {
      if (key.startsWith(`${roomId}:`)) delete metadataVersions[key];
    }
    rooms.value = rooms.value.filter((room) => room.id !== roomId);
    if (recentRoomId.value === roomId) recentRoomId.value = undefined;
  }

  async function update(roomId: string, request: UpdateRoom): Promise<Room> {
    const room = await updateRoom(roomId, request);
    updateRoomName(room);
    for (const [scope, snapshot] of Object.entries(snapshots.value)) {
      if (scope.startsWith(`${room.id}:`)) snapshot.room = room;
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
    updateRoomName(snapshot.room);
  }

  function updateRoomName(room: Room): void {
    const index = rooms.value.findIndex((candidate) => candidate.id === room.id);
    if (index !== -1) rooms.value.splice(index, 1, room);
  }

  function syncMetadata(metadata: RoomMetadata, channelId: string): void {
    const scope = snapshotScope(metadata.room.id, channelId);
    const snapshot = snapshots.value[scope];
    if (!snapshot || metadata.eventId < (metadataVersions[scope] ?? 0)) return;
    metadataVersions[scope] = metadata.eventId;
    snapshot.room = metadata.room;
    snapshot.topics = metadata.topics;
    snapshot.members = metadata.members;
    snapshot.sessions = metadata.sessions;
    snapshot.positions = metadata.positions;
    snapshot.summary = metadata.summary;
    updateRoomName(metadata.room);
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
    loaded,
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
    prependPage,
    applyMessages,
    createTopic,
  };
});
