<template>
  <DropdownMenuRoot v-model:open="open" :modal="false">
    <DropdownMenuTrigger as-child>
      <button
        type="button"
        class="room-switcher-trigger"
        :aria-label="selectedRoom ? `选择聊天室：${selectedRoom.name}` : '选择聊天室'"
        :title="selectedRoom?.name"
      >
        <span>{{ selectedRoom?.name ?? "选择聊天室" }}</span>
        <AppIcon name="chevron-down" />
      </button>
    </DropdownMenuTrigger>
    <DropdownMenuPortal>
      <DropdownMenuContent
        class="room-switcher-menu"
        aria-label="选择聊天室"
        align="end"
        :side-offset="8"
        :collision-padding="12"
        loop
      >
        <AppLoading v-if="loading" class="switcher-state" />
        <template v-else-if="loadError">
          <p class="field-error" role="alert">{{ loadError }}</p>
          <DropdownMenuItem class="room-menu-action" @select.prevent="load">
            <AppIcon name="refresh" />重试
          </DropdownMenuItem>
        </template>
        <div v-else class="room-options">
          <p v-if="!roomsStore.rooms.length" class="switcher-state">暂无聊天室</p>
          <div v-for="room in roomsStore.rooms" :key="room.id" class="room-option-row">
            <DropdownMenuItem
              class="room-option"
              :class="{ 'is-selected': route.params.roomId === room.id }"
              :aria-current="route.params.roomId === room.id ? 'page' : undefined"
              @select="select(room.id)"
            >
              <span class="room-option-icon"><AppIcon name="chat" /></span>
              <span class="room-option-label">
                <span>{{ room.name }}</span>
                <span class="room-option-path" :title="room.projectPath">{{
                  room.projectPath
                }}</span>
              </span>
              <AppIcon v-if="route.params.roomId === room.id" name="check" />
            </DropdownMenuItem>
            <DropdownMenuItem as-child @select="startDelete(room)">
              <button
                type="button"
                class="room-delete-button"
                :aria-label="`删除聊天室：${room.name}`"
                :title="`删除聊天室：${room.name}`"
                :disabled="deleting"
              >
                <AppIcon name="trash" />
              </button>
            </DropdownMenuItem>
          </div>
        </div>
        <DropdownMenuSeparator class="room-menu-separator" />
        <DropdownMenuItem class="room-menu-action" @select="startCreate">
          <AppIcon name="plus" />新建聊天室
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenuPortal>
  </DropdownMenuRoot>
  <RoomSetupDialog
    :mode="roomsStore.createOpen ? 'room' : undefined"
    :topics="[]"
    :saving="saving"
    :error="createError"
    @close="roomsStore.createOpen = false"
    @create-room="saveRoom"
  />
  <RoomDeleteDialog
    :target="roomToDelete ? { kind: 'room', node: roomToDelete } : undefined"
    :saving="deleting"
    :error="deleteError"
    @close="roomToDelete = undefined"
    @confirm="deleteRoom"
  />
</template>

<script setup lang="ts">
  import {
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuPortal,
    DropdownMenuRoot,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
  } from "reka-ui";
  import { computed, nextTick, ref, watch } from "vue";
  import { useRoute, useRouter } from "vue-router";

  import AppIcon from "@/components/AppIcon.vue";
  import AppLoading from "@/components/AppLoading.vue";
  import RoomDeleteDialog from "@/domains/room/RoomDeleteDialog.vue";
  import RoomSetupDialog from "@/domains/room/RoomSetupDialog.vue";
  import { describeApiError } from "@/services/api";
  import type { CreateRoom, Room } from "@/services/roomApi";
  import { useRoomsStore } from "@/stores/rooms";
  import { useToastsStore } from "@/stores/toasts";

  const route = useRoute();
  const router = useRouter();
  const roomsStore = useRoomsStore();
  const toasts = useToastsStore();
  const selectedRoom = computed(() =>
    roomsStore.rooms.find((room) => room.id === route.params.roomId),
  );
  const open = ref(false);
  const loading = ref(false);
  const saving = ref(false);
  const loadError = ref<string | null>(null);
  const createError = ref<string | null>(null);
  const roomToDelete = ref<Room>();
  const deleting = ref(false);
  const deleteError = ref<string | null>(null);

  async function load(): Promise<void> {
    loading.value = true;
    loadError.value = null;
    try {
      await roomsStore.load();
    } catch (caught) {
      loadError.value = describeApiError(caught, "聊天室加载失败，请重试。");
    } finally {
      loading.value = false;
    }
  }

  async function select(roomId: string): Promise<void> {
    await router.push({ name: "room-detail", params: { roomId } });
    open.value = false;
  }

  async function startCreate(): Promise<void> {
    open.value = false;
    await nextTick();
    roomsStore.createOpen = true;
  }

  async function saveRoom(request: CreateRoom): Promise<void> {
    if (saving.value) return;
    saving.value = true;
    createError.value = null;
    try {
      const room = await roomsStore.create(request);
      roomsStore.createOpen = false;
      toasts.success("聊天室已创建");
      await router.push({ name: "room-detail", params: { roomId: room.id } });
    } catch (caught) {
      createError.value = describeApiError(caught, "创建失败，请重试。");
      toasts.error(createError.value);
    } finally {
      saving.value = false;
    }
  }

  async function startDelete(room: Room): Promise<void> {
    open.value = false;
    await nextTick();
    deleteError.value = null;
    roomToDelete.value = room;
  }

  async function deleteRoom(): Promise<void> {
    const room = roomToDelete.value;
    if (!room || deleting.value) return;
    deleting.value = true;
    deleteError.value = null;
    try {
      await roomsStore.remove(room.id);
    } catch (caught) {
      deleteError.value = describeApiError(caught, "删除失败，请重试。");
      return;
    } finally {
      deleting.value = false;
    }
    roomToDelete.value = undefined;
    toasts.success("聊天室已删除");
    if (route.params.roomId === room.id) {
      const nextRoom = roomsStore.rooms[0];
      await router.replace(
        nextRoom ? { name: "room-detail", params: { roomId: nextRoom.id } } : { name: "room" },
      );
    }
  }

  watch(open, (value) => {
    if (value) void load();
  });
  watch(
    () => roomsStore.createOpen,
    () => {
      createError.value = null;
    },
  );
</script>
