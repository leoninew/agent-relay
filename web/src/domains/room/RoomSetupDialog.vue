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
            <label id="setup-session-label">选择会话 <span class="required-mark">*</span></label>
            <AppButton
              variant="plain"
              class="session-reload"
              :loading="sessionsLoading"
              loading-label="刷新中…"
              :disabled="saving || topicSaving"
              @click="$emit('reloadSessions')"
            >
              刷新会话
            </AppButton>
          </div>
          <AppLoading v-if="sessionsLoading" class="session-state">正在加载会话…</AppLoading>
          <p v-else-if="sessionsError" class="field-error" role="alert">{{ sessionsError }}</p>
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
                  可加入会话 <span class="ml-1 tabular-nums">{{ availableSessions.length }}</span>
                </p>
                <div class="grid max-h-64 gap-2 overflow-y-auto rounded-lg p-0.5">
                  <div v-for="session in availableSessions" :key="session.id" class="relative">
                    <RadioGroupItem
                      :value="session.id"
                      class="group flex w-full items-start gap-3 rounded-lg border border-border bg-card p-3 text-start outline-none transition-colors hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset disabled:opacity-60 data-[state=checked]:border-primary/60 data-[state=checked]:bg-primary/5 motion-reduce:transition-none"
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
                      label="清空所选会话"
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
                  {{ sessions?.length ? "暂无可加入的会话" : "当前项目目录下暂无 Codex 会话" }}
                </p>
                <p class="mt-1 text-xs text-muted-foreground">
                  {{
                    sessions?.length
                      ? "可刷新会话，或展开下方列表查看原因。"
                      : "打开此项目的 Codex 会话后刷新列表。"
                  }}
                </p>
              </div>
              <CollapsibleRoot
                v-if="unavailableSessions.length"
                v-model:open="unavailableOpen"
                :disabled="saving"
                class="border-t border-border pt-2"
              >
                <CollapsibleTrigger
                  class="group flex w-full items-center gap-2 rounded-md px-2 py-2 text-start text-xs text-muted-foreground hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
                >
                  <AppIcon
                    name="chevron"
                    class="size-3.5 shrink-0 transition-transform group-data-[state=open]:rotate-90 motion-reduce:transition-none"
                  />
                  <span>不可用会话</span>
                  <span class="ml-auto rounded bg-muted px-1.5 py-0.5 tabular-nums">
                    {{ unavailableSessions.length }}
                  </span>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <ul
                    aria-label="不可用会话"
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
                          v-if="sessionStatus(session) === '不可用'"
                          :text="unavailableReason(session)"
                        >
                          <button
                            type="button"
                            class="shrink-0 cursor-help rounded-sm text-xs underline decoration-dotted underline-offset-2 focus-visible:outline-2 focus-visible:outline-ring"
                          >
                            {{ sessionStatus(session) }}
                          </button>
                        </AppTooltip>
                        <span v-else class="shrink-0 text-xs">{{ sessionStatus(session) }}</span>
                      </div>
                      <span class="truncate text-xs" :title="session.id">{{ session.id }}</span>
                      <p v-if="sessionStatus(session) !== '不可用'" class="text-xs break-words">
                        {{ unavailableReason(session) }}
                      </p>
                    </li>
                  </ul>
                </CollapsibleContent>
              </CollapsibleRoot>
            </RadioGroupRoot>
          </template>
          <p v-if="errors.session" id="setup-session-error" class="field-error">
            {{ errors.session }}
          </p>
        </div>
        <div class="setup-field">
          <label for="setup-name">
            {{ mode === "room" ? "项目名称" : mode === "member" ? "成员名称" : "话题名称" }}
            <span class="required-mark">*</span>
          </label>
          <AppInput
            id="setup-name"
            v-model="name"
            :maxlength="mode === 'topic' ? 40 : 80"
            :disabled="saving"
            :invalid="!!errors.name"
            clear-label="清空名称"
            aria-describedby="setup-name-error"
            autocomplete="off"
          />
          <p v-if="errors.name" id="setup-name-error" class="field-error">{{ errors.name }}</p>
        </div>
        <div v-if="mode === 'room'" class="setup-field">
          <label for="setup-path">项目路径 <span class="required-mark">*</span></label>
          <AppInput
            id="setup-path"
            v-model="projectPath"
            maxlength="500"
            :disabled="saving"
            :invalid="!!errors.projectPath"
            clear-label="清空项目路径"
            aria-describedby="setup-path-error"
            placeholder=""
            autocomplete="off"
          />
          <p v-if="errors.projectPath" id="setup-path-error" class="field-error">
            {{ errors.projectPath }}
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
          <label for="setup-description">话题说明</label>
          <AppInput
            id="setup-description"
            v-model="description"
            maxlength="300"
            :disabled="saving"
            clear-label="清空话题说明"
          />
        </div>
        <p v-if="error" class="field-error" role="alert">{{ error }}</p>
      </div>
      <footer class="dialog-actions">
        <AppButton variant="secondary" :disabled="saving || topicSaving" @click="$emit('close')">
          取消
        </AppButton>
        <AppButton
          type="submit"
          :loading="saving"
          loading-label="保存中…"
          :disabled="topicSaving || (mode === 'member' && (sessionsLoading || !!sessionsError))"
        >
          {{ topic ? "保存话题" : title }}
        </AppButton>
      </footer>
    </form>
  </AppDialog>
