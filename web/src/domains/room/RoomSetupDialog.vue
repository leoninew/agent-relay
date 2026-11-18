<template>
  <AppDialog
    :open="mode !== undefined"
    :title="title"
    :busy="saving || topicSaving"
    initial-focus="#setup-name"
    @close="$emit('close')"
  >
    <form class="setup-form" novalidate @submit.prevent="submit">
      <div class="setup-form-content">
        <div class="setup-field">
          <label for="setup-name">
            {{ nameLabel }}
            <span class="required-mark">*</span>
          </label>
          <AppInput
            id="setup-name"
            v-model="name"
            :maxlength="mode === 'topic' ? 40 : 80"
            :disabled="saving"
            :invalid="!!errors.name"
            :clear-label="t('forms.clearName')"
            aria-describedby="setup-name-error"
            autocomplete="off"
          />
          <p v-if="errors.name" id="setup-name-error" class="field-error">
            {{ translateMessage(errors.name) }}
          </p>
        </div>
        <div v-if="mode === 'room'" class="setup-field">
          <label for="setup-path"
            >{{ t("setup.workspacePath") }} <span class="required-mark">*</span></label
          >
          <AppInput
            id="setup-path"
            v-model="workspacePath"
            maxlength="500"
            :disabled="saving"
            :invalid="!!errors.workspacePath"
            :clear-label="t('setup.clearPath')"
            aria-describedby="setup-path-error"
            placeholder=""
            autocomplete="off"
          />
          <p v-if="errors.workspacePath" id="setup-path-error" class="field-error">
            {{ translateMessage(errors.workspacePath) }}
          </p>
        </div>
        <MemberTopicsField
          v-if="mode === 'member'"
          v-model="topicIds"
          v-model:busy="topicSaving"
          id-prefix="setup-member"
          :topics="topics"
          :room-id="roomId"
          :channel-id="channelId"
          :disabled="saving"
        />
        <div v-if="mode === 'member'" class="setup-field grid-cols-1">
          <div class="setup-field-heading">
            <label id="setup-session-label"
              >{{ t("setup.selectSession") }} <span class="required-mark">*</span></label
            >
            <AppButton
              v-if="!sessionsLoading"
              variant="plain"
              class="session-reload"
              :disabled="saving || topicSaving"
              @click="$emit('reloadSessions')"
            >
              {{ t("setup.refreshSessions") }}
            </AppButton>
          </div>
          <AppLoading v-if="sessionsLoading" class="session-state">{{
            t("setup.loadingSessions")
          }}</AppLoading>
          <p v-else-if="sessionsError" class="field-error" role="alert">
            {{ translateMessage(sessionsError) }}
          </p>
          <template v-else>
            <RadioGroupRoot
              v-model="sessionId"
              class="grid grid-cols-1 gap-2 rounded-md"
              :disabled="saving"
              aria-labelledby="setup-session-label"
              :aria-invalid="!!errors.session"
              aria-describedby="setup-session-error"
            >
              <div
                class="max-h-72 overflow-x-hidden overflow-y-auto rounded-md border border-border bg-card"
                :class="{ 'border-destructive': !!errors.session }"
              >
                <template v-if="availableSessions.length">
                  <div
                    v-for="session in availableSessions"
                    :key="session.id"
                    class="relative border-b border-border last:border-b-0"
                  >
                    <RadioGroupItem
                      :value="session.id"
                      class="group block w-full border-s-2 border-transparent px-3 py-2.5 text-start outline-none transition-colors hover:bg-muted/40 focus-visible:z-10 focus-visible:outline focus-visible:outline-1 focus-visible:outline-dashed focus-visible:outline-muted-foreground disabled:opacity-60 data-[state=checked]:border-s-primary data-[state=checked]:bg-primary/5 motion-reduce:transition-none"
                      :aria-invalid="!!errors.session"
                    >
                      <span class="grid min-w-0 grid-cols-1 gap-1">
                        <span class="flex min-w-0 items-center gap-3">
                          <span class="min-w-0 flex-1 truncate font-medium" :title="session.name">
                            {{ session.name }}
                          </span>
                          <span class="shrink-0 text-xs text-muted-foreground">
                            {{ sessionStatus(session) }}
                          </span>
                        </span>
                        <span
                          class="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs text-muted-foreground"
                        >
                          <span>{{ t("setup.joinedChannels") }}</span>
                          <span
                            v-for="channel in session.joinedChannels"
                            :key="channel.id"
                            class="max-w-full rounded bg-muted px-1.5 py-0.5 break-all group-data-[state=checked]:bg-card"
                          >
                            {{ channel.name }}
                          </span>
                          <span v-if="!session.joinedChannels.length">
                            {{ t("setup.noJoinedChannels") }}
                          </span>
                        </span>
                      </span>
                    </RadioGroupItem>
                  </div>
                </template>
                <div v-else class="px-3 py-3 text-sm text-muted-foreground">
                  {{ t(sessions?.length ? "setup.noAvailable" : "setup.noSessions") }}
                </div>
              </div>
            </RadioGroupRoot>
            <CollapsibleRoot
              v-if="unavailableSessions.length"
              v-model:open="unavailableOpen"
              :disabled="saving"
              class="mt-2"
            >
              <CollapsibleTrigger
                class="group inline-flex items-center gap-1.5 rounded-sm py-1 text-start text-xs text-muted-foreground hover:text-foreground focus-visible:outline focus-visible:outline-1 focus-visible:outline-dashed focus-visible:outline-muted-foreground"
              >
                <AppIcon
                  name="chevron"
                  class="size-3.5 shrink-0 transition-transform group-data-[state=open]:rotate-90 motion-reduce:transition-none"
                />
                <span>{{ t("setup.unavailableSessions") }}</span>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <ul
                  :aria-label="t('setup.unavailableSessions')"
                  class="mt-1 max-h-48 overflow-x-hidden overflow-y-auto rounded-md border border-border bg-card"
                >
                  <li
                    v-for="session in unavailableSessions"
                    :key="session.id"
                    class="flex min-w-0 items-center gap-3 border-b border-border px-3 py-2 last:border-b-0"
                  >
                    <span
                      class="min-w-0 flex-1 truncate text-sm text-muted-foreground"
                      :title="session.name"
                    >
                      {{ session.name }}
                    </span>
                    <AppTooltip :text="unavailableReason(session)">
                      <button
                        type="button"
                        class="shrink-0 cursor-help rounded-sm text-xs text-muted-foreground underline decoration-dotted underline-offset-2 focus-visible:outline-1 focus-visible:outline-dashed focus-visible:outline-muted-foreground"
                      >
                        {{ sessionStatus(session) }}
                      </button>
                    </AppTooltip>
                  </li>
                </ul>
              </CollapsibleContent>
            </CollapsibleRoot>
          </template>
          <p v-if="errors.session" id="setup-session-error" class="field-error">
            {{ translateMessage(errors.session) }}
          </p>
        </div>
        <div v-if="mode === 'topic'" class="setup-field">
          <label for="setup-description">{{ t("setup.topicDescription") }}</label>
          <AppInput
            id="setup-description"
            v-model="description"
            maxlength="300"
            :disabled="saving"
            :clear-label="t('setup.clearDescription')"
          />
        </div>
        <p v-if="error" class="field-error" role="alert">{{ translateMessage(error) }}</p>
      </div>
      <footer class="dialog-actions">
        <AppButton variant="secondary" :disabled="saving || topicSaving" @click="$emit('close')">
          {{ t("common.cancel") }}
        </AppButton>
        <AppButton
          type="submit"
          :loading="saving"
          :loading-label="t('settings.saving')"
          :disabled="topicSaving || (mode === 'member' && (sessionsLoading || !!sessionsError))"
        >
          {{ topic ? t("setup.saveTopic") : mode === "room" && room ? t("setup.saveName") : title }}
        </AppButton>
      </footer>
    </form>
  </AppDialog>
