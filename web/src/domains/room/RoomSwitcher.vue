<template>
  <div class="room-navigation">
    <div class="room-navigation-projects">
      <NavigationMenuRoot
        v-if="!loading && !loadError && roomsStore.rooms.length"
        class="room-navigation-menu"
        :disable-hover-trigger="true"
        aria-label="项目"
      >
        <NavigationMenuList class="room-tab-list">
          <NavigationMenuItem
            v-for="room in roomsStore.rooms"
            :key="room.id"
            class="room-tab-row"
            :class="{ 'is-current': route.params.roomId === room.id }"
          >
            <NavigationMenuLink as-child :active="route.params.roomId === room.id">
              <RouterLink
                :to="{ name: 'room-detail', params: { roomId: room.id } }"
                class="room-tab"
                :aria-label="`切换项目：${room.name}`"
                :title="room.name"
              >
                <span class="room-tab-name">{{ room.name }}</span>
              </RouterLink>
            </NavigationMenuLink>
            <DropdownMenuRoot :modal="false">
              <DropdownMenuTrigger as-child>
                <button
                  type="button"
                  class="room-tab-menu-button"
                  :aria-label="`管理项目：${room.name}`"
                  :title="`管理项目：${room.name}`"
                >
                  <span aria-hidden="true">...</span>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuPortal>
                <DropdownMenuContent
                  class="room-switcher-menu"
                  :aria-label="`管理项目：${room.name}`"
                  side="bottom"
                  align="start"
                  :side-offset="8"
                  :collision-padding="12"
                >
                  <DropdownMenuItem class="room-menu-action" @select="startEdit(room)">
                    <AppIcon name="edit" />编辑名称
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    class="room-menu-action room-menu-danger"
                    @select="startDelete(room)"
                  >
                    <AppIcon name="trash" />删除
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenuPortal>
            </DropdownMenuRoot>
          </NavigationMenuItem>
          <NavigationMenuItem class="room-tab-add">
            <button
              type="button"
              class="room-navigation-action"
              aria-label="新建聊天室"
              title="新建聊天室"
              @click="startCreate"
            >
              <AppIcon name="plus" />
            </button>
          </NavigationMenuItem>
        </NavigationMenuList>
      </NavigationMenuRoot>
      <p v-else-if="loading" class="room-navigation-state" role="status">加载中…</p>
      <div v-else-if="loadError" class="room-navigation-state">
        <span role="alert">{{ loadError }}</span>
        <button type="button" class="room-navigation-retry" @click="load">重试</button>
      </div>
      <div v-else class="room-navigation-state">
        <span>暂无聊天室</span>
        <button
          type="button"
          class="room-navigation-action"
          aria-label="新建聊天室"
          title="新建聊天室"
          @click="startCreate"
        >
          <AppIcon name="plus" />
        </button>
      </div>
    </div>
  </div>
  <RoomSetupDialog
    :mode="roomDialogMode"
    :room="editingRoom"
    :topics="[]"
    :saving="saving"
    :error="roomDialogError"
    @close="closeRoomDialog"
    @create-room="saveRoom"
    @update-room="renameRoom"
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
    DropdownMenuTrigger,
    NavigationMenuItem,
    NavigationMenuLink,
    NavigationMenuList,
    NavigationMenuRoot,
  } from "reka-ui";
  import { computed, nextTick, onMounted, ref, watch } from "vue";
  import { RouterLink, useRoute, useRouter } from "vue-router";

  import AppIcon from "@/components/AppIcon.vue";
  import RoomDeleteDialog from "@/domains/room/RoomDeleteDialog.vue";
  import RoomSetupDialog from "@/domains/room/RoomSetupDialog.vue";
  import { describeApiError } from "@/services/api";
  import type { CreateRoom, Room, UpdateRoom } from "@/services/roomApi";
  import { useRoomsStore } from "@/stores/rooms";
  import { useToastsStore } from "@/stores/toasts";

  const route = useRoute();
  const router = useRouter();
  const roomsStore = useRoomsStore();
  const toasts = useToastsStore();
  const loading = ref(false);
  const saving = ref(false);
  const loadError = ref<string | null>(null);
  const createError = ref<string | null>(null);
  const editingRoom = ref<Room>();
  const renameError = ref<string | null>(null);
  const roomToDelete = ref<Room>();
  const deleting = ref(false);
  const deleteError = ref<string | null>(null);
  const roomDialogMode = computed(() =>
    roomsStore.createOpen || editingRoom.value ? "room" : undefined,
  );
  const roomDialogError = computed(() =>
    editingRoom.value ? renameError.value : createError.value,
  );

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

  async function startCreate(): Promise<void> {
    editingRoom.value = undefined;
    renameError.value = null;
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

  async function startEdit(room: Room): Promise<void> {
    roomsStore.createOpen = false;
    await nextTick();
    renameError.value = null;
    editingRoom.value = room;
  }

  async function renameRoom(request: UpdateRoom): Promise<void> {
    const room = editingRoom.value;
    if (!room || saving.value) return;
    saving.value = true;
    renameError.value = null;
    try {
      await roomsStore.rename(room.id, request.name);
      editingRoom.value = undefined;
      toasts.success("聊天室名称已更新");
    } catch (caught) {
      renameError.value = describeApiError(caught, "保存失败，请重试。");
      toasts.error(renameError.value);
    } finally {
      saving.value = false;
    }
  }

  function closeRoomDialog(): void {
    roomsStore.createOpen = false;
    editingRoom.value = undefined;
    renameError.value = null;
  }

  async function startDelete(room: Room): Promise<void> {
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

  onMounted(() => {
    if (!roomsStore.loaded) void load();
  });
  watch(
    () => roomsStore.createOpen,
    (open) => {
      if (open) createError.value = null;
    },
  );
</script>
