import { defineStore } from "pinia";
import { ref } from "vue";

import { addRoomTopic, createRoom, fetchRooms } from "@/services/roomApi";
import type { CreateRoom, CreateTopic, Room, RoomSnapshot, Topic } from "@/services/roomApi";

type RoomCatalog = { topics: Topic[] };

export const useRoomsStore = defineStore("rooms", () => {
  const rooms = ref<Room[]>([]);
  const loaded = ref(false);
  const createOpen = ref(false);
  const catalogs = ref<Record<string, RoomCatalog>>({});
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

  function syncCatalog(snapshot: RoomSnapshot): void {
    const roomId = snapshot.room.id;
    catalogs.value[roomId] = {
      topics: snapshot.topics,
    };
  }

  async function createTopic(roomId: string, request: CreateTopic): Promise<Topic> {
    const topic = await addRoomTopic(roomId, request);
    catalogs.value[roomId].topics.push(topic);
    return topic;
  }

  return {
    rooms,
    loaded,
    createOpen,
    catalogs,
    load,
    create,
    syncCatalog,
    createTopic,
  };
});
