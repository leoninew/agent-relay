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
        :selected-member-id="selectedMemberId"
        @select="selectMember"
        @add-member="openSetup('member')"
        @edit-member="editMember"
        @delete-member="openDelete({ kind: 'member', node: $event })"
      />
    </TopicSidebar>

    <section class="conversation-panel" aria-label="聊天室">
      <header class="room-panel-heading conversation-heading">
        <div class="conversation-title">
          <h2 class="room-panel-title">聊天室</h2>
          <AppButton
            variant="plain"
            class="conversation-refresh"
            :loading="loading || refreshingSessions"
            loading-label="刷新中…"
            :disabled="sending"
            @click="refreshRoom()"
          >
            刷新
          </AppButton>
        </div>
      </header>
      <div v-if="loadError" class="room-alert" role="alert">
        <span>{{ loadError }}</span>
        <button type="button" @click="loadRoom()">重试</button>
      </div>
      <MessageTimeline
        ref="timeline"
        :messages="visibleMessages"
        :has-more="snapshot.hasMore"
        :has-newer="snapshot.hasNewer"
        :loading-older="loadingOlder"
        :unavailable="loadError !== null"
        :members="snapshot.members"
        :topics="snapshot.topics"
        :selected-message-id="detailMessage?.id"
        :details-open="detailsOpen"
        :loading="loading"
        @load-older="loadOlder"
        @latest="loadLatest"
        @reply="quoteMessage"
        @reference="showReference"
        @select="selectMessage"
        @show-details="detailsOpen = true"
      />
      <RoomComposer
        :key="snapshot.room.id"
        ref="composer"
        v-model:draft="drafts[snapshot.room.id]"
        :room-id="snapshot.room.id"
        :topics="activeTopics"
        :members="snapshot.members"
        :reply-to="replyTo"
        :sending="sending"
        :locked="Boolean(pendingPublication)"
        :error="sendError"
        @send="sendMessage"
        @cancel-reply="replyTo = undefined"
      />
      <div v-if="pendingPublication && !sending" class="room-alert" role="status">
        <span>发布结果待确认，请核对后继续。</span>
        <AppButton @click="resumePublication">核对发布结果</AppButton>
      </div>
    </section>

    <MessageDetails
      v-if="detailsOpen"
      :message="detailMessage"
      :topic="detailTopic"
      :member="detailMember"
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
    :topic="editingTopic"
    @close="setupMode = undefined"
    @create-member="saveNewMember"
    @create-topic="saveNewTopic"
    @update-topic="saveTopic"
    @reload-sessions="loadSessions"
  />
  <MemberEditDialog
    :member="editingMember"
    :linked-session="snapshot?.sessions.find((session) => session.id === editingMember?.sessionId)"
    :topics="activeTopics"
    :room-id="currentRoomId"
    :saving="saving"
    :error="setupError"
    @close="editingMember = undefined"
    @save="saveMember"
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
  import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
  import { useRouter } from "vue-router";

  import AppButton from "@/components/AppButton.vue";
  import AppIcon from "@/components/AppIcon.vue";
  import AppLoading from "@/components/AppLoading.vue";
  import MemberEditDialog from "@/domains/room/MemberEditDialog.vue";
  import MemberPanel from "@/domains/room/MemberPanel.vue";
  import MessageDetails from "@/domains/room/MessageDetails.vue";
  import MessageTimeline from "@/domains/room/MessageTimeline.vue";
  import RoomComposer from "@/domains/room/RoomComposer.vue";
  import RoomDeleteDialog from "@/domains/room/RoomDeleteDialog.vue";
  import type { DeleteTarget } from "@/domains/room/RoomDeleteDialog.vue";
  import RoomSetupDialog from "@/domains/room/RoomSetupDialog.vue";
  import TopicSidebar from "@/domains/room/TopicSidebar.vue";
  import { ApiClientError, describeApiError } from "@/services/api";
  import {
    addRoomMember,
    addRoomTopic,
    deleteRoomMember,
    deleteRoomTopic,
    fetchRoom,
    fetchRoomMessages,
    fetchRoomMessage,
    fetchRoomMetadata,
    fetchRoomSessions,
    fetchPublication,
    postRoomMessage,
    updateRoomMember,
    updateRoomTopic,
  } from "@/services/roomApi";
  import type {
    CreateMember,
    CreateMessage,
    CreateTopic,
    Member,
    MessageDraft,
    RoomMessage,
    MessageQuery,
    RoomEventPage,
    RoomMetadata,
    SessionCandidate,
    Topic,
    UpdateMember,
  } from "@/services/roomApi";
  import { subscribeRoomEvents } from "@/services/roomEvents";
  import { useRoomsStore } from "@/stores/rooms";
  import { useToastsStore } from "@/stores/toasts";

  import "./room.css";

  type DetailTarget =
    { kind: "message" } | { kind: "topic"; id: string } | { kind: "member"; id: string };
  type ResourceDeleteTarget = Exclude<DeleteTarget, { kind: "room" }>;

  const props = defineProps<{ roomId?: string }>();
  const router = useRouter();
  const roomsStore = useRoomsStore();
  const toasts = useToastsStore();
  const currentRoomId = ref<string>();
  const snapshot = computed(() =>
    currentRoomId.value ? roomsStore.snapshots[currentRoomId.value] : undefined,
  );
  const selectedTopicId = ref<string>();
  const selectedMemberId = ref<string>();
  const activeTopics = computed(
    () => snapshot.value?.topics.filter((topic) => !topic.deletedAt) ?? [],
  );
  const activeMembers = computed(
    () => snapshot.value?.members.filter((member) => !member.deletedAt) ?? [],
  );
  const visibleMessages = computed(() => snapshot.value?.messages ?? []);
  const selectedMessageId = ref<string>();
  const selectedMessage = computed(() => {
    const messages = visibleMessages.value;
    return messages.find((message) => message.id === selectedMessageId.value) ?? messages.at(-1);
  });
  const detailTarget = ref<DetailTarget>({ kind: "message" });
  const detailMessage = computed(() =>
    detailTarget.value.kind === "message" ? selectedMessage.value : undefined,
  );
  const detailTopic = computed(() => {
    const target = detailTarget.value;
    return target.kind === "topic"
      ? activeTopics.value.find((topic) => topic.id === target.id)
      : undefined;
  });
  const detailMember = computed(() => {
    const target = detailTarget.value;
    return target.kind === "member"
      ? activeMembers.value.find((member) => member.id === target.id)
      : undefined;
  });
  const detailsOpen = ref(true);
  const loading = ref(true);
  const refreshingSessions = ref(false);
  const loadingOlder = ref(false);
  const sending = ref(false);
  const loadError = ref<string | null>(null);
  const sendError = ref<string | null>(null);
  const replyTo = ref<RoomMessage>();
  const composer = ref<InstanceType<typeof RoomComposer>>();
  const timeline = ref<InstanceType<typeof MessageTimeline>>();
  const drafts = ref<Record<string, MessageDraft>>({});
  const pendingPublication = ref<CreateMessage>();
  const setupMode = ref<"member" | "topic">();
  const editingMember = ref<Member>();
  const editingTopic = ref<Topic>();
  const deleteTarget = ref<ResourceDeleteTarget>();
  const saving = ref(false);
  const setupError = ref<string | null>(null);
  const sessions = ref<SessionCandidate[]>([]);
  const sessionsLoading = ref(false);
  const sessionsError = ref<string | null>(null);
  let sessionsVersion = 0;
  let loadVersion = 0;

  let stopEvents: (() => void) | undefined;
  let queryController: AbortController | undefined;

  function filters(): MessageQuery {
    return { topicId: selectedTopicId.value, memberId: selectedMemberId.value };
  }

  function cancelQueries(): number {
    stopEvents?.();
    stopEvents = undefined;
    queryController?.abort();
    queryController = new AbortController();
    loadingOlder.value = false;
    return ++loadVersion;
  }

  function startEvents(roomId: string, version: number): void {
    const current = roomsStore.snapshots[roomId];
    if (!current || version !== loadVersion) return;
    stopEvents = subscribeRoomEvents(roomId, current.eventId, async (page: RoomEventPage) => {
      if (version !== loadVersion) return;
      if (page.resyncRequired) {
        await loadRoom();
        return;
      }
      const events = page.events.filter((event) => event.eventId > current.eventId);
      if (!events.length) return;
      const signal = queryController?.signal;
      const ids = [
        ...new Set(
          events.map((event) => event.messageId).filter((id): id is string => Boolean(id)),
        ),
      ];
      const [metadata, messages] = await Promise.all([
        fetchRoomMetadata(roomId, signal),
        Promise.all(ids.map((id) => fetchRoomMessage(roomId, id, signal))),
      ]);
      if (version !== loadVersion) return;
      roomsStore.syncMetadata(metadata);
      if (clearDeletedFilters()) {
        await loadRoom();
        return;
      }
      const wasAtEnd = timeline.value?.isAtEnd();
      const previousSeq = current.messages.at(-1)?.seq ?? 0;
      roomsStore.applyMessages(roomId, messages, filters());
      current.eventId = page.nextEventId;
      const newest = current.messages.at(-1);
      if (wasAtEnd && newest && newest.seq > previousSeq) {
        selectMessage(newest.id);
        await nextTick();
        if (version === loadVersion) timeline.value?.scrollToEnd();
      }
    });
  }

  function clearDeletedFilters(): boolean {
    let changed = false;
    const target = detailTarget.value;
    if (target.kind === "topic" && !activeTopics.value.some((topic) => topic.id === target.id)) {
      detailTarget.value = { kind: "message" };
    } else if (
      target.kind === "member" &&
      !activeMembers.value.some((member) => member.id === target.id)
    ) {
      detailTarget.value = { kind: "message" };
    }
    if (
      selectedTopicId.value &&
      !activeTopics.value.some((topic) => topic.id === selectedTopicId.value)
    ) {
      selectedTopicId.value = undefined;
      changed = true;
    }
    if (
      selectedMemberId.value &&
      !activeMembers.value.some((member) => member.id === selectedMemberId.value)
    ) {
      selectedMemberId.value = undefined;
      changed = true;
    }
    return changed;
  }

  async function loadRoom(beforeSeq?: number): Promise<boolean> {
    const roomId = currentRoomId.value;
    if (!roomId) return false;
    const version = cancelQueries();
    loading.value = true;
    loadError.value = null;
    try {
      const result = await fetchRoom(roomId, { ...filters(), beforeSeq }, queryController?.signal);
      if (version !== loadVersion) return false;
      roomsStore.sync(result);
      selectedMessageId.value = selectedMessage.value?.id;
      if (clearDeletedFilters()) return await loadRoom();
      startEvents(roomId, version);
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

  async function loadLatest(): Promise<void> {
    if (!(await loadRoom())) return;
    await nextTick();
    timeline.value?.scrollToEnd();
  }

  async function loadOlder(): Promise<void> {
    const roomId = currentRoomId.value;
    const beforeSeq = snapshot.value?.nextBeforeSeq;
    if (!roomId || !beforeSeq || loadingOlder.value || loading.value) return;
    const version = cancelQueries();
    loadingOlder.value = true;
    try {
      const page = await fetchRoomMessages(
        roomId,
        { ...filters(), beforeSeq },
        queryController?.signal,
      );
      if (version !== loadVersion) return;
      timeline.value?.rememberScroll();
      roomsStore.prependPage(roomId, page);
      await nextTick();
      timeline.value?.restoreScroll();
    } catch (caught) {
      if (version === loadVersion)
        toasts.error(describeApiError(caught, "历史消息加载失败，请重试。"));
    } finally {
      if (version === loadVersion) {
        loadingOlder.value = false;
        startEvents(roomId, version);
      }
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
    cancelQueries();
    delete roomsStore.snapshots[roomId];
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
    detailTarget.value = { kind: "message" };
    detailsOpen.value = true;
    replyTo.value = undefined;
    sendError.value = null;
    const saved = sessionStorage.getItem(`relay-publication:${roomId}`);
    pendingPublication.value = saved ? (JSON.parse(saved) as CreateMessage) : undefined;
    if (pendingPublication.value) drafts.value[roomId] = pendingPublication.value;
    await loadRoom();
    await nextTick();
    timeline.value?.scrollToEnd();
  }

  async function retry(): Promise<void> {
    if (currentRoomId.value) await loadRoom();
    else await initialize();
  }

  function syncDraftRouting(): void {
    const roomId = currentRoomId.value;
    if (!roomId || pendingPublication.value) return;
    const draft = drafts.value[roomId] ?? { content: "", topicIds: [], mentionedMemberIds: [] };
    const member = activeMembers.value.find((member) => member.id === selectedMemberId.value);
    drafts.value[roomId] = {
      ...draft,
      topicIds: selectedTopicId.value ? [selectedTopicId.value] : [],
      mentionedMemberIds: member?.kind === "agent" ? [member.id] : [],
    };
  }

  async function selectTopic(topicId?: string): Promise<void> {
    selectedTopicId.value = topicId;
    if (!topicId) selectedMemberId.value = undefined;
    detailTarget.value = topicId ? { kind: "topic", id: topicId } : { kind: "message" };
    detailsOpen.value = true;
    syncDraftRouting();
    await loadRoom();
    await nextTick();
    timeline.value?.scrollToEnd();
  }

  async function selectMember(memberId: string): Promise<void> {
    selectedMemberId.value = selectedMemberId.value === memberId ? undefined : memberId;
    detailTarget.value = { kind: "member", id: memberId };
    detailsOpen.value = true;
    syncDraftRouting();
    await loadRoom();
    await nextTick();
    timeline.value?.scrollToEnd();
  }

  function selectMessage(messageId: string): void {
    selectedMessageId.value = messageId;
    detailTarget.value = { kind: "message" };
    detailsOpen.value = true;
  }

  function quoteMessage(message: RoomMessage): void {
    if (sending.value || pendingPublication.value) return;
    replyTo.value = message;
    void composer.value?.quote(message);
  }

  async function sendMessage(draft: MessageDraft): Promise<void> {
    if (sending.value || !currentRoomId.value) return;
    if (pendingPublication.value) return;
    const request = { ...draft, publicationId: crypto.randomUUID() };
    sessionStorage.setItem(`relay-publication:${currentRoomId.value}`, JSON.stringify(request));
    pendingPublication.value = request;
    await publish(request);
  }

  async function resumePublication(): Promise<void> {
    if (pendingPublication.value && !sending.value) await publish(pendingPublication.value, true);
  }

  async function publish(request: CreateMessage, lookup = false): Promise<void> {
    if (!currentRoomId.value) return;
    const roomId = currentRoomId.value;
    sending.value = true;
    sendError.value = null;
    let sentMessage: RoomMessage;
    try {
      if (lookup) {
        try {
          sentMessage = await fetchPublication(roomId, request.publicationId);
        } catch (caught) {
          if (!(caught instanceof ApiClientError) || caught.status !== 404) throw caught;
          sentMessage = await postRoomMessage(roomId, request);
        }
      } else sentMessage = await postRoomMessage(roomId, request);
    } catch (caught) {
      if (
        caught instanceof ApiClientError &&
        caught.kind === "http_error" &&
        [404, 409, 422].includes(caught.status ?? 0)
      ) {
        sessionStorage.removeItem(`relay-publication:${roomId}`);
        if (roomId === currentRoomId.value) pendingPublication.value = undefined;
      }
      const message = describeApiError(caught, "发布结果待确认，草稿已保留，请核对发布结果。");
      if (roomId === currentRoomId.value) sendError.value = message;
      toasts.error(message);
      sending.value = false;
      return;
    }
    sessionStorage.removeItem(`relay-publication:${roomId}`);
    delete drafts.value[roomId];
    if (roomId !== currentRoomId.value) {
      sending.value = false;
      return;
    }
    selectedMessageId.value = sentMessage.id;
    detailTarget.value = { kind: "message" };
    detailsOpen.value = true;
    pendingPublication.value = undefined;
    composer.value?.reset();
    replyTo.value = undefined;
    toasts.success("消息已发布");
    selectedMemberId.value = undefined;
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

  async function refreshRoom(): Promise<void> {
    if (!currentRoomId.value || refreshingSessions.value || sending.value) return;
    const roomId = currentRoomId.value;
    refreshingSessions.value = true;
    try {
      await fetchRoomSessions(roomId);
    } catch (caught) {
      toasts.error(describeApiError(caught, "会话状态刷新失败"));
    } finally {
      refreshingSessions.value = false;
    }
    if (roomId !== currentRoomId.value || !(await loadRoom())) return;
    const newest = visibleMessages.value.at(-1);
    if (newest) selectMessage(newest.id);
    await nextTick();
    if (roomId === currentRoomId.value) timeline.value?.scrollToEnd();
  }

  function editMember(member: Member): void {
    setupError.value = null;
    editingTopic.value = undefined;
    deleteTarget.value = undefined;
    editingMember.value = member;
    setupMode.value = undefined;
  }

  function editTopic(topic: Topic): void {
    setupError.value = null;
    editingMember.value = undefined;
    editingTopic.value = topic;
    deleteTarget.value = undefined;
    setupMode.value = "topic";
  }

  function openDelete(target: ResourceDeleteTarget): void {
    setupMode.value = undefined;
    editingMember.value = undefined;
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
      if (roomId === currentRoomId.value) {
        setupMode.value = undefined;
        editingMember.value = undefined;
      }
    } catch (caught) {
      const message = describeApiError(caught, "保存失败，请稍后重试。");
      if (roomId === currentRoomId.value) setupError.value = message;
      toasts.error(message);
    } finally {
      saving.value = false;
    }
  }

  function applyResourceChange(metadata: RoomMetadata): void {
    roomsStore.syncMetadata(metadata);
    if (metadata.room.id === currentRoomId.value && clearDeletedFilters()) void loadRoom();
  }

  async function saveNewMember(request: CreateMember): Promise<void> {
    if (!currentRoomId.value) return;
    const roomId = currentRoomId.value;
    await saveSetup(async () => {
      const result = await addRoomMember(roomId, request);
      applyResourceChange(result.metadata);
    }, "成员已加入");
  }

  async function saveMember(memberId: string, request: UpdateMember): Promise<void> {
    if (!currentRoomId.value) return;
    const roomId = currentRoomId.value;
    await saveSetup(async () => {
      const result = await updateRoomMember(roomId, memberId, request);
      applyResourceChange(result.metadata);
    }, "成员已保存");
  }

  async function saveNewTopic(request: CreateTopic): Promise<void> {
    if (!currentRoomId.value) return;
    const roomId = currentRoomId.value;
    await saveSetup(async () => {
      const result = await addRoomTopic(roomId, request);
      applyResourceChange(result.metadata);
    }, "话题已创建");
  }

  async function saveTopic(topicId: string, request: CreateTopic): Promise<void> {
    if (!currentRoomId.value) return;
    const roomId = currentRoomId.value;
    await saveSetup(async () => {
      const result = await updateRoomTopic(roomId, topicId, request);
      applyResourceChange(result.metadata);
    }, "话题已保存");
  }

  async function deleteNode(): Promise<void> {
    if (saving.value || !currentRoomId.value || !deleteTarget.value) return;
    const roomId = currentRoomId.value;
    const target = deleteTarget.value;
    saving.value = true;
    setupError.value = null;
    try {
      const result =
        target.kind === "topic"
          ? await deleteRoomTopic(roomId, target.node.id)
          : await deleteRoomMember(roomId, target.node.id);
      applyResourceChange(result.metadata);
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
    const roomId = currentRoomId.value;
    if (!roomId) return;
    if (!visibleMessages.value.some((message) => message.id === messageId)) {
      const version = loadVersion;
      try {
        const message = await fetchRoomMessage(roomId, messageId, queryController?.signal);
        if (version !== loadVersion) return;
        selectedTopicId.value = undefined;
        selectedMemberId.value = undefined;
        if (!(await loadRoom(message.seq + 1))) return;
      } catch (caught) {
        if (version === loadVersion)
          toasts.error(describeApiError(caught, "引用消息加载失败，请重试。"));
        return;
      }
    }
    selectedMessageId.value = messageId;
    detailTarget.value = { kind: "message" };
    detailsOpen.value = true;
    await nextTick();
    timeline.value?.scrollToMessage(messageId);
  }

  onBeforeUnmount(() => {
    cancelQueries();
    sessionsVersion++;
  });

  watch(
    () => props.roomId,
    (roomId) => {
      if (roomId) {
        void openRoom(roomId);
      } else {
        cancelQueries();
        sessionsVersion++;
        currentRoomId.value = undefined;
        pendingPublication.value = undefined;
        void initialize();
      }
    },
  );

  onMounted(initialize);
</script>
