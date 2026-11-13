<template>
  <div v-if="!snapshot" class="room-initial-state">
    <template v-if="loading">
      <AppIcon name="relay" />
      <h1>{{ t("room.connecting") }}</h1>
      <AppLoading>{{ t("room.loading") }}</AppLoading>
    </template>
    <template v-else-if="loadError">
      <AppIcon name="chat" />
      <h1>{{ t("room.unavailable") }}</h1>
      <p role="alert">{{ translateMessage(loadError) }}</p>
      <AppButton @click="retry">{{ t("room.reload") }}</AppButton>
    </template>
    <template v-else>
      <AppIcon name="chat" />
      <h1>{{ t("room.empty") }}</h1>
      <AppButton @click="roomsStore.createOpen = true">{{ t("room.create") }}</AppButton>
    </template>
  </div>
  <RoomWorkbench v-else :details-open="drawerOpen" @collapse-details="drawerOpen = false">
    <template #sidebar>
      <aside class="room-sidebar" :aria-label="t('room.navigation')">
        <TopicSidebar
          :snapshot="snapshot"
          :busy="sending || saving"
          :selected-topic-id="selectedTopicId"
          @select="selectSidebar('topic', $event)"
          @create-topic="openSetup('topic')"
        />
        <MemberPanel
          :snapshot="snapshot"
          :busy="sending || saving"
          :selected-member-id="selectedMemberId"
          @select="selectSidebar('member', $event)"
          @add-member="openSetup('member')"
        />
      </aside>
    </template>

    <section class="conversation-panel" :aria-label="t('room.title')">
      <div class="conversation-messages">
        <header class="room-panel-heading conversation-heading">
          <div class="conversation-title">
            <h2 class="room-panel-title">{{ t("room.title") }}</h2>
            <AppButton
              variant="plain"
              class="details-toggle"
              :aria-expanded="drawerOpen"
              @click="roomPanel.openDrawer"
            >
              {{ t("room.details") }}
            </AppButton>
          </div>
          <div class="conversation-actions">
            <form
              class="conversation-search"
              role="search"
              :aria-label="t('room.searchRoom')"
              @submit.prevent="submitSearch"
            >
              <div class="conversation-search-field">
                <AppIcon name="search" />
                <AppInput
                  v-model="searchText"
                  type="search"
                  name="keyword"
                  maxlength="200"
                  :placeholder="t('room.searchPlaceholder')"
                  :aria-label="t('room.search')"
                  :clear-label="t('room.clearSearch')"
                  autocomplete="off"
                />
              </div>
              <AppButton
                type="submit"
                variant="primary"
                class="conversation-search-button"
                :title="searchText.trim() ? t('room.search') : t('room.refresh')"
                :loading="loading || refreshingSessions"
                :loading-label="t('room.loadingShort')"
                :disabled="sending || clearing"
              >
                {{ t("room.search") }}
              </AppButton>
            </form>
            <AppButton
              variant="warning"
              class="conversation-clear-button"
              :loading="clearing"
              :loading-label="t('room.clearing')"
              :disabled="
                loading || refreshingSessions || sending || saving || Boolean(pendingPublication)
              "
              @click="openClear"
            >
              {{ t("room.clear") }}
            </AppButton>
          </div>
        </header>
        <div v-if="loadError" class="room-alert" role="alert">
          <span>{{ translateMessage(loadError) }}</span>
          <button type="button" @click="loadRoom()">{{ t("common.retry") }}</button>
        </div>
        <MessageTimeline
          ref="timeline"
          :messages="visibleMessages"
          :has-more="snapshot.hasMore"
          :has-newer="snapshot.hasNewer"
          :loading-older="loadingOlder"
          :unavailable="loadError !== null"
          :members="snapshot.members"
          :sessions="snapshot.sessions"
          :topics="snapshot.topics"
          :selected-message-id="detailMessage?.id"
          details-open
          :loading="loading"
          :searching="Boolean(keyword)"
          @load-older="loadOlder"
          @latest="loadLatest"
          @reply="quoteMessage"
          @reference="showReference"
          @select="selectMessage"
          @add-topic="composer?.addTopic($event)"
          @add-member="composer?.addMember($event)"
        />
      </div>
      <RoomComposer
        :key="snapshot.room.id"
        ref="composer"
        v-model:draft="drafts[snapshot.room.id]"
        :room-id="snapshot.room.id"
        :topics="activeTopics"
        :members="snapshot.members"
        :sessions="snapshot.sessions"
        :reply-to="replyTo"
        :sending="sending || clearing"
        :locked="Boolean(pendingPublication)"
        :error="sendError"
        :catalog="capabilities.catalog.value"
        @refresh-capabilities="capabilities.refresh"
        @send="sendMessage"
        @cancel-reply="replyTo = undefined"
      />
      <div v-if="pendingPublication && !sending" class="room-alert" role="status">
        <span>{{ t("room.pending") }}</span>
        <AppButton @click="resumePublication">{{ t("room.checkPublication") }}</AppButton>
      </div>
    </section>

    <template #details="{ collapse }">
      <MessageDetails
        :message="detailMessage"
        :topic="detailTopic"
        :member="detailMember"
        :topics="snapshot.topics"
        :members="snapshot.members"
        :sessions="snapshot.sessions"
        :busy="sending || saving"
        @close="roomPanel.closeDetails"
        @collapse="collapse"
        @edit-topic="editTopic"
        @delete-topic="openDelete({ kind: 'topic', node: $event })"
        @edit-member="editMember"
        @delete-member="openDelete({ kind: 'member', node: $event })"
      >
        <template #queue>
          <MessageQueue
            :messages="queueMessages"
            :has-more="queueHasMore"
            :loading="queueLoading"
            :loading-more="queueLoadingMore"
            :removing-id="queueRemovingId"
            :error="queueError"
            :remove-error="queueRemoveError"
            @select="selectQueueMessage"
            @refresh="messageQueue.refresh"
            @remove="messageQueue.remove"
            @load-more="messageQueue.loadMore"
          />
        </template>
      </MessageDetails>
    </template>
  </RoomWorkbench>
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
  <RoomClearDialog
    :room="clearOpen ? snapshot?.room : undefined"
    :saving="clearing"
    :error="clearError"
    @close="clearOpen = false"
    @confirm="clearCurrentRoom"
  />