</template>

<script setup lang="ts">
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
    Topic,
  } from "@/services/roomApi";

  import "./member-session.css";

  const props = defineProps<{
    mode: "room" | "member" | "topic" | undefined;
    topics: Topic[];
    saving: boolean;
    error: string | null;
    sessions?: SessionCandidate[];
    sessionsLoading?: boolean;
    sessionsError?: string | null;
    roomId?: string;
    topic?: Topic;
  }>();
  const emit = defineEmits<{
    close: [];
    createRoom: [request: CreateRoom];
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
  const errors = ref<Record<string, string>>({});
  const availableSessions = computed(() =>
    (props.sessions ?? []).filter((session) => session.usable && !session.memberId),
  );
  const unavailableSessions = computed(() =>
    (props.sessions ?? []).filter((session) => !session.usable || session.memberId),
  );
  const title = computed(() =>
    props.mode === "room"
      ? "新建聊天室"
      : props.mode === "member"
        ? "添加成员"
        : props.topic
          ? "编辑话题"
          : "新建话题",
  );

  function sessionStatus(session: SessionCandidate): string {
    if (session.memberId) return "已加入";
    if (session.archived) return "已归档";
    if (!session.usable) return "不可用";
    return session.presence === "busy" ? "忙碌" : "空闲";
  }

  function unavailableReason(session: SessionCandidate): string {
    if (session.unavailableReason) return session.unavailableReason;
    return session.memberId ? "此会话已加入当前聊天室。" : "此会话暂不可加入，请刷新后重试。";
  }

  watch([() => props.mode, () => props.topic?.id, () => props.roomId], () => {
    name.value = props.topic?.name ?? "";
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
    if (!name.value.trim()) errors.value.name = "请输入名称";
    if (props.mode === "room") {
      if (!projectPath.value.trim()) errors.value.projectPath = "请输入项目路径";
      else if (!/^([a-zA-Z]:[\\/]|\/|\\\\)/.test(projectPath.value.trim()))
        errors.value.projectPath = "请输入项目的绝对路径";
    }
    if (props.mode === "member") {
      if (
        !props.sessions?.some(
          (session) => session.id === sessionId.value && !session.memberId && session.usable,
        )
      )
        errors.value.session = "请选择要加入的会话";
    }
    if (Object.keys(errors.value).length) return;
    if (props.mode === "room")
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
