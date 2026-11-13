import { defineStore } from "pinia";
import { ref } from "vue";

import { createMessageDraftStorage } from "@/stores/messageDrafts";

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
    createMessageDraftStorage().remove(roomId);
    rooms.value = rooms.value.filter((room) => room.id !== roomId);
    if (recentRoomId.value === roomId) recentRoomId.value = undefined;
    delete snapshots.value[roomId];
    delete metadataVersions[roomId];
  }

  async function rename(roomId: string, name: string): Promise<Room> {
    const room = await updateRoom(roomId, { name });
    updateRoomName(room);
    const snapshot = snapshots.value[room.id];
    if (snapshot) snapshot.room = room;
    return room;
  }

  async function clear(roomId: string): Promise<ClearedRoom> {
    const result = await clearRoom(roomId);
    sync({
      ...result.metadata,
      messages: [],
      hasMore: false,
      hasNewer: false,
      nextBeforeSeq: null,
    });
    return result;
  }

  function sync(snapshot: RoomSnapshot): void {
    snapshots.value[snapshot.room.id] = snapshot;
    metadataVersions[snapshot.room.id] = snapshot.eventId;
    updateRoomName(snapshot.room);
  }

  function updateRoomName(room: Room): void {
    const index = rooms.value.findIndex((candidate) => candidate.id === room.id);
    if (index !== -1) rooms.value.splice(index, 1, room);
  }

  function syncMetadata(metadata: RoomMetadata): void {
    const snapshot = snapshots.value[metadata.room.id];
    if (!snapshot || metadata.eventId < (metadataVersions[metadata.room.id] ?? 0)) return;
    metadataVersions[metadata.room.id] = metadata.eventId;
    snapshot.room = metadata.room;
    snapshot.topics = metadata.topics;
    snapshot.members = metadata.members;
    snapshot.sessions = metadata.sessions;
    snapshot.positions = metadata.positions;
    snapshot.summary = metadata.summary;
    updateRoomName(metadata.room);
  }

  function prependPage(roomId: string, page: MessagePage): void {
    const snapshot = snapshots.value[roomId];
    snapshot.messages = orderedMessages([...page.messages, ...snapshot.messages]);
    snapshot.hasMore = page.hasMore;
    snapshot.nextBeforeSeq = page.nextBeforeSeq;
  }

  function applyMessages(roomId: string, messages: RoomMessage[], query: MessageQuery): void {
    const snapshot = snapshots.value[roomId];
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

  async function createTopic(roomId: string, request: CreateTopic): Promise<Topic> {
    const topic = await addRoomTopic(roomId, request);
    syncMetadata(topic.metadata);
    return topic;
  }

  return {
    rooms,
    loaded,
    recentRoomId,
    createOpen,
    snapshots,
    load,
    create,
    rename,
    remove,
    clear,
    sync,
    syncMetadata,
    prependPage,
    applyMessages,
    createTopic,
  };
});
