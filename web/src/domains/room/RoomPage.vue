<template>
  <div v-if="!snapshot" class="room-initial-state">
    <template v-if="loading">
      <AppIcon name="relay" />
      <h1>正在连接协作空间</h1>
      <AppLoading>正在加载房间、话题和消息…</AppLoading>
    </template>
    <template v-else-if="loadError">
      <AppIcon name="chat" />
      <h1>暂时无法打开聊天室</h1>
      <p role="alert">{{ loadError }}</p>
      <AppButton @click="retry">重新加载</AppButton>
    </template>
    <template v-else>
      <AppIcon name="chat" />
      <h1>暂无项目聊天室</h1>
      <AppButton @click="roomsStore.createOpen = true"> 新建聊天室 </AppButton>
    </template>
  </div>
  <div v-else class="room-workbench" :class="{ 'has-hidden-details': !detailsOpen }">
    <TopicSidebar
      :snapshot="snapshot"
      :busy="sending || saving"
      :selected-topic-id="selectedTopicId"
      :selected-member-id="selectedMemberId"
      @select="selectTopic"
      @create-topic="openSetup('topic')"
      @edit-topic="editTopic"
      @delete-topic="openDelete({ kind: 'topic', node: $event })"
    >
      <MemberPanel
        :snapshot="snapshot"
        :busy="sending || saving"
        :selected-topic-id="selectedTopicId"
        :selected-member-id="selectedMemberId"
        @select="selectMember"
        @add-member="openSetup('member')"
        @edit-member="editMember"
        @delete-member="openDelete({ kind: 'member', node: $event })"
      />
    </TopicSidebar>

    <section class="conversation-panel" aria-label="聊天室">
      <header class="conversation-heading">
        <div class="conversation-title">
          <h2>聊天室</h2>
        </div>
        <div class="conversation-tools">
          <AppButton
            variant="plain"
            class="conversation-refresh"
            :loading="loading"
            loading-label="刷新中…"
            :disabled="sending"
            @click="loadRoom"
          >
            <template #icon><AppIcon name="refresh" /></template>
            刷新会话
          </AppButton>
        </div>
      </header>
      <div v-if="loadError" class="room-alert" role="alert">
        <span>{{ loadError }}</span>
        <button type="button" @click="loadRoom">重试</button>
      </div>
      <MessageTimeline
        ref="timeline"
        :messages="visibleMessages"
        :unavailable="loadError !== null"
        :members="snapshot.members"
        :topics="snapshot.topics"
        :selected-message-id="selectedMessage?.id"
        :details-open="detailsOpen"
        :loading="loading"
        @reply="replyTo = $event"
        @reference="showReference"
        @select="selectedMessageId = $event"
        @show-details="detailsOpen = true"
      />
      <RoomComposer
        :key="snapshot.room.id"
        ref="composer"
        :room-id="snapshot.room.id"
        :draft="drafts[snapshot.room.id]"
        :topics="activeTopics"
        :members="activeMembers"
        :default-topic-id="selectedTopicId"
        :reply-to="replyTo"
        :sending="sending"
        :error="sendError"
        @send="sendMessage"
        @draft="saveDraft"
        @cancel-reply="replyTo = undefined"
      />
    </section>

    <MessageDetails
      v-if="detailsOpen"
      :message="selectedMessage"
      :topics="snapshot.topics"
      :members="snapshot.members"
      @close="detailsOpen = false"
    />
  </div>
  <RoomSetupDialog
    :mode="setupMode"
    :topics="activeTopics"
    :saving="saving"
    :error="setupError"
    :sessions="sessions"
    :sessions-loading="sessionsLoading"
    :sessions-error="sessionsError"
    :room-id="currentRoomId"
    :member="editingMember"
    :linked-session="roomData?.sessions.find((session) => session.id === editingMember?.sessionId)"
    :topic="editingTopic"
    @close="setupMode = undefined"
    @create-member="saveNewMember"
    @update-member="saveMember"
    @create-topic="saveNewTopic"
    @update-topic="saveTopic"
    @reload-sessions="loadSessions"
  />
  <RoomDeleteDialog
    :target="deleteTarget"
    :saving="saving"
    :error="setupError"
    @close="deleteTarget = undefined"
    @confirm="deleteNode"
  />
</template>