</template>

<script setup lang="ts">
  import {
    computed,
    nextTick,
    onActivated,
    onBeforeUnmount,
    onDeactivated,
    onMounted,
    ref,
    watch,
  } from "vue";
  import { useRouter } from "vue-router";
  import { useI18n } from "vue-i18n";
  import { translateMessage } from "@/i18n";
  import type { MessageDescriptor } from "@/i18n";

  import AppButton from "@/components/AppButton.vue";
  import AppIcon from "@/components/AppIcon.vue";
  import AppInput from "@/components/AppInput.vue";
  import AppLoading from "@/components/AppLoading.vue";
  import MemberEditDialog from "@/domains/room/MemberEditDialog.vue";
  import MemberPanel from "@/domains/room/MemberPanel.vue";
  import MessageDetails from "@/domains/room/MessageDetails.vue";
  import MessageQueue from "@/domains/room/MessageQueue.vue";
  import MessageTimeline from "@/domains/room/MessageTimeline.vue";
  import RoomComposer from "@/domains/room/RoomComposer.vue";
  import RoomClearDialog from "@/domains/room/RoomClearDialog.vue";
  import RoomDeleteDialog from "@/domains/room/RoomDeleteDialog.vue";
  import type { DeleteTarget } from "@/domains/room/RoomDeleteDialog.vue";
  import RoomSetupDialog from "@/domains/room/RoomSetupDialog.vue";
  import RoomWorkbench from "@/domains/room/RoomWorkbench.vue";
  import TopicSidebar from "@/domains/room/TopicSidebar.vue";
  import { useMessageQueue } from "@/domains/room/useMessageQueue";
  import { useRoomPanel } from "@/domains/room/useRoomPanel";
  import { useRoomCapabilities } from "@/domains/room/useRoomCapabilities";
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

  type ResourceDeleteTarget = Exclude<DeleteTarget, { kind: "room" }>;

  const props = defineProps<{ roomId?: string }>();
  const { t } = useI18n();
  const router = useRouter();
  const roomsStore = useRoomsStore();
  const active = ref(true);
  let activatedBefore = false;
  const toasts = useToastsStore();
  const currentRoomId = ref<string>();
  const snapshot = computed(() =>
    currentRoomId.value ? roomsStore.snapshots[currentRoomId.value] : undefined,
  );
  const searchText = ref("");
  const keyword = ref("");
  const activeTopics = computed(
    () => snapshot.value?.topics.filter((topic) => !topic.deletedAt) ?? [],
  );
  const activeMembers = computed(
    () => snapshot.value?.members.filter((member) => !member.deletedAt) ?? [],
  );
  const visibleMessages = computed(() => snapshot.value?.messages ?? []);
  const roomPanel = useRoomPanel(() => visibleMessages.value);
  const {
    selectedTopicId,
    selectedMemberId,
    target: detailTarget,
    message: detailMessage,
    drawerOpen,
    queueScope,
  } = roomPanel;
  const messageQueue = useMessageQueue(
    () => (active.value ? currentRoomId.value : undefined),
    () => queueScope.value,
  );
  const {
    messages: queueMessages,
    hasMore: queueHasMore,
    loading: queueLoading,
    loadingMore: queueLoadingMore,
    removingId: queueRemovingId,
    error: queueError,
    removeError: queueRemoveError,
  } = messageQueue;
  const detailTopic = computed(() => {
    const target = detailTarget.value;
    return target?.kind === "topic"
      ? activeTopics.value.find((topic) => topic.id === target.id)
      : undefined;
  });
  const detailMember = computed(() => {
    const target = detailTarget.value;
    return target?.kind === "member"
      ? activeMembers.value.find((member) => member.id === target.id)
      : undefined;
  });
  const loading = ref(true);
  const refreshingSessions = ref(false);
  const loadingOlder = ref(false);
  const sending = ref(false);
  const loadError = ref<MessageDescriptor | null>(null);
  const sendError = ref<MessageDescriptor | null>(null);
  const replyTo = ref<RoomMessage>();
  const composer = ref<InstanceType<typeof RoomComposer>>();
  const timeline = ref<InstanceType<typeof MessageTimeline>>();
  const drafts = ref<Record<string, MessageDraft>>({});
  const capabilities = useRoomCapabilities(() =>
    roomsStore.rooms.find((room) => room.id === currentRoomId.value),
  );
  const pendingPublication = ref<CreateMessage>();
  const setupMode = ref<"member" | "topic">();
  const editingMember = ref<Member>();
  const editingTopic = ref<Topic>();
  const deleteTarget = ref<ResourceDeleteTarget>();
  const saving = ref(false);
  const clearOpen = ref(false);
  const clearing = ref(false);
  const clearError = ref<MessageDescriptor | null>(null);
  const setupError = ref<MessageDescriptor | null>(null);
  const sessions = ref<SessionCandidate[]>([]);
  const sessionsLoading = ref(false);
  const sessionsError = ref<MessageDescriptor | null>(null);
  let sessionsVersion = 0;
  let loadVersion = 0;
  let initializationVersion = 0;

  let stopEvents: (() => void) | undefined;
  let queryController: AbortController | undefined;
  let sessionsController: AbortController | undefined;
  let refreshController: AbortController | undefined;
  let searchTimer: ReturnType<typeof setTimeout> | undefined;

  function filters(): MessageQuery {
    return {
      topicId: selectedTopicId.value,
      memberId: selectedMemberId.value,
      keyword: keyword.value || undefined,
    };
  }

  function resetSearch(): void {
    clearTimeout(searchTimer);
    searchText.value = "";
    keyword.value = "";
  }

  async function applySearch(): Promise<void> {
    clearTimeout(searchTimer);
    if (!active.value) return;
    const nextKeyword = searchText.value.trim();
    if (nextKeyword === keyword.value) return;
    keyword.value = nextKeyword;
    await loadLatest();
  }

  async function submitSearch(): Promise<void> {
    clearTimeout(searchTimer);
    if (loading.value || refreshingSessions.value || sending.value || clearing.value) return;
    keyword.value = searchText.value.trim();
    if (keyword.value) await loadLatest();
    else await refreshRoom();
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
        roomPanel.closeDetails();
        replyTo.value = undefined;
        messageQueue.reset();
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
      roomPanel.syncMessages(messages);
      current.eventId = page.nextEventId;
      const newest = current.messages.at(-1);
      if (wasAtEnd && newest && newest.seq > previousSeq) {
        await nextTick();
        if (version === loadVersion) timeline.value?.scrollToEnd();
      }
    });
  }

  function clearDeletedFilters(): boolean {
    let changed = false;
    const target = detailTarget.value;
    if (target?.kind === "topic" && !activeTopics.value.some((topic) => topic.id === target.id)) {
      roomPanel.closeDetails();
    } else if (
      target?.kind === "member" &&
      !activeMembers.value.some((member) => member.id === target.id)
    ) {
      roomPanel.closeDetails();
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
    if (!roomId || !active.value) return false;
    const version = cancelQueries();
    loading.value = true;
    loadError.value = null;
    try {
      const result = await fetchRoom(roomId, { ...filters(), beforeSeq }, queryController?.signal);
      if (version !== loadVersion) return false;
      roomsStore.sync(result);
      roomPanel.syncMessages(result.messages);
      if (clearDeletedFilters()) return await loadRoom();
      await refreshDetailMessage(roomId, version);
      if (version !== loadVersion) return false;
      startEvents(roomId, version);
      return true;
    } catch (caught) {
      if (version === loadVersion) {
        loadError.value = describeApiError(caught, "errors.messageLoad");
        toasts.error(loadError.value);
      }
      return false;
    } finally {
      if (version === loadVersion) loading.value = false;
    }
  }

  async function refreshDetailMessage(roomId: string, version: number): Promise<void> {
    const target = detailTarget.value;
    if (target?.kind !== "message") return;
    const selected = target.message;
    try {
      const message = await fetchRoomMessage(roomId, selected.id, queryController?.signal);
      if (version === loadVersion) roomPanel.syncMessages([message]);
    } catch (caught) {
      if (version === loadVersion) toasts.error(describeApiError(caught, "errors.detailLoad"));
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
      if (version === loadVersion) toasts.error(describeApiError(caught, "errors.historyLoad"));
    } finally {
      if (version === loadVersion) {
        loadingOlder.value = false;
        startEvents(roomId, version);
      }
    }
  }

  async function initialize(): Promise<void> {
    const version = ++initializationVersion;
    loading.value = true;
    loadError.value = null;
    try {
      await roomsStore.load();
      if (!active.value || version !== initializationVersion) return;
      if (props.roomId) await openRoom(props.roomId);
      else if (roomsStore.rooms.length)
        await router.replace({ name: "room-detail", params: { roomId: roomsStore.rooms[0].id } });
      else loading.value = false;
    } catch (caught) {
      if (!active.value || version !== initializationVersion) return;
      loadError.value = describeApiError(caught, "errors.roomLoad");
      toasts.error(loadError.value);
      loading.value = false;
    }
  }

  async function openRoom(roomId: string): Promise<void> {
    resetSearch();
    currentRoomId.value = roomId;
    roomsStore.recentRoomId = roomId;
    cancelQueries();
    delete roomsStore.snapshots[roomId];
    setupMode.value = undefined;
    editingMember.value = undefined;
    editingTopic.value = undefined;
    deleteTarget.value = undefined;
    clearOpen.value = false;
    clearError.value = null;
    sessionsVersion++;
    sessionsController?.abort();
    sessions.value = [];
    sessionsLoading.value = false;
    sessionsError.value = null;
    roomPanel.reset();
    messageQueue.reset();
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

  async function selectSidebar(
    kind: "topic" | "member",
    resourceId: string | undefined,
  ): Promise<void> {
    if (!roomPanel.selectSidebar(kind, resourceId)) return;
    if (kind === "topic") composer.value?.selectTopic(resourceId);
    else composer.value?.selectMember(resourceId);
    await loadLatest();
  }

  function selectMessage(messageId: string): void {
    const message =
      visibleMessages.value.find((message) => message.id === messageId) ??
      queueMessages.value.find((message) => message.id === messageId);
    if (message) roomPanel.showMessage(message);
  }

  function selectQueueMessage(messageId: string): void {
    selectMessage(messageId);
    timeline.value?.scrollToMessage(messageId);
  }

  function quoteMessage(message: RoomMessage): void {
    if (sending.value || pendingPublication.value) return;
    replyTo.value = message;
    void composer.value?.quote(message);
  }

  async function sendMessage(draft: MessageDraft): Promise<void> {
    if (sending.value || clearing.value || !currentRoomId.value) return;
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
      const message = describeApiError(caught, "errors.publish");
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
    roomPanel.showMessage(sentMessage);
    pendingPublication.value = undefined;
    composer.value?.reset();
    replyTo.value = undefined;
    toasts.success({ key: "notice.published" });
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
    if (!currentRoomId.value || !active.value) return;
    const roomId = currentRoomId.value;
    const version = ++sessionsVersion;
    sessionsController?.abort();
    sessionsController = new AbortController();
    sessionsLoading.value = true;
    sessionsError.value = null;
    try {
      const result = await fetchRoomSessions(roomId, sessionsController.signal);
      if (version === sessionsVersion) sessions.value = result;
    } catch (caught) {
      if (version === sessionsVersion) {
        sessions.value = [];
        sessionsError.value = describeApiError(caught, "errors.sessionLoad");
      }
    } finally {
      if (version === sessionsVersion) sessionsLoading.value = false;
    }
  }

  async function refreshRoom(): Promise<void> {
    if (!currentRoomId.value || refreshingSessions.value || sending.value || clearing.value) return;
    const roomId = currentRoomId.value;
    const version = initializationVersion;
    refreshController = new AbortController();
    refreshingSessions.value = true;
    try {
      await fetchRoomSessions(roomId, refreshController.signal);
    } catch (caught) {
      if (active.value && version === initializationVersion)
        toasts.error(describeApiError(caught, "errors.sessionRefresh"));
    } finally {
      if (version === initializationVersion) refreshingSessions.value = false;
    }
    if (
      !active.value ||
      version !== initializationVersion ||
      roomId !== currentRoomId.value ||
      !(await loadRoom())
    )
      return;
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

  function openClear(): void {
    clearError.value = null;
    clearOpen.value = true;
  }

  async function clearCurrentRoom(): Promise<void> {
    const roomId = currentRoomId.value;
    if (!roomId || !clearOpen.value || saving.value || sending.value || pendingPublication.value)
      return;
    clearing.value = true;
    saving.value = true;
    clearError.value = null;
    const version = cancelQueries();
    messageQueue.cancel();
    try {
      const result = await roomsStore.clear(roomId);
      toasts.success({
        key: "notice.cleared",
        params: { messages: result.removedMessages, members: result.removedMembers },
      });
      if (currentRoomId.value !== roomId) return;
      clearOpen.value = false;
      roomPanel.reset();
      messageQueue.reset();
      replyTo.value = undefined;
      resetSearch();
      await loadLatest();
    } catch (caught) {
      const message = describeApiError(caught, "errors.clear");
      if (currentRoomId.value === roomId) {
        clearError.value = message;
        startEvents(roomId, version);
        void messageQueue.refresh();
      }
      toasts.error(message);
    } finally {
      clearing.value = false;
      saving.value = false;
    }
  }

  async function saveSetup(action: () => Promise<void>, successMessage: string): Promise<void> {
    if (saving.value) return;
    saving.value = true;
    setupError.value = null;
    const roomId = currentRoomId.value;
    try {
      await action();
      toasts.success({ key: successMessage });
      if (roomId === currentRoomId.value) {
        setupMode.value = undefined;
        editingMember.value = undefined;
      }
    } catch (caught) {
      const message = describeApiError(caught, "errors.save");
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
    }, "notice.memberAdded");
  }

  async function saveMember(memberId: string, request: UpdateMember): Promise<void> {
    if (!currentRoomId.value) return;
    const roomId = currentRoomId.value;
    await saveSetup(async () => {
      const result = await updateRoomMember(roomId, memberId, request);
      applyResourceChange(result.metadata);
    }, "notice.memberSaved");
  }

  async function saveNewTopic(request: CreateTopic): Promise<void> {
    if (!currentRoomId.value) return;
    const roomId = currentRoomId.value;
    await saveSetup(async () => {
      const result = await addRoomTopic(roomId, request);
      applyResourceChange(result.metadata);
    }, "notice.topicCreated");
  }

  async function saveTopic(topicId: string, request: CreateTopic): Promise<void> {
    if (!currentRoomId.value) return;
    const roomId = currentRoomId.value;
    await saveSetup(async () => {
      const result = await updateRoomTopic(roomId, topicId, request);
      applyResourceChange(result.metadata);
    }, "notice.topicSaved");
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
      toasts.success({
        key: target.kind === "topic" ? "notice.topicDeleted" : "notice.memberDeleted",
      });
      if (currentRoomId.value === roomId) deleteTarget.value = undefined;
    } catch (caught) {
      const message = describeApiError(caught, "errors.remove");
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
        resetSearch();
        if (!(await loadRoom(message.seq + 1))) return;
      } catch (caught) {
        if (version === loadVersion) toasts.error(describeApiError(caught, "errors.reference"));
        return;
      }
    }
    selectMessage(messageId);
    await nextTick();
    timeline.value?.scrollToMessage(messageId);
  }

  function pauseReads(): void {
    initializationVersion++;
    clearTimeout(searchTimer);
    cancelQueries();
    messageQueue.cancel();
    sessionsVersion++;
    sessionsController?.abort();
    refreshController?.abort();
    sessionsLoading.value = false;
    refreshingSessions.value = false;
    capabilities.pause();
  }

  onDeactivated(() => {
    active.value = false;
    pauseReads();
  });
  onActivated(() => {
    if (!activatedBefore) {
      activatedBefore = true;
      return;
    }
    active.value = true;
    capabilities.resume();
    if (currentRoomId.value) {
      keyword.value = searchText.value.trim();
      void loadRoom();
      void messageQueue.refresh();
      if (setupMode.value === "member") void loadSessions();
    } else void initialize();
  });
  onBeforeUnmount(pauseReads);

  watch(searchText, (value) => {
    clearTimeout(searchTimer);
    if (!value.trim()) void applySearch();
    else searchTimer = setTimeout(() => void applySearch(), 300);
  });

  watch(
    [
      currentRoomId,
      () => queueScope.value.topicId,
      () => queueScope.value.memberId,
      () => snapshot.value?.eventId,
    ],
    ([roomId, topicId, memberId], [previousRoomId, previousTopicId, previousMemberId]) => {
      if (roomId !== previousRoomId || topicId !== previousTopicId || memberId !== previousMemberId)
        messageQueue.reset();
      if (active.value && roomId && snapshot.value) void messageQueue.refresh();
    },
  );

  watch(
    () => props.roomId,
    (roomId) => {
      if (roomId) {
        void openRoom(roomId);
      } else {
        cancelQueries();
        messageQueue.reset();
        roomPanel.reset();
        sessionsVersion++;
        currentRoomId.value = undefined;
        pendingPublication.value = undefined;
        void initialize();
      }
    },
  );

  onMounted(initialize);
</script>
