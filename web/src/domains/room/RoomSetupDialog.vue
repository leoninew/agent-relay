<template>
  <AppDialog
    :open="mode !== undefined"
    :title="title"
    :busy="saving || topicSaving"
    @close="$emit('close')"
  >
    <form class="setup-form" novalidate @submit.prevent="submit">
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
            class="session-options"
            :disabled="saving"
            aria-labelledby="setup-session-label"
            :aria-invalid="!!errors.session"
            aria-describedby="setup-session-error"
          >
            <div v-for="session in sessions" :key="session.id" class="session-option-row">
              <RadioGroupItem
                :value="session.id"
                class="session-option"
                :disabled="!!session.memberId || !session.usable"
                :aria-invalid="!!errors.session"
              >
                <span class="session-option-label">
                  <strong :title="session.name">{{ session.name }}</strong>
                  <span :title="session.id">{{ session.id }}</span>
                </span>
              </RadioGroupItem>
              <span class="session-option-meta">
                <AppTooltip
                  v-if="!session.usable && session.unavailableReason"
                  :text="session.unavailableReason"
                >
                  <button
                    type="button"
                    class="session-option-help"
                    :aria-label="`${session.name}不可用：${session.unavailableReason}`"
                  >
                    {{ sessionStatus(session) }}<AppIcon name="info" />
                  </button>
                </AppTooltip>
                <span v-else>{{ sessionStatus(session) }}</span>
                <AppClearButton
                  v-if="sessionId === session.id"
                  label="清空所选会话"
                  :disabled="saving"
                  @clear="clearSession"
                />
              </span>
            </div>
          </RadioGroupRoot>
          <p v-if="!sessions?.length" class="session-state">当前项目目录下暂无 Codex 会话</p>
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
          placeholder="D:/SourceCodes/mywork/project"
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
        :error="errors.topics"
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
  import { RadioGroupItem, RadioGroupRoot } from "reka-ui";
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
  const projectPath = ref("");
  const description = ref("");
  const topicIds = ref<string[]>([]);
  const topicSaving = ref(false);
  const errors = ref<Record<string, string>>({});
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
    return session.presence === "busy" ? "忙碌，可排队" : "可用";
  }

  watch([() => props.mode, () => props.topic?.id, () => props.roomId], () => {
    name.value = props.topic?.name ?? "";
    sessionId.value = "";
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
  watch(topicIds, (value) => {
    if (value.length) delete errors.value.topics;
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
      if (!topicIds.value.length) errors.value.topics = "请至少选择一个订阅话题";
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

<style scoped>
  .session-option-help {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 0;
    border: 0;
    border-radius: 4px;
    color: inherit;
    font: inherit;
    background: transparent;
    cursor: help;
  }

  .session-option-help:hover,
  .session-option-help:focus-visible {
    color: hsl(var(--foreground));
  }

  .session-option-help svg {
    width: 14px;
    height: 14px;
  }
</style>