<script setup lang="ts">
  import { computed, nextTick, onMounted, ref, watch } from "vue";
  import { useRouter } from "vue-router";

  import AppButton from "@/components/AppButton.vue";
  import AppIcon from "@/components/AppIcon.vue";
  import AppLoading from "@/components/AppLoading.vue";
  import MemberPanel from "@/domains/room/MemberPanel.vue";
  import MessageDetails from "@/domains/room/MessageDetails.vue";
  import MessageTimeline from "@/domains/room/MessageTimeline.vue";
  import RoomComposer from "@/domains/room/RoomComposer.vue";
  import RoomDeleteDialog from "@/domains/room/RoomDeleteDialog.vue";
  import type { DeleteTarget } from "@/domains/room/RoomDeleteDialog.vue";
  import RoomSetupDialog from "@/domains/room/RoomSetupDialog.vue";
  import TopicSidebar from "@/domains/room/TopicSidebar.vue";
  import { describeApiError } from "@/services/api";
  import {
    addRoomMember,
    deleteRoomMember,
    deleteRoomTopic,
    fetchRoom,
    fetchRoomSessions,
    postRoomMessage,
    updateRoomMember,
    updateRoomTopic,
  } from "@/services/roomApi";
  import type {
    CreateMember,
    CreateMessage,
    CreateTopic,
    Member,
    RoomMessage,
    RoomSnapshot,
    SessionCandidate,
    Topic,
    UpdateMember,
  } from "@/services/roomApi";
  import { useRoomsStore } from "@/stores/rooms";
  import { useToastsStore } from "@/stores/toasts";

  import "./room.css";

  const props = defineProps<{ roomId?: string }>();
  const router = useRouter();
  const roomsStore = useRoomsStore();
  const toasts = useToastsStore();
  const currentRoomId = ref<string>();
  const roomData = ref<RoomSnapshot>();
  const currentCatalog = computed(() =>
    currentRoomId.value ? roomsStore.catalogs[currentRoomId.value] : undefined,
  );
  const snapshot = computed(() =>
    roomData.value ? { ...roomData.value, topics: currentCatalog.value?.topics ?? [] } : undefined,
  );
  const selectedTopicId = ref<string>();
  const selectedMemberId = ref<string>();
  const activeTopics = computed(
    () => snapshot.value?.topics.filter((topic) => !topic.deletedAt) ?? [],
  );
  const activeMembers = computed(
    () => snapshot.value?.members.filter((member) => !member.deletedAt) ?? [],
  );
  const visibleMessages = computed(
    () =>
      snapshot.value?.messages.filter(
        (message) => !selectedMemberId.value || message.senderId === selectedMemberId.value,
      ) ?? [],
  );
  const selectedMessageId = ref<string>();
  const selectedMessage = computed(() => {
    const messages = visibleMessages.value;
    return messages.find((message) => message.id === selectedMessageId.value) ?? messages.at(-1);
  });
  const detailsOpen = ref(true);
  const loading = ref(true);
  const sending = ref(false);
  const loadError = ref<string | null>(null);
  const sendError = ref<string | null>(null);
  const replyTo = ref<RoomMessage>();
  const composer = ref<InstanceType<typeof RoomComposer>>();
  const timeline = ref<InstanceType<typeof MessageTimeline>>();
  const drafts = ref<Record<string, CreateMessage>>({});
  const setupMode = ref<"member" | "topic">();
  const editingMember = ref<Member>();
  const editingTopic = ref<Topic>();
  const deleteTarget = ref<DeleteTarget>();
  const saving = ref(false);
  const setupError = ref<string | null>(null);
  const sessions = ref<SessionCandidate[]>([]);
  const sessionsLoading = ref(false);
  const sessionsError = ref<string | null>(null);
  let sessionsVersion = 0;
  let loadVersion = 0;

  async function loadRoom(): Promise<boolean> {
    if (!currentRoomId.value) return false;
    const version = ++loadVersion;
    loading.value = true;
    loadError.value = null;
    try {
      const result = await fetchRoom(currentRoomId.value, selectedTopicId.value);
      if (version !== loadVersion) return false;
      if (
        selectedMemberId.value &&
        !result.members.some((member) => member.id === selectedMemberId.value && !member.deletedAt)
      )
        selectedMemberId.value = undefined;
      roomsStore.syncCatalog(result);
      roomData.value = result;
      return true;
    } catch (caught) {
      if (version === loadVersion) {
        loadError.value = describeApiError(caught, "消息加载失败，请稍后重试。");
        toasts.error(loadError.value);
      }
      return false;
    } finally {
      if (version === loadVersion) loading.value = false;
    }
  }

  async function initialize(): Promise<void> {
    loading.value = true;
    loadError.value = null;
    try {
      await roomsStore.load();
      if (props.roomId) await openRoom(props.roomId);
      else if (roomsStore.rooms.length)
        await router.replace({ name: "room-detail", params: { roomId: roomsStore.rooms[0].id } });
      else loading.value = false;
    } catch (caught) {
      loadError.value = describeApiError(caught, "聊天室加载失败，请稍后重试。");
      toasts.error(loadError.value);
      loading.value = false;
    }
  }

  async function openRoom(roomId: string): Promise<void> {
    currentRoomId.value = roomId;
    roomData.value = undefined;
    setupMode.value = undefined;
    editingMember.value = undefined;
    editingTopic.value = undefined;
    deleteTarget.value = undefined;
    sessionsVersion++;
    sessions.value = [];
    sessionsLoading.value = false;
    sessionsError.value = null;
    selectedTopicId.value = undefined;
    selectedMemberId.value = undefined;
    selectedMessageId.value = undefined;
    detailsOpen.value = true;
    replyTo.value = undefined;
    sendError.value = null;
    await loadRoom();
    await nextTick();
    timeline.value?.scrollToEnd();
  }

  async function retry(): Promise<void> {
    if (currentRoomId.value) await loadRoom();
    else await initialize();
  }

  function saveDraft(roomId: string, draft: CreateMessage): void {
    drafts.value[roomId] = draft;
  }

  async function selectTopic(topicId?: string): Promise<void> {
    selectedTopicId.value = topicId;
    selectedMemberId.value = undefined;
    await loadRoom();
    await nextTick();
    timeline.value?.scrollToEnd();
  }

  async function selectMember(memberId: string): Promise<void> {
    selectedMemberId.value = selectedMemberId.value === memberId ? undefined : memberId;
    await nextTick();
    timeline.value?.scrollToEnd();
  }

  async function sendMessage(request: CreateMessage): Promise<void> {
    if (sending.value || !currentRoomId.value) return;
    const roomId = currentRoomId.value;
    sending.value = true;
    sendError.value = null;
    let sentMessage: RoomMessage;
    try {
      sentMessage = await postRoomMessage(roomId, request);
    } catch (caught) {
      const message = describeApiError(caught, "发送失败，草稿已保留，请稍后重试。");
      if (roomId === currentRoomId.value) sendError.value = message;
      toasts.error(message);
      sending.value = false;
      return;
    }
    if (roomId !== currentRoomId.value) {
      sending.value = false;
      return;
    }
    selectedMessageId.value = sentMessage.id;
    composer.value?.reset();
    replyTo.value = undefined;
    toasts.success("消息已发送");
    if (selectedTopicId.value && !request.topicIds.includes(selectedTopicId.value)) {
      selectedTopicId.value = request.topicIds[0];
    }
    await loadRoom();
    sending.value = false;
    await nextTick();
    timeline.value?.scrollToEnd();
  }

  function openSetup(mode: "member" | "topic"): void {
    setupError.value = null;
    editingMember.value = undefined;
    editingTopic.value = undefined;
    deleteTarget.value = undefined;
    setupMode.value = mode;
    if (mode === "member") void loadSessions();
  }

  async function loadSessions(): Promise<void> {
    if (!currentRoomId.value) return;
    const roomId = currentRoomId.value;
    const version = ++sessionsVersion;
    sessionsLoading.value = true;
    sessionsError.value = null;
    try {
      const result = await fetchRoomSessions(roomId);
      if (version === sessionsVersion) sessions.value = result;
    } catch (caught) {
      if (version === sessionsVersion) {
        sessions.value = [];
        sessionsError.value = describeApiError(caught, "会话加载失败，请刷新重试。");
      }
    } finally {
      if (version === sessionsVersion) sessionsLoading.value = false;
    }
  }

  function editMember(member: Member): void {
    setupError.value = null;
    editingTopic.value = undefined;
    deleteTarget.value = undefined;
    editingMember.value = member;
    setupMode.value = "member";
  }

  function editTopic(topic: Topic): void {
    setupError.value = null;
    editingMember.value = undefined;
    editingTopic.value = topic;
    deleteTarget.value = undefined;
    setupMode.value = "topic";
  }

  function openDelete(target: DeleteTarget): void {
    setupMode.value = undefined;
    setupError.value = null;
    deleteTarget.value = target;
  }

  async function saveSetup(action: () => Promise<void>, successMessage: string): Promise<void> {
    if (saving.value) return;
    saving.value = true;
    setupError.value = null;
    const roomId = currentRoomId.value;
    try {
      await action();
      toasts.success(successMessage);
      if (roomId === currentRoomId.value) setupMode.value = undefined;
    } catch (caught) {
      const message = describeApiError(caught, "保存失败，请稍后重试。");
      if (roomId === currentRoomId.value) setupError.value = message;
      toasts.error(message);
    } finally {
      saving.value = false;
    }
  }

  async function saveNewMember(request: CreateMember): Promise<void> {
    if (!currentRoomId.value) return;
    const roomId = currentRoomId.value;
    await saveSetup(async () => {
      const { session, ...member } = await addRoomMember(roomId, request);
      if (roomData.value?.room.id === roomId) {
        roomData.value.members.push(member);
        const index = roomData.value.sessions.findIndex((saved) => saved.id === session.id);
        if (index === -1) roomData.value.sessions.push(session);
        else roomData.value.sessions.splice(index, 1, session);
      }
    }, "成员已加入");
  }

  async function saveMember(memberId: string, request: UpdateMember): Promise<void> {
    if (!currentRoomId.value) return;
    const roomId = currentRoomId.value;
    await saveSetup(async () => {
      const member = await updateRoomMember(roomId, memberId, request);
      if (roomData.value?.room.id === roomId) {
        const index = roomData.value.members.findIndex((candidate) => candidate.id === memberId);
        roomData.value.members.splice(index, 1, member);
      }
    }, "成员已保存");
  }

  async function saveNewTopic(request: CreateTopic): Promise<void> {
    if (!currentRoomId.value) return;
    const roomId = currentRoomId.value;
    await saveSetup(async () => {
      await roomsStore.createTopic(roomId, request);
    }, "话题已创建");
  }

  async function saveTopic(topicId: string, request: CreateTopic): Promise<void> {
    if (!currentRoomId.value) return;
    const roomId = currentRoomId.value;
    await saveSetup(async () => {
      const topic = await updateRoomTopic(roomId, topicId, request);
      const topics = roomsStore.catalogs[roomId]?.topics;
      if (topics) {
        const index = topics.findIndex((item) => item.id === topicId);
        if (index !== -1) topics.splice(index, 1, topic);
      }
    }, "话题已保存");
  }

  async function deleteNode(): Promise<void> {
    if (saving.value || !currentRoomId.value || !deleteTarget.value) return;
    const roomId = currentRoomId.value;
    const target = deleteTarget.value;
    saving.value = true;
    setupError.value = null;
    try {
      if (target.kind === "topic") {
        const topic = await deleteRoomTopic(roomId, target.node.id);
        const topics = roomsStore.catalogs[roomId]?.topics;
        const index = topics?.findIndex((item) => item.id === topic.id) ?? -1;
        if (topics && index !== -1) topics.splice(index, 1, topic);
        if (roomData.value?.room.id === roomId) {
          for (const member of roomData.value.members)
            member.topicIds = member.topicIds.filter((id) => id !== topic.id);
          if (selectedTopicId.value === topic.id) {
            selectedTopicId.value = undefined;
            await loadRoom();
          }
        }
      } else {
        const member = await deleteRoomMember(roomId, target.node.id);
        if (roomData.value?.room.id === roomId) {
          const index = roomData.value.members.findIndex((item) => item.id === member.id);
          if (index !== -1) roomData.value.members.splice(index, 1, member);
          if (selectedMemberId.value === member.id) selectedMemberId.value = undefined;
        }
      }
      toasts.success(target.kind === "topic" ? "话题已删除" : "成员已删除");
      if (currentRoomId.value === roomId) deleteTarget.value = undefined;
    } catch (caught) {
      const message = describeApiError(caught, "删除失败，请稍后重试。");
      if (currentRoomId.value === roomId) setupError.value = message;
      toasts.error(message);
    } finally {
      saving.value = false;
    }
  }

  async function showReference(messageId: string): Promise<void> {
    if (!visibleMessages.value.some((message) => message.id === messageId)) {
      selectedTopicId.value = undefined;
      selectedMemberId.value = undefined;
      if (!(await loadRoom())) return;
    }
    selectedMessageId.value = messageId;
    await nextTick();
    timeline.value?.scrollToMessage(messageId);
  }

  watch(
    () => props.roomId,
    (roomId) => {
      if (roomId) void openRoom(roomId);
    },
  );

  onMounted(initialize);
</script>