</template>

<script setup lang="ts">
  import { useI18n } from "vue-i18n";
  import { translateMessage } from "@/i18n";
  import type { MessageDescriptor } from "@/i18n";
  import {
    CollapsibleContent,
    CollapsibleRoot,
    CollapsibleTrigger,
    RadioGroupItem,
    RadioGroupRoot,
  } from "reka-ui";
  import { computed, ref, watch } from "vue";

  import AppButton from "@/components/AppButton.vue";
  import AppDialog from "@/components/AppDialog.vue";
  import AppIcon from "@/components/AppIcon.vue";
  import AppInput from "@/components/AppInput.vue";
  import AppLoading from "@/components/AppLoading.vue";
  import AppTooltip from "@/components/AppTooltip.vue";
  import MemberTopicsField from "@/domains/room/MemberTopicsField.vue";
  import type {
    CreateMember,
    CreateRoom,
    CreateTopic,
    SessionCandidate,
    Room,
    Topic,
    UpdateRoom,
  } from "@/services/roomApi";

  import "./member-session.css";

  const props = defineProps<{
    mode: "room" | "member" | "topic" | undefined;
    room?: Room;
    topics: Topic[];
    saving: boolean;
    error: MessageDescriptor | null;
    sessions?: SessionCandidate[];
    sessionsLoading?: boolean;
    sessionsError?: MessageDescriptor | null;
    roomId?: string;
    channelId?: string;
    topic?: Topic;
  }>();
  const emit = defineEmits<{
    close: [];
    createRoom: [request: CreateRoom];
    updateRoom: [request: UpdateRoom];
    createMember: [request: CreateMember];
    createTopic: [request: CreateTopic];
    updateTopic: [topicId: string, request: CreateTopic];
    reloadSessions: [];
  }>();

  const name = ref("");
  const sessionId = ref("");
  const unavailableOpen = ref(false);
  const workspacePath = ref(props.room?.rawWorkspacePath ?? "");
  const description = ref("");
  const topicIds = ref<string[]>([]);
  const topicSaving = ref(false);
  const errors = ref<Record<string, MessageDescriptor>>({});
  const sortedSessions = computed(() =>
    (props.sessions ?? []).toSorted((left, right) => right.id.localeCompare(left.id)),
  );
  const availableSessions = computed(() =>
    sortedSessions.value.filter((session) => session.usable && !session.memberId),
  );
  const unavailableSessions = computed(() =>
    sortedSessions.value.filter((session) => !session.usable && !session.memberId),
  );
  const { t, te } = useI18n();
  const title = computed(() =>
    props.mode === "room"
      ? props.room
        ? t("setup.editRoom")
        : t("setup.createRoom")
      : props.mode === "member"
        ? t("sidebar.addMember")
        : props.topic
          ? t("setup.editTopic")
          : t("sidebar.newTopic"),
  );
  const nameLabel = computed(() =>
    t(
      props.mode === "room"
        ? "setup.roomName"
        : props.mode === "member"
          ? "forms.memberName"
          : "setup.topicName",
    ),
  );

  function sessionStatus(session: SessionCandidate): string {
    if (session.archived) return t("session.archived");
    if (!session.usable) {
      if (session.unavailableReasonCode === "session_not_connected")
        return t("session.notConnected");
      if (session.unavailableReasonCode === "session_error") return t("session.error");
      return t("session.unavailable");
    }
    return t(session.presence === "busy" ? "session.busy" : "session.idle");
  }

  function unavailableReason(session: SessionCandidate): string {
    const key = `session.${session.unavailableReasonCode}`;
    if (session.unavailableReasonCode && te(key)) return t(key);
    return t("session.unavailableReason");
  }

  watch([() => props.mode, () => props.topic?.id, () => props.roomId, () => props.room?.id], () => {
    name.value = props.room?.name ?? props.topic?.name ?? "";
    sessionId.value = "";
    unavailableOpen.value = false;
    workspacePath.value = props.room?.rawWorkspacePath ?? "";
    description.value = props.topic?.description ?? "";
    topicIds.value = [];
    errors.value = {};
  });

  watch(sessionId, (selected, previous) => {
    if (props.mode !== "member") return;
    const previousName = props.sessions?.find((session) => session.id === previous)?.name;
    if (!name.value || name.value === previousName)
      name.value =
        props.sessions?.find((session) => session.id === selected)?.name.slice(0, 80) ?? "";
    if (selected) delete errors.value.session;
  });
  watch(
    () => props.sessions,
    (sessions) => {
      if (
        sessionId.value &&
        !sessions?.some(
          (session) => session.id === sessionId.value && !session.memberId && session.usable,
        )
      )
        sessionId.value = "";
    },
  );
  watch(name, (value) => {
    if (value.trim()) delete errors.value.name;
  });
  watch(workspacePath, (value) => {
    if (value.trim()) delete errors.value.workspacePath;
  });

  function submit(): void {
    if (props.saving || topicSaving.value) return;
    if (props.mode === "member" && (props.sessionsLoading || props.sessionsError)) return;
    errors.value = {};
    if (!name.value.trim()) errors.value.name = { key: "validation.name" };
    if (props.mode === "room") {
      if (!workspacePath.value.trim()) errors.value.workspacePath = { key: "validation.path" };
      else if (!/^([a-zA-Z]:[\\/]|\/|\\\\)/.test(workspacePath.value.trim()))
        errors.value.workspacePath = { key: "validation.absolutePath" };
    }
    if (props.mode === "member") {
      if (
        !props.sessions?.some(
          (session) => session.id === sessionId.value && !session.memberId && session.usable,
        )
      )
        errors.value.session = { key: "validation.session" };
    }
    if (Object.keys(errors.value).length) return;
    if (props.mode === "room" && props.room)
      emit("updateRoom", { name: name.value.trim(), workspacePath: workspacePath.value });
    else if (props.mode === "room")
      emit("createRoom", { name: name.value.trim(), workspacePath: workspacePath.value });
    if (props.mode === "member") {
      const request = {
        name: name.value.trim(),
        topicIds: [...topicIds.value],
      };
      emit("createMember", { ...request, sessionId: sessionId.value });
    }
    if (props.mode === "topic") {
      const request = { name: name.value.trim(), description: description.value.trim() };
      if (props.topic) emit("updateTopic", props.topic.id, request);
      else emit("createTopic", request);
    }
  }
</script>
