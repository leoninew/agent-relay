<template>
  <div class="room-navigation">
    <div class="room-navigation-projects">
      <NavigationMenuRoot
        v-if="!loading && !loadError && roomsStore.rooms.length"
        class="room-navigation-menu"
        :disable-hover-trigger="true"
        :aria-label="t('navigation.projects')"
      >
        <NavigationMenuList as-child>
          <VueDraggable
            v-model="rooms"
            tag="ul"
            class="room-tab-list"
            draggable=".room-tab-row"
            handle=".room-tab"
            direction="horizontal"
            ghost-class="room-tab-drag-ghost"
            chosen-class="room-tab-drag-chosen"
            :animation="150"
            :delay="150"
            :delay-on-touch-only="true"
            :disabled="rooms.length < 2"
          >
            <NavigationMenuItem
              v-for="room in rooms"
              :key="room.id"
              class="room-tab-row"
              :class="{ 'is-current': route.params.roomId === room.id }"
            >
              <NavigationMenuLink as-child :active="route.params.roomId === room.id">
                <RouterLink
                  :to="{ name: 'room-detail', params: { roomId: room.id } }"
                  class="room-tab"
                  :aria-label="t('navigation.switchProject', { name: room.name })"
                  :title="t('navigation.reorderProject', { name: room.name })"
                  aria-keyshortcuts="Alt+ArrowLeft Alt+ArrowRight"
                  @keydown.alt.left.prevent.stop="moveRoom(room.id, -1)"
                  @keydown.alt.right.prevent.stop="moveRoom(room.id, 1)"
                >
                  <span class="room-tab-name">{{ room.name }}</span>
                </RouterLink>
              </NavigationMenuLink>
              <DropdownMenuRoot :modal="false">
                <DropdownMenuTrigger as-child>
                  <button
                    type="button"
                    class="room-tab-menu-button"
                    :aria-label="t('navigation.manageProject', { name: room.name })"
                    :title="t('navigation.manageProject', { name: room.name })"
                  >
                    <span aria-hidden="true">...</span>
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuPortal>
                  <DropdownMenuContent
                    class="room-switcher-menu"
                    :aria-label="t('navigation.manageProject', { name: room.name })"
                    side="bottom"
                    align="start"
                    :side-offset="8"
                    :collision-padding="12"
                  >
                    <DropdownMenuItem class="room-menu-action" @select="startEdit(room)">
                      <AppIcon name="edit" />{{ t("navigation.editName") }}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      class="room-menu-action room-menu-danger"
                      @select="startDelete(room)"
                    >
                      <AppIcon name="trash" />{{ t("common.delete") }}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenuPortal>
              </DropdownMenuRoot>
            </NavigationMenuItem>
            <NavigationMenuItem class="room-tab-add">
              <button
                type="button"
                class="room-navigation-action"
                :aria-label="t('room.create')"
                :title="t('room.create')"
                @click="startCreate"
              >
                <AppIcon name="plus" />
              </button>
            </NavigationMenuItem>
          </VueDraggable>
        </NavigationMenuList>
      </NavigationMenuRoot>
      <p v-else-if="loading" class="room-navigation-state" role="status">
        {{ t("common.loading") }}
      </p>
      <div v-else-if="loadError" class="room-navigation-state">
        <span role="alert">{{ translateMessage(loadError) }}</span>
        <button type="button" class="room-navigation-retry" @click="load">
          {{ t("common.retry") }}
        </button>
      </div>
      <div v-else class="room-navigation-state">
        <span>{{ t("navigation.noRooms") }}</span>
        <button
          type="button"
          class="room-navigation-action"
          :aria-label="t('room.create')"
          :title="t('room.create')"
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
  import { VueDraggable } from "vue-draggable-plus";
  import { useI18n } from "vue-i18n";
  import { translateMessage } from "@/i18n";
  import type { MessageDescriptor } from "@/i18n";

  import AppIcon from "@/components/AppIcon.vue";
  import { useStoredOrder } from "@/composables/useStoredOrder";
  import RoomDeleteDialog from "@/domains/room/RoomDeleteDialog.vue";
  import RoomSetupDialog from "@/domains/room/RoomSetupDialog.vue";
  import { describeApiError } from "@/services/api";
  import type { CreateRoom, Room, UpdateRoom } from "@/services/roomApi";
  import { useRoomsStore } from "@/stores/rooms";
  import { useToastsStore } from "@/stores/toasts";

  const { t } = useI18n();
  const route = useRoute();
  const router = useRouter();
  const roomsStore = useRoomsStore();
  const { orderedItems: rooms, moveItem: moveRoom } = useStoredOrder(
    () => "relay-room-order",
    () => roomsStore.rooms,
  );
  const toasts = useToastsStore();
  const loading = ref(false);
  const saving = ref(false);
  const loadError = ref<MessageDescriptor | null>(null);
  const createError = ref<MessageDescriptor | null>(null);
  const editingRoom = ref<Room>();
  const renameError = ref<MessageDescriptor | null>(null);
  const roomToDelete = ref<Room>();
  const deleting = ref(false);
  const deleteError = ref<MessageDescriptor | null>(null);
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
      loadError.value = describeApiError(caught, "errors.roomLoad");
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
      toasts.success({ key: "notice.roomCreated" });
      await router.push({ name: "room-detail", params: { roomId: room.id } });
    } catch (caught) {
      createError.value = describeApiError(caught, "errors.create");
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
      toasts.success({ key: "notice.roomRenamed" });
    } catch (caught) {
      renameError.value = describeApiError(caught, "errors.save");
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
      deleteError.value = describeApiError(caught, "errors.remove");
      return;
    } finally {
      deleting.value = false;
    }
    roomToDelete.value = undefined;
    toasts.success({ key: "notice.roomDeleted" });
    if (route.params.roomId === room.id) {
      const nextRoom = rooms.value[0];
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
