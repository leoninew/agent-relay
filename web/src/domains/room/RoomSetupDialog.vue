<template>
  <AppDialog
    :open="mode !== undefined"
    :title="title"
    :busy="saving || topicSaving"
    @close="$emit('close')"
  >
    <form class="setup-form" novalidate @submit.prevent="submit">
      <div class="setup-form-content">
        <div v-if="mode === 'member'" class="setup-field">
          <div class="setup-field-heading">
            <label id="setup-session-label"
              >{{ t("setup.selectSession") }} <span class="required-mark">*</span></label
            >
            <AppButton
              variant="plain"
              class="session-reload"
              :loading="sessionsLoading"
              :loading-label="t('setup.refreshing')"
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
              ref="sessionChoices"
              v-model="sessionId"
              class="grid gap-3 rounded-lg border border-transparent p-0.5 aria-[invalid=true]:border-destructive"
              :disabled="saving"
              aria-labelledby="setup-session-label"
              :aria-invalid="!!errors.session"
              aria-describedby="setup-session-error"
            >
              <template v-if="availableSessions.length">
                <p class="text-xs text-muted-foreground">
                  {{ t("setup.availableSessions") }}
                  <span class="ml-1 tabular-nums">{{ availableSessions.length }}</span>
                </p>
                <div class="grid max-h-64 gap-2 overflow-y-auto rounded-lg p-0.5">
                  <div v-for="session in availableSessions" :key="session.id" class="relative">
                    <RadioGroupItem
                      :value="session.id"
                      class="group flex w-full items-start gap-3 rounded-lg border border-border bg-card p-3 text-start outline-none transition-colors hover:bg-muted/50 focus-visible:bg-muted disabled:opacity-60 data-[state=checked]:border-input data-[state=checked]:bg-primary/5 motion-reduce:transition-none"
                      :aria-invalid="!!errors.session"
                    >
                      <span
                        class="mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full border border-input group-data-[state=checked]:border-primary group-data-[state=checked]:bg-primary"
                      >
                        <RadioGroupIndicator class="flex">
                          <AppIcon name="check" class="size-3 text-primary-foreground" />
                        </RadioGroupIndicator>
                      </span>
                      <span class="grid min-w-0 flex-1 gap-1">
                        <span class="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
                          <span class="min-w-0 flex-1 truncate font-medium" :title="session.name">
                            {{ session.name }}
                          </span>
                          <span class="shrink-0 text-xs text-muted-foreground">
                            {{ sessionStatus(session) }}
                          </span>
                        </span>
                        <span
                          class="truncate pr-7 text-xs text-muted-foreground"
                          :title="session.id"
                        >
                          {{ session.id }}
                        </span>
                      </span>
                    </RadioGroupItem>
                    <AppClearButton
                      v-if="sessionId === session.id"
                      class="absolute right-2 bottom-2"
                      :label="t('setup.clearSession')"
                      :disabled="saving"
                      @clear="clearSession"
                    />
                  </div>
                </div>
              </template>
              <div
                v-else
                class="rounded-lg border border-dashed border-border bg-muted/30 px-4 py-5 text-center"
              >
                <p class="text-muted-foreground">
                  {{ t(sessions?.length ? "setup.noAvailable" : "setup.noSessions") }}
                </p>
                <p class="mt-1 text-xs text-muted-foreground">
                  {{ t(sessions?.length ? "setup.checkUnavailable" : "setup.openSession") }}
                </p>
              </div>
              <CollapsibleRoot
                v-if="unavailableSessions.length"
                v-model:open="unavailableOpen"
                :disabled="saving"
                class="border-t border-border pt-2"
              >
                <CollapsibleTrigger
                  class="group flex w-full items-center gap-2 rounded-md px-2 py-2 text-start text-xs text-muted-foreground hover:bg-muted/50 focus-visible:bg-muted"
                >
                  <AppIcon
                    name="chevron"
                    class="size-3.5 shrink-0 transition-transform group-data-[state=open]:rotate-90 motion-reduce:transition-none"
                  />
                  <span>{{ t("setup.unavailableSessions") }}</span>
                  <span class="ml-auto rounded bg-muted px-1.5 py-0.5 tabular-nums">
                    {{ unavailableSessions.length }}
                  </span>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <ul
                    :aria-label="t('setup.unavailableSessions')"
                    class="mt-2 grid max-h-48 gap-2 overflow-y-auto rounded-lg"
                  >
                    <li
                      v-for="session in unavailableSessions"
                      :key="session.id"
                      class="grid min-w-0 gap-1 rounded-md bg-muted/40 p-3 text-muted-foreground"
                    >
                      <div class="flex min-w-0 items-center gap-3">
                        <span class="min-w-0 flex-1 truncate font-medium" :title="session.name">
                          {{ session.name }}
                        </span>
                        <AppTooltip
                          v-if="!session.memberId && !session.archived && !session.usable"
                          :text="unavailableReason(session)"
                        >
                          <button
                            type="button"
                            class="shrink-0 cursor-help rounded-sm text-xs underline decoration-dotted underline-offset-2 focus-visible:outline-1 focus-visible:outline-dashed focus-visible:outline-muted-foreground"
                          >
                            {{ sessionStatus(session) }}
                          </button>
                        </AppTooltip>
                        <span v-else class="shrink-0 text-xs">{{ sessionStatus(session) }}</span>
                      </div>
                      <span class="truncate text-xs" :title="session.id">{{ session.id }}</span>
                      <p
                        v-if="session.memberId || session.archived || session.usable"
                        class="text-xs break-words"
                      >
                        {{ unavailableReason(session) }}
                      </p>
                    </li>
                  </ul>
                </CollapsibleContent>
              </CollapsibleRoot>
            </RadioGroupRoot>
          </template>
          <p v-if="errors.session" id="setup-session-error" class="field-error">
            {{ translateMessage(errors.session) }}
          </p>
        </div>
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
        <div v-if="mode === 'room' && !room" class="setup-field">
          <label for="setup-path"
            >{{ t("setup.projectPath") }} <span class="required-mark">*</span></label
          >
          <AppInput
            id="setup-path"
            v-model="projectPath"
            maxlength="500"
            :disabled="saving"
            :invalid="!!errors.projectPath"
            :clear-label="t('setup.clearPath')"
            aria-describedby="setup-path-error"
            placeholder=""
            autocomplete="off"
          />
          <p v-if="errors.projectPath" id="setup-path-error" class="field-error">
            {{ translateMessage(errors.projectPath) }}
          </p>
        </div>
        <MemberTopicsField
          v-if="mode === 'member'"
          v-model="topicIds"
          v-model:busy="topicSaving"
          id-prefix="setup-member"
          :topics="topics"
          :room-id="roomId"
          :disabled="saving"
        />
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
    RadioGroupIndicator,
    RadioGroupItem,
    RadioGroupRoot,
  } from "reka-ui";
  import { computed, nextTick, ref, watch } from "vue";

  import AppButton from "@/components/AppButton.vue";
  import AppClearButton from "@/components/AppClearButton.vue";
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
  const sessionChoices = ref<InstanceType<typeof RadioGroupRoot>>();
  const unavailableOpen = ref(false);
  const projectPath = ref("");
  const description = ref("");
  const topicIds = ref<string[]>([]);
  const topicSaving = ref(false);
  const errors = ref<Record<string, MessageDescriptor>>({});
  const availableSessions = computed(() =>
    (props.sessions ?? []).filter((session) => session.usable && !session.memberId),
  );
  const unavailableSessions = computed(() =>
    (props.sessions ?? []).filter((session) => !session.usable || session.memberId),
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
        ? "setup.projectName"
        : props.mode === "member"
          ? "forms.memberName"
          : "setup.topicName",
    ),
  );

  function sessionStatus(session: SessionCandidate): string {
    if (session.memberId) return t("session.joined");
    if (session.archived) return t("session.archived");
    if (!session.usable) return t("session.unavailable");
    return t(session.presence === "busy" ? "session.busy" : "session.idle");
  }

  function unavailableReason(session: SessionCandidate): string {
    const key = `session.${session.unavailableReasonCode}`;
    if (session.unavailableReasonCode && te(key)) return t(key);
    return t(session.memberId ? "session.joinedReason" : "session.unavailableReason");
  }

  watch([() => props.mode, () => props.topic?.id, () => props.roomId, () => props.room?.id], () => {
    name.value = props.room?.name ?? props.topic?.name ?? "";
    sessionId.value = "";
    unavailableOpen.value = false;
    projectPath.value = "";
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
  watch(projectPath, (value) => {
    if (value.trim()) delete errors.value.projectPath;
  });

  async function clearSession(): Promise<void> {
    const element = sessionChoices.value?.$el as HTMLElement | undefined;
    const selected = element?.querySelector<HTMLButtonElement>(
      '[role="radio"][data-state="checked"]',
    );
    sessionId.value = "";
    await nextTick();
    selected?.focus();
  }

  function submit(): void {
    if (props.saving || topicSaving.value) return;
    if (props.mode === "member" && (props.sessionsLoading || props.sessionsError)) return;
    errors.value = {};
    if (!name.value.trim()) errors.value.name = { key: "validation.name" };
    if (props.mode === "room" && !props.room) {
      if (!projectPath.value.trim()) errors.value.projectPath = { key: "validation.path" };
      else if (!/^([a-zA-Z]:[\\/]|\/|\\\\)/.test(projectPath.value.trim()))
        errors.value.projectPath = { key: "validation.absolutePath" };
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
    if (props.mode === "room" && props.room) emit("updateRoom", { name: name.value.trim() });
    else if (props.mode === "room")
      emit("createRoom", { name: name.value.trim(), projectPath: projectPath.value.trim() });
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
