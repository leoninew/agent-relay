<template>
  <RoomLoadingSkeleton v-if="!snapshot && loading" :visible="skeletonVisible" />
  <div v-else-if="!snapshot" class="room-initial-state">
    <template v-if="loadError">
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
    <template #sidebar="{ closeNavigation }">
      <aside class="room-sidebar" :aria-label="t('room.navigation')">
        <ChannelBar
          v-model:channels="sortableChannels"
          :default-channel="defaultChannel"
          :channel-id="currentChannelId"
          :disabled="saving || sending || clearing || archiving || !currentRoomId"
          @move="moveChannel"
          @archive="openArchive"
          @create="
            closeNavigation();
            openChannelCreate();
          "
          @select="
            selectChannel($event);
            closeNavigation();
          "
        />
        <TopicSidebar
          v-model:topics="activeTopics"
          :busy="sending || saving"
          :selected-topic-id="selectedTopicId"
          @move="moveTopic"
          @select="
            selectSidebar('topic', $event);
            closeNavigation();
          "
          @create-topic="
            closeNavigation();
            openSetup('topic');
          "
        />
        <MemberPanel
          v-model:members="activeAgents"
          :snapshot="snapshot"
          :busy="sending || saving || clearing || Boolean(pendingPublication)"
          :selected-member-id="selectedMemberId"
          :interrupting-member-ids="interruptingMemberIds"
          @move="moveMember"
          @interrupt="interruptMember"
          @delete-member="openDelete({ kind: 'member', node: $event })"
          @select="
            selectSidebar('member', $event);
            closeNavigation();
          "
          @add-member="
            closeNavigation();
            openSetup('member');
          "
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
              :aria-label="t('sidebar.openRight')"
              :title="t('sidebar.openDetails')"
              :aria-expanded="drawerOpen"
              @click="roomPanel.openDrawer"
            >
              <AppIcon name="panel-right-open" />
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
          :messages="messagesCurrent ? visibleMessages : []"
          :has-more="snapshot.hasMore"
          :has-newer="snapshot.hasNewer"
          :loading-older="loadingOlder"
          :unavailable="loadError !== null && !messagesCurrent"
          :members="snapshot.members"
          :sessions="snapshot.sessions"
          :topics="snapshot.topics"
          :skill-descriptions="skillDescriptions"
          :selected-message-id="detailMessage?.id"
          :details-open="drawerOpen"
          :loading="loading && !messagesCurrent"
          :skeleton-visible="skeletonVisible"
          :refreshing="loading && messagesCurrent"
          :searching="Boolean(keyword)"
          @load-older="loadOlder"
          @latest="loadLatest"
          @reply="quoteMessage"
          @reference="showReference"
          @select="selectMessage"
          @view-details="viewMessageDetails"
          @add-topic="composer?.addTopic($event)"
          @select-member="composer?.selectOnlyMember($event)"
        />
      </div>
      <RoomComposer
        :key="`${snapshot.room.id}:${currentChannelId}`"
        ref="composer"
        v-model:draft="drafts[composerScope]"
        :channel-id="currentChannelId!"
        :room-id="snapshot.room.id"
        :topics="activeTopics"
        :members="orderedMembers"
        :sessions="snapshot.sessions"
        :reply-to="replyTo"
        :sending="sending || clearing"
        :ready="true"
        :locked="Boolean(pendingPublication)"
        :error="sendError"
        :catalog="capabilities.catalog.value"
        :skill-descriptions="skillDescriptions"
        @refresh-capabilities="capabilities.refresh"
        @send="sendMessage"
        @cancel-reply="cancelReply"
      />
      <div v-if="pendingPublication && !sending" class="room-alert" role="status">
        <span>{{ t("room.pending") }}</span>
        <AppButton @click="resumePublication">{{ t("room.checkPublication") }}</AppButton>
      </div>
    </section>

    <template #details="{ collapse }">
      <MessageDetails
        :message="detailMessage"
        :channel="detailChannel"
        :topic="detailTopic"
        :member="detailMember"
        :topics="orderedTopics"
        :members="orderedMembers"
        :sessions="snapshot.sessions"
        :busy="sending || saving || clearing || Boolean(pendingPublication)"
        @close="roomPanel.closeDetails"
        @collapse="collapse"
        @edit-channel="editChannel"
        @delete-channel="openDelete({ kind: 'channel', node: $event })"
        @edit-topic="editTopic"
        @delete-topic="openDelete({ kind: 'topic', node: $event })"
        @edit-member="editMember"
        @select-member="composer?.selectOnlyMember($event)"
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
  <ChannelCreateDialog
    :open="channelCreateOpen"
    :room-id="currentRoomId"
    :source-channel-id="currentChannelId"
    @close="channelCreateOpen = false"
    @created="openCreatedChannel"
  />
  <ChannelEditDialog
    :channel="editingChannel"
    :saving="saving"
    :error="setupError"
    @close="editingChannel = undefined"
    @save="saveChannel"
  />
  <ChannelArchiveDialog
    :channel="archiveTarget"
    :busy="archiving"
    :error="archiveError"
    @close="closeArchive"
    @confirm="archiveChannel"
  />
  <RoomSetupDialog
    :mode="setupMode"
    :topics="activeTopics"
    :saving="saving"
    :error="setupError"
    :sessions="sessions"
    :sessions-loading="sessionsLoading"
    :sessions-error="sessionsError"
    :room-id="currentRoomId"
    :channel-id="currentChannelId"
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
    :channel-id="currentChannelId"
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
    watchPostEffect,
  } from "vue";
  import { useRouter } from "vue-router";
  import { useI18n } from "vue-i18n";
  import { translateMessage } from "@/i18n";
  import type { MessageDescriptor } from "@/i18n";

  import AppButton from "@/components/AppButton.vue";
  import AppIcon from "@/components/AppIcon.vue";
  import AppInput from "@/components/AppInput.vue";
  import ChannelBar from "@/domains/channel/ChannelBar.vue";
  import ChannelArchiveDialog from "@/domains/channel/ChannelArchiveDialog.vue";
  import ChannelCreateDialog from "@/domains/channel/ChannelCreateDialog.vue";
  import ChannelEditDialog from "@/domains/channel/ChannelEditDialog.vue";
  import { DEFAULT_CHANNEL_ID, draftScope } from "@/domains/channel/channelRoutes";
  import { useChannelOrder } from "@/domains/channel/useChannelOrder";
  import { useChannelArchive } from "@/domains/channel/useChannelArchive";
  import MemberEditDialog from "@/domains/room/MemberEditDialog.vue";
  import MemberPanel from "@/domains/room/MemberPanel.vue";
  import MessageDetails from "@/domains/room/MessageDetails.vue";
  import MessageQueue from "@/domains/room/MessageQueue.vue";
  import MessageTimeline from "@/domains/room/MessageTimeline.vue";
  import RoomComposer from "@/domains/room/RoomComposer.vue";
  import RoomClearDialog from "@/domains/room/RoomClearDialog.vue";
  import RoomDeleteDialog from "@/domains/room/RoomDeleteDialog.vue";
  import type { DeleteTarget } from "@/domains/room/RoomDeleteDialog.vue";
  import RoomLoadingSkeleton from "@/domains/room/RoomLoadingSkeleton.vue";
  import RoomSetupDialog from "@/domains/room/RoomSetupDialog.vue";
  import { memberRoleNotFound } from "@/domains/room/useMemberRolePicker";
  import RoomWorkbench from "@/domains/room/RoomWorkbench.vue";
  import TopicSidebar from "@/domains/room/TopicSidebar.vue";
  import { useMessageQueue } from "@/domains/room/useMessageQueue";
  import { useMemberInterrupt } from "@/domains/room/useMemberInterrupt";
  import { useRoomPanel } from "@/domains/room/useRoomPanel";
  import { useRoomCapabilities } from "@/domains/room/useRoomCapabilities";
  import { useRoomDraft } from "@/domains/room/useRoomDraft";
  import { useRoomResourceOrder } from "@/domains/room/useRoomResourceOrder";
  import { loadRoomEventUpdates } from "@/domains/room/roomEventUpdates";
  import { messageQueryKey, mergeRefreshedSnapshot } from "@/domains/room/roomMessageQuery";
  import { useDelayedSkeleton } from "@/domains/room/useDelayedSkeleton";
  import { ApiClientError, describeApiError } from "@/services/api";
  import { channelResourceKey, roomCacheKey } from "@/services/cacheKeys";
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
  import type { Channel, UpdateChannel } from "@/services/channelApi";
  import { useRoomsStore } from "@/stores/rooms";
  import { useNavigationActivity } from "@/stores/navigationActivity";
  import { useChannelsStore } from "@/stores/channels";
  import { useToastsStore } from "@/stores/toasts";

  import "./room.css";

  type ResourceDeleteTarget = Exclude<DeleteTarget, { kind: "room" }>;

  const props = defineProps<{ roomId?: string; channelId?: string }>();
  const { t } = useI18n();
  const router = useRouter();
  const roomsStore = useRoomsStore();
  const channelsStore = useChannelsStore();
  const active = ref(true);
  let activatedBefore = false;
  const toasts = useToastsStore();
  const currentRoomId = ref<string>();
  const currentChannelId = ref<string>();
  const channelCreateOpen = ref(false);
  const snapshot = computed(() =>
    currentRoomId.value && currentChannelId.value
      ? roomsStore.snapshots[roomsStore.snapshotKey(currentRoomId.value, currentChannelId.value)]
      : undefined,
  );
  const { defaultChannel, sortableChannels, availableChannels, moveChannel } = useChannelOrder(
    () => currentRoomId.value,
    () => (currentRoomId.value ? channelsStore.activeChannels(currentRoomId.value) : []),
  );
  const composerScope = computed(() =>
    currentRoomId.value && currentChannelId.value
      ? draftScope(currentRoomId.value, currentChannelId.value)
      : "",
  );
  const searchText = ref("");
  const keyword = ref("");
  const {
    topics: orderedTopics,
    members: orderedMembers,
    activeTopics,
    activeAgents,
    moveTopic,
    moveMember,
  } = useRoomResourceOrder(
    () => snapshot.value,
    () => currentChannelId.value,
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
  const loadedQueryKey = ref<string>();
  const currentQueryKey = computed(() =>
    messageQueryKey(currentRoomId.value, currentChannelId.value, filters()),
  );
  const messagesCurrent = computed(
    () => Boolean(snapshot.value) && loadedQueryKey.value === currentQueryKey.value,
  );
  const requestScope = computed(() =>
    active.value && currentRoomId.value && currentChannelId.value
      ? draftScope(currentRoomId.value, currentChannelId.value)
      : undefined,
  );
  const { interruptingMemberIds, interruptMember } = useMemberInterrupt(
    () => (active.value ? currentRoomId.value : undefined),
    () => currentChannelId.value,
    async (roomId, channelId) => {
      await fetchRoomSessions(roomId, undefined, channelId);
      const metadata = await fetchRoomMetadata(roomId, undefined, channelId);
      roomsStore.syncMetadata(metadata, channelId);
    },
  );
  const messageQueue = useMessageQueue(
    () => (active.value ? currentRoomId.value : undefined),
    () => queueScope.value,
    () => currentChannelId.value,
  );
  const queueCursor = messageQueue.followEvents();
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
  const detailChannel = computed(() => {
    const target = detailTarget.value;
    return target?.kind === "channel"
      ? availableChannels.value.find((channel) => channel.id === target.id)
      : undefined;
  });
  const loading = ref(true);
  const skeletonVisible = useDelayedSkeleton(
    () => active.value && loading.value && !messagesCurrent.value,
    () => currentQueryKey.value,
  );
  const refreshingSessions = ref(false);
  const loadingOlder = ref(false);
  const sending = ref(false);
  const loadError = ref<MessageDescriptor | null>(null);
  const sendError = ref<MessageDescriptor | null>(null);
  const replyTo = ref<RoomMessage>();
  const composer = ref<InstanceType<typeof RoomComposer>>();
  const timeline = ref<InstanceType<typeof MessageTimeline>>();
  const activity = useNavigationActivity();
  watchPostEffect(() => {
    const roomId = currentRoomId.value;
    const channelId = currentChannelId.value;
    if (
      !active.value ||
      !activity.visible ||
      !roomId ||
      !channelId ||
      roomId !== props.roomId ||
      channelId !== props.channelId ||
      !timeline.value ||
      loading.value ||
      loadError.value ||
      !messagesCurrent.value ||
      selectedTopicId.value ||
      selectedMemberId.value ||
      keyword.value
    ) {
      return;
    }
    const last = visibleMessages.value.at(-1);
    if (last) {
      activity.presented(roomId, channelId, last.seq);
    }
  });
  const pendingPublication = ref<CreateMessage>();
  const {
    drafts,
    open: openDraft,
    finish: finishDraft,
  } = useRoomDraft(undefined, () => sending.value || Boolean(pendingPublication.value));
  const capabilities = useRoomCapabilities(
    () => roomsStore.rooms.find((room) => room.id === currentRoomId.value),
    () => currentChannelId.value,
  );
  const skillDescriptions = computed(
    () => new Map(capabilities.catalog.value.skills.map((skill) => [skill.id, skill.description])),
  );
  const setupMode = ref<"member" | "topic">();
  const editingMember = ref<Member>();
  const editingTopic = ref<Topic>();
  const editingChannel = ref<Channel>();
  const deleteTarget = ref<ResourceDeleteTarget>();
  const saving = ref(false);
  const clearOpen = ref(false);
  const clearing = ref(false);
  const {
    target: archiveTarget,
    busy: archiving,
    error: archiveError,
    open: openArchive,
    close: closeArchive,
    confirm: confirmArchive,
  } = useChannelArchive(
    () => currentRoomId.value,
    () => currentChannelId.value,
    () => saving.value || sending.value || clearing.value || Boolean(pendingPublication.value),
  );
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
    if (!active.value) {
      return;
    }
    const nextKeyword = searchText.value.trim();
    if (nextKeyword === keyword.value) {
      return;
    }
    keyword.value = nextKeyword;
    await loadLatest();
  }

  async function submitSearch(): Promise<void> {
    clearTimeout(searchTimer);
    if (loading.value || refreshingSessions.value || sending.value || clearing.value) {
      return;
    }
    keyword.value = searchText.value.trim();
    if (keyword.value) {
      await loadLatest();
    } else {
      await refreshRoom();
    }
  }

  function cancelQueries(): number {
    stopEvents?.();
    stopEvents = undefined;
    queryController?.abort();
    queryController = new AbortController();
    loadingOlder.value = false;
    return ++loadVersion;
  }

  function startEvents(scope: string, roomId: string, version: number): void {
    const current = roomsStore.snapshots[scope];
    const channelId = currentChannelId.value;
    if (!current || !channelId || version !== loadVersion) {
      return;
    }
    stopEvents = subscribeRoomEvents(
      roomId,
      queueCursor.resume(current.eventId),
      async (page: RoomEventPage) => {
        if (version !== loadVersion) {
          return;
        }
        if (page.resyncRequired) {
          queueCursor.reset();
          roomPanel.closeDetails();
          replyTo.value = undefined;
          messageQueue.reset();
          await loadRoom();
          return;
        }
        const events = page.events.filter((event) => event.eventId > current.eventId);
        if (!events.length) {
          queueCursor.advance(page);
          return;
        }
        if (events.some((event) => event.kind === "room" && event.entityId === channelId)) {
          await channelsStore.load(roomId, true);
          if (version !== loadVersion) {
            return;
          }
        }
        const signal = queryController?.signal;
        const retainedIds = new Set(current.messages.map((message) => message.id));
        if (detailMessage.value) {
          retainedIds.add(detailMessage.value.id);
        }
        if (replyTo.value) {
          retainedIds.add(replyTo.value.id);
        }
        const { state, messages } = await loadRoomEventUpdates(
          roomId,
          channelId,
          events,
          filters(),
          retainedIds,
          signal,
        );
        if (version !== loadVersion) {
          return;
        }
        if ("room" in state) {
          roomsStore.syncMetadata(state, channelId);
        } else {
          roomsStore.syncActivity(roomId, state, channelId);
        }
        queueCursor.advance(page);
        if (clearDeletedFilters()) {
          await loadRoom();
          return;
        }
        const wasAtEnd = timeline.value?.isAtEnd();
        const previousSeq = current.messages.at(-1)?.seq ?? 0;
        roomsStore.applyMessages(roomId, messages, filters(), channelId);
        roomPanel.syncMessages(messages);
        const updatedReply = messages.find((message) => message.id === replyTo.value?.id);
        if (updatedReply) {
          replyTo.value = updatedReply;
        }
        current.eventId = page.nextEventId;
        const newest = current.messages.at(-1);
        if (wasAtEnd && newest && newest.seq > previousSeq) {
          await nextTick();
          if (version === loadVersion) {
            timeline.value?.scrollToEnd();
          }
        }
      },
      undefined,
      channelId,
    );
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

  async function loadRoom(
    options: { beforeSeq?: number; preservePosition?: boolean } = {},
  ): Promise<boolean> {
    const roomId = currentRoomId.value;
    const channelId = currentChannelId.value;
    if (!roomId || !channelId || !active.value) {
      return false;
    }
    const scope = roomsStore.snapshotKey(roomId, channelId);
    const query = filters();
    const queryKey = messageQueryKey(roomId, channelId, query);
    const previous =
      options.beforeSeq === undefined && options.preservePosition !== false && messagesCurrent.value
        ? snapshot.value
        : undefined;
    const endSeq = previous?.messages.at(-1)?.seq;
    const beforeSeq =
      options.beforeSeq ??
      (endSeq !== undefined && !timeline.value?.isAtEnd() ? endSeq + 1 : undefined);
    const version = cancelQueries();
    loading.value = true;
    loadError.value = null;
    try {
      const result = await fetchRoom(
        roomId,
        { ...query, beforeSeq },
        queryController?.signal,
        channelId,
      );
      if (version !== loadVersion) {
        return false;
      }
      const position = previous ? timeline.value?.capturePosition() : undefined;
      roomsStore.sync(previous ? mergeRefreshedSnapshot(previous, result) : result, channelId);
      loadedQueryKey.value = queryKey;
      roomPanel.syncMessages(result.messages);
      if (position) {
        await nextTick();
        if (version !== loadVersion) {
          return false;
        }
        timeline.value?.restorePosition(position);
      }
      if (clearDeletedFilters()) {
        return await loadRoom();
      }
      await refreshDetailMessage(roomId, version);
      await refreshReplyTo(roomId, version);
      if (version !== loadVersion) {
        return false;
      }
      startEvents(scope, roomId, version);
      return true;
    } catch (caught) {
      if (version === loadVersion) {
        loadError.value = describeApiError(caught, "errors.messageLoad");
        toasts.error(loadError.value);
      }
      return false;
    } finally {
      if (version === loadVersion) {
        loading.value = false;
      }
    }
  }

  async function refreshDetailMessage(roomId: string, version: number): Promise<void> {
    const target = detailTarget.value;
    const channelId = currentChannelId.value;
    if (target?.kind !== "message" || !channelId) {
      return;
    }
    const selected = target.message;
    try {
      const message = await fetchRoomMessage(
        roomId,
        selected.id,
        queryController?.signal,
        channelId,
      );
      if (version === loadVersion) {
        roomPanel.syncMessages([message]);
      }
    } catch (caught) {
      if (version === loadVersion) {
        toasts.error(describeApiError(caught, "errors.detailLoad"));
      }
    }
  }

  async function refreshReplyTo(roomId: string, version: number): Promise<void> {
    const scope = requestScope.value;
    const channelId = currentChannelId.value;
    const draft = scope ? drafts.value[scope] : undefined;
    const messageId = draft?.replyToMessageId;
    if (!messageId || !channelId) {
      return;
    }
    const current = () =>
      version === loadVersion &&
      currentRoomId.value === roomId &&
      scope !== undefined &&
      drafts.value[scope]?.replyToMessageId === messageId;
    try {
      const message =
        visibleMessages.value.find((message) => message.id === messageId) ??
        (await fetchRoomMessage(roomId, messageId, queryController?.signal, channelId));
      if (current()) {
        replyTo.value = message;
      }
    } catch (caught) {
      if (!current()) {
        return;
      }
      if (caught instanceof ApiClientError && caught.status === 404 && !pendingPublication.value) {
        cancelReply();
      }
      toasts.error(describeApiError(caught, "errors.detailLoad"));
    }
  }

  async function loadLatest(): Promise<void> {
    if (!(await loadRoom({ preservePosition: false }))) {
      return;
    }
    await nextTick();
    timeline.value?.scrollToEnd();
  }

  async function loadOlder(): Promise<void> {
    const roomId = currentRoomId.value;
    const channelId = currentChannelId.value;
    const beforeSeq = snapshot.value?.nextBeforeSeq;
    if (!roomId || !channelId || !beforeSeq || loadingOlder.value || loading.value) {
      return;
    }
    const scope = roomsStore.snapshotKey(roomId, channelId);
    const version = cancelQueries();
    loadingOlder.value = true;
    try {
      const page = await fetchRoomMessages(
        roomId,
        { ...filters(), beforeSeq },
        queryController?.signal,
        channelId,
      );
      if (version !== loadVersion) {
        return;
      }
      timeline.value?.rememberScroll();
      roomsStore.prependPage(roomId, page, channelId);
      await nextTick();
      timeline.value?.restoreScroll();
    } catch (caught) {
      if (version === loadVersion) {
        toasts.error(describeApiError(caught, "errors.historyLoad"));
      }
    } finally {
      if (version === loadVersion) {
        loadingOlder.value = false;
        startEvents(scope, roomId, version);
      }
    }
  }

  async function initialize(): Promise<void> {
    const version = ++initializationVersion;
    loading.value = true;
    loadError.value = null;
    try {
      await roomsStore.load();
      if (!active.value || version !== initializationVersion) {
        return;
      }
      if (props.roomId && props.channelId) {
        await openRoom(props.roomId, props.channelId);
      } else if (roomsStore.rooms.length) {
        await router.replace(
          channelRoute(
            roomsStore.rooms[0].id,
            channelsStore.preferredChannel(roomsStore.rooms[0].id) ?? DEFAULT_CHANNEL_ID,
          ),
        );
      } else {
        loading.value = false;
      }
    } catch (caught) {
      if (!active.value || version !== initializationVersion) {
        return;
      }
      loadError.value = describeApiError(caught, "errors.roomLoad");
      toasts.error(loadError.value);
      loading.value = false;
    }
  }

  async function openRoom(roomId: string, requestedChannelId: string): Promise<void> {
    initializationVersion++;
    const version = cancelQueries();
    loading.value = true;
    loadError.value = null;
    const previouslySelectedChannel = channelsStore.preferredChannel(roomId);
    resetSearch();
    roomPanel.reset();
    currentRoomId.value = roomId;
    currentChannelId.value = undefined;
    roomsStore.recentRoomId = roomId;
    channelCreateOpen.value = false;
    try {
      await channelsStore.load(roomId, true);
    } catch {
      if (version !== loadVersion || !active.value) {
        return;
      }
      loadError.value = channelsStore.errors[roomCacheKey(roomId, "channels")] ?? {
        key: "errors.channelLoad",
      };
      loading.value = false;
      return;
    }
    if (version !== loadVersion || !active.value) {
      return;
    }
    const requested = channelsStore.resolveChannelId(roomId, requestedChannelId);
    const cachedFallback =
      requestedChannelId === previouslySelectedChannel
        ? channelsStore.resolveChannelId(roomId, DEFAULT_CHANNEL_ID)
        : undefined;
    const channelId = requested ?? cachedFallback;
    if (!channelId) {
      loadError.value = { key: "errors.channel_not_found" };
      loading.value = false;
      return;
    }
    const route = channelRoute(roomId, channelId);
    if (requestedChannelId !== route.params.channelId) {
      void router.replace(route);
    }
    await openChannel(roomId, channelId);
  }

  function channelRoute(roomId: string, channelId: string) {
    return {
      name: "channel",
      params: { roomId, channelId },
    };
  }

  async function openChannel(
    roomId: string,
    channelId: string,
    showDetails = false,
  ): Promise<void> {
    resetSearch();
    currentChannelId.value = channelId;
    queueCursor.reset();
    channelsStore.remember(roomId, channelId);
    cancelQueries();
    const scope = roomsStore.snapshotKey(roomId, channelId);
    loadedQueryKey.value = undefined;
    delete roomsStore.snapshots[scope];
    setupMode.value = undefined;
    editingMember.value = undefined;
    editingTopic.value = undefined;
    editingChannel.value = undefined;
    deleteTarget.value = undefined;
    clearOpen.value = false;
    clearError.value = null;
    sessionsVersion++;
    sessionsController?.abort();
    sessions.value = [];
    sessionsLoading.value = false;
    sessionsError.value = null;
    roomPanel.changeChannel();
    if (showDetails) {
      roomPanel.selectChannel(channelId);
    }
    messageQueue.reset();
    replyTo.value = undefined;
    sendError.value = null;
    const saved = sessionStorage.getItem(channelResourceKey(scope, "publication"));
    pendingPublication.value = saved ? (JSON.parse(saved) as CreateMessage) : undefined;
    openDraft(scope, pendingPublication.value);
    if (!(await loadRoom())) {
      return;
    }
    await nextTick();
    if (currentRoomId.value === roomId && currentChannelId.value === channelId) {
      timeline.value?.scrollToEnd();
    }
  }

  async function retry(): Promise<void> {
    if (currentRoomId.value && props.channelId && !currentChannelId.value) {
      await openRoom(currentRoomId.value, props.channelId);
    } else if (currentRoomId.value) {
      await loadRoom();
    } else {
      await initialize();
    }
  }

  function openChannelCreate(): void {
    if (!currentChannelId.value) {
      return;
    }
    channelCreateOpen.value = true;
  }

  async function selectChannel(channelId: string): Promise<void> {
    const roomId = currentRoomId.value;
    if (!roomId) {
      return;
    }
    if (channelId === currentChannelId.value) {
      roomPanel.selectChannel(channelId);
      return;
    }
    await openChannel(roomId, channelId, true);
    if (currentRoomId.value === roomId && currentChannelId.value === channelId) {
      await router.push(channelRoute(roomId, channelId));
    }
  }

  async function openCreatedChannel(channelId: string): Promise<void> {
    channelCreateOpen.value = false;
    toasts.success({ key: "notice.channelCreated" });
    if (!currentRoomId.value) {
      return;
    }
    await selectChannel(channelId);
  }

  async function selectSidebar(
    kind: "topic" | "member",
    resourceId: string | undefined,
  ): Promise<void> {
    if (!roomPanel.selectSidebar(kind, resourceId)) {
      return;
    }
    if (kind === "topic") {
      composer.value?.selectTopic(resourceId);
    } else {
      composer.value?.selectMember(resourceId);
    }
    await loadLatest();
  }

  function selectMessage(messageId: string): void {
    const message =
      visibleMessages.value.find((message) => message.id === messageId) ??
      queueMessages.value.find((message) => message.id === messageId);
    if (message) {
      roomPanel.selectMessage(message);
    }
  }

  function viewMessageDetails(messageId: string): void {
    selectMessage(messageId);
    roomPanel.openDrawer();
  }

  function selectQueueMessage(messageId: string): void {
    selectMessage(messageId);
    timeline.value?.scrollToMessage(messageId);
  }

  function quoteMessage(message: RoomMessage): void {
    if (sending.value || pendingPublication.value) {
      return;
    }
    replyTo.value = message;
    void composer.value?.quote(message);
  }

  function cancelReply(): void {
    const scope = requestScope.value;
    const draft = scope ? drafts.value[scope] : undefined;
    if (draft) {
      draft.replyToMessageId = undefined;
    }
    replyTo.value = undefined;
  }

  async function sendMessage(draft: MessageDraft): Promise<void> {
    const scope = requestScope.value;
    if (sending.value || clearing.value || !scope) {
      return;
    }
    if (pendingPublication.value) {
      return;
    }
    const request = { ...draft, publicationId: crypto.randomUUID() };
    sessionStorage.setItem(channelResourceKey(scope, "publication"), JSON.stringify(request));
    pendingPublication.value = request;
    await publish(request);
  }

  async function resumePublication(): Promise<void> {
    if (pendingPublication.value && !sending.value) {
      await publish(pendingPublication.value, true);
    }
  }

  async function publish(request: CreateMessage, lookup = false): Promise<void> {
    const scope = requestScope.value;
    if (!currentRoomId.value || !currentChannelId.value || !scope) {
      return;
    }
    const roomId = currentRoomId.value;
    const channelId = currentChannelId.value;
    sending.value = true;
    sendError.value = null;
    let sentMessage: RoomMessage;
    try {
      if (lookup) {
        try {
          sentMessage = await fetchPublication(roomId, request.publicationId, channelId);
        } catch (caught) {
          if (!(caught instanceof ApiClientError) || caught.status !== 404) {
            throw caught;
          }
          sentMessage = await postRoomMessage(roomId, request, channelId);
        }
      } else {
        sentMessage = await postRoomMessage(roomId, request, channelId);
      }
    } catch (caught) {
      if (
        caught instanceof ApiClientError &&
        caught.kind === "http_error" &&
        [404, 409, 422].includes(caught.status ?? 0)
      ) {
        sessionStorage.removeItem(channelResourceKey(scope, "publication"));
        if (scope === requestScope.value) {
          pendingPublication.value = undefined;
        }
      }
      const message = describeApiError(caught, "errors.publish");
      if (scope === requestScope.value) {
        sendError.value = message;
      }
      toasts.error(message);
      sending.value = false;
      return;
    }
    sessionStorage.removeItem(channelResourceKey(scope, "publication"));
    finishDraft(scope, request);
    if (scope !== requestScope.value) {
      sending.value = false;
      return;
    }
    roomPanel.selectMessage(sentMessage);
    pendingPublication.value = undefined;
    composer.value?.reset();
    replyTo.value = undefined;
    toasts.success({ key: "notice.published" });
    selectedMemberId.value = undefined;
    if (selectedTopicId.value && !request.topicIds.includes(selectedTopicId.value)) {
      selectedTopicId.value = request.topicIds[0];
    }
    await loadRoom({ preservePosition: false });
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
    if (mode === "member") {
      void loadSessions();
    }
  }

  async function loadSessions(): Promise<void> {
    if (!currentRoomId.value || !currentChannelId.value || !active.value) {
      return;
    }
    const roomId = currentRoomId.value;
    const channelId = currentChannelId.value;
    const version = ++sessionsVersion;
    sessionsController?.abort();
    sessionsController = new AbortController();
    sessionsLoading.value = true;
    sessionsError.value = null;
    try {
      const result = await fetchRoomSessions(roomId, sessionsController.signal, channelId);
      if (version === sessionsVersion) {
        sessions.value = result;
      }
    } catch (caught) {
      if (version === sessionsVersion) {
        sessions.value = [];
        sessionsError.value = describeApiError(caught, "errors.sessionLoad");
      }
    } finally {
      if (version === sessionsVersion) {
        sessionsLoading.value = false;
      }
    }
  }

  async function refreshRoom(): Promise<void> {
    if (
      !currentRoomId.value ||
      !currentChannelId.value ||
      refreshingSessions.value ||
      sending.value ||
      clearing.value
    ) {
      return;
    }
    const roomId = currentRoomId.value;
    const channelId = currentChannelId.value;
    const version = initializationVersion;
    refreshController = new AbortController();
    refreshingSessions.value = true;
    try {
      await fetchRoomSessions(roomId, refreshController.signal, channelId);
    } catch (caught) {
      if (active.value && version === initializationVersion) {
        toasts.error(describeApiError(caught, "errors.sessionRefresh"));
      }
    } finally {
      if (version === initializationVersion) {
        refreshingSessions.value = false;
      }
    }
    if (
      !active.value ||
      version !== initializationVersion ||
      roomId !== currentRoomId.value ||
      channelId !== currentChannelId.value ||
      !(await loadRoom())
    ) {
      return;
    }
  }

  function editChannel(channel: Channel): void {
    if (channel.isDefault) {
      return;
    }
    setupError.value = null;
    editingChannel.value = channel;
  }

  async function archiveChannel(name: string): Promise<void> {
    if (await confirmArchive(name)) {
      toasts.success({ key: "notice.channelArchived" });
    }
  }

  async function saveChannel(channelId: string, request: UpdateChannel): Promise<void> {
    if (!currentRoomId.value || channelId === DEFAULT_CHANNEL_ID) {
      return;
    }
    const roomId = currentRoomId.value;
    await saveSetup(async () => {
      await channelsStore.update(roomId, channelId, request);
    }, "notice.channelSaved");
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
    if (target.kind === "channel" && target.node.isDefault) {
      return;
    }
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
    const channelId = currentChannelId.value;
    if (
      !roomId ||
      !channelId ||
      !clearOpen.value ||
      saving.value ||
      sending.value ||
      pendingPublication.value
    ) {
      return;
    }
    clearing.value = true;
    saving.value = true;
    clearError.value = null;
    const version = cancelQueries();
    messageQueue.cancel();
    try {
      const result = await roomsStore.clear(roomId, channelId);
      toasts.success({
        key: "notice.cleared",
        params: { messages: result.removedMessages, members: result.removedMembers },
      });
      if (currentRoomId.value !== roomId || currentChannelId.value !== channelId) {
        return;
      }
      clearOpen.value = false;
      roomPanel.reset();
      queueCursor.reset();
      messageQueue.reset();
      cancelReply();
      resetSearch();
      await loadLatest();
    } catch (caught) {
      const message = describeApiError(caught, "errors.clear");
      if (currentRoomId.value === roomId && currentChannelId.value === channelId) {
        clearError.value = message;
        startEvents(roomsStore.snapshotKey(roomId, channelId), roomId, version);
        void messageQueue.refresh();
      }
      toasts.error(message);
    } finally {
      clearing.value = false;
      saving.value = false;
    }
  }

  async function saveSetup(action: () => Promise<void>, successMessage: string): Promise<void> {
    if (saving.value) {
      return;
    }
    saving.value = true;
    setupError.value = null;
    const roomId = currentRoomId.value;
    const channelId = currentChannelId.value;
    try {
      await action();
      toasts.success({ key: successMessage });
      if (roomId === currentRoomId.value && channelId === currentChannelId.value) {
        setupMode.value = undefined;
        editingMember.value = undefined;
        editingChannel.value = undefined;
      }
    } catch (caught) {
      const message = describeApiError(caught, "errors.save");
      if (roomId === currentRoomId.value && channelId === currentChannelId.value) {
        setupError.value = message;
        if (setupMode.value === "member" && message.key === memberRoleNotFound) {
          return;
        }
      }
      toasts.error(message);
    } finally {
      saving.value = false;
    }
  }

  function applyResourceChange(metadata: RoomMetadata, channelId: string): void {
    roomsStore.syncMetadata(metadata, channelId);
    if (
      metadata.room.id === currentRoomId.value &&
      channelId === currentChannelId.value &&
      clearDeletedFilters()
    ) {
      void loadRoom();
    }
  }

  async function saveNewMember(request: CreateMember): Promise<void> {
    if (!currentRoomId.value || !currentChannelId.value) {
      return;
    }
    const roomId = currentRoomId.value;
    const channelId = currentChannelId.value;
    await saveSetup(async () => {
      const result = await addRoomMember(roomId, request, channelId);
      applyResourceChange(result.metadata, channelId);
    }, "notice.memberAdded");
  }

  async function saveMember(memberId: string, request: UpdateMember): Promise<void> {
    if (!currentRoomId.value || !currentChannelId.value) {
      return;
    }
    const roomId = currentRoomId.value;
    const channelId = currentChannelId.value;
    await saveSetup(async () => {
      const result = await updateRoomMember(roomId, memberId, request, channelId);
      applyResourceChange(result.metadata, channelId);
    }, "notice.memberSaved");
  }

  async function saveNewTopic(request: CreateTopic): Promise<void> {
    if (!currentRoomId.value || !currentChannelId.value) {
      return;
    }
    const roomId = currentRoomId.value;
    const channelId = currentChannelId.value;
    await saveSetup(async () => {
      const result = await addRoomTopic(roomId, request, channelId);
      applyResourceChange(result.metadata, channelId);
    }, "notice.topicCreated");
  }

  async function saveTopic(topicId: string, request: CreateTopic): Promise<void> {
    if (!currentRoomId.value || !currentChannelId.value) {
      return;
    }
    const roomId = currentRoomId.value;
    const channelId = currentChannelId.value;
    await saveSetup(async () => {
      const result = await updateRoomTopic(roomId, topicId, request, channelId);
      applyResourceChange(result.metadata, channelId);
    }, "notice.topicSaved");
  }

  async function deleteNode(): Promise<void> {
    if (
      saving.value ||
      sending.value ||
      clearing.value ||
      !currentRoomId.value ||
      !currentChannelId.value ||
      !deleteTarget.value
    ) {
      return;
    }
    const roomId = currentRoomId.value;
    const channelId = currentChannelId.value;
    const target = deleteTarget.value;
    if (target.kind === "channel" && (target.node.isDefault || pendingPublication.value)) {
      return;
    }
    saving.value = true;
    setupError.value = null;
    try {
      if (target.kind === "channel") {
        await channelsStore.remove(roomId, target.node.id);
        delete roomsStore.snapshots[roomsStore.snapshotKey(roomId, target.node.id)];
        if (currentRoomId.value === roomId) {
          deleteTarget.value = undefined;
          if (currentChannelId.value === target.node.id) {
            await openChannel(roomId, DEFAULT_CHANNEL_ID);
            await router.replace(channelRoute(roomId, DEFAULT_CHANNEL_ID));
          } else if (
            detailTarget.value?.kind === "channel" &&
            detailTarget.value.id === target.node.id
          ) {
            roomPanel.closeDetails();
          }
        }
        toasts.success({ key: "notice.channelDeleted" });
        return;
      }
      const result =
        target.kind === "topic"
          ? await deleteRoomTopic(roomId, target.node.id, channelId)
          : await deleteRoomMember(roomId, target.node.id, channelId);
      applyResourceChange(result.metadata, channelId);
      toasts.success({
        key: target.kind === "topic" ? "notice.topicDeleted" : "notice.memberDeleted",
      });
      if (currentRoomId.value === roomId) {
        deleteTarget.value = undefined;
      }
    } catch (caught) {
      const message = describeApiError(caught, "errors.remove");
      if (currentRoomId.value === roomId) {
        setupError.value = message;
      }
      toasts.error(message);
    } finally {
      saving.value = false;
    }
  }

  async function showReference(messageId: string): Promise<void> {
    const roomId = currentRoomId.value;
    const channelId = currentChannelId.value;
    if (!roomId || !channelId) {
      return;
    }
    if (!visibleMessages.value.some((message) => message.id === messageId)) {
      const version = loadVersion;
      try {
        const message = await fetchRoomMessage(
          roomId,
          messageId,
          queryController?.signal,
          channelId,
        );
        if (version !== loadVersion) {
          return;
        }
        selectedTopicId.value = undefined;
        selectedMemberId.value = undefined;
        resetSearch();
        if (!(await loadRoom({ beforeSeq: message.seq + 1 }))) {
          return;
        }
      } catch (caught) {
        if (version === loadVersion) {
          toasts.error(describeApiError(caught, "errors.reference"));
        }
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
    queueCursor.reset();
    capabilities.resume();
    if (currentRoomId.value && currentChannelId.value) {
      keyword.value = searchText.value.trim();
      void loadRoom();
      if (setupMode.value === "member") {
        void loadSessions();
      }
    } else {
      void initialize();
    }
  });
  onBeforeUnmount(pauseReads);

  watch(searchText, (value) => {
    clearTimeout(searchTimer);
    if (!value.trim()) {
      void applySearch();
    } else {
      searchTimer = setTimeout(() => void applySearch(), 300);
    }
  });

  watch([() => props.roomId, () => props.channelId], ([roomId, channelId]) => {
    if (!roomId || !channelId) {
      cancelQueries();
      messageQueue.reset();
      roomPanel.reset();
      sessionsVersion++;
      currentRoomId.value = undefined;
      currentChannelId.value = undefined;
      pendingPublication.value = undefined;
      void initialize();
      return;
    }
    if (
      currentRoomId.value !== roomId ||
      !currentChannelId.value ||
      !channelsStore.loadedRooms[roomCacheKey(roomId, "channels")]
    ) {
      void openRoom(roomId, channelId);
      return;
    }
    if (!channelsStore.activeChannels(roomId).some((channel) => channel.id === channelId)) {
      cancelQueries();
      messageQueue.reset();
      roomPanel.reset();
      currentChannelId.value = undefined;
      loadError.value = { key: "errors.channel_not_found" };
      loading.value = false;
      return;
    }
    if (channelId !== currentChannelId.value) {
      void openChannel(roomId, channelId);
    }
  });

  onMounted(initialize);
</script>
