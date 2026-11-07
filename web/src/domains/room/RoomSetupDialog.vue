<template>
  <AppDialog
    :open="mode !== undefined"
    :title="title"
    :busy="saving || topicSaving"
    @close="$emit('close')"
  >
    <form class="setup-form" novalidate @submit.prevent="submit">
      <div v-if="mode === 'member' && member" class="setup-field">
        <label>关联会话</label>
        <p v-if="linkedSession" class="session-state">{{ linkedSession.name }}</p>
        <p v-else class="session-state">会话名称不可用</p>
        <p class="session-state session-id">{{ member.sessionId }}</p>
      </div>
      <div v-else-if="mode === 'member'" class="setup-field">
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
                :disabled="!!session.memberId"
                :aria-invalid="!!errors.session"
              >
                <span class="session-option-label">
                  <strong>{{ session.name }}</strong>
                  <span>
                    {{ session.id }}
                    <template v-if="session.archived"> · 已归档</template>
                    <template v-if="session.memberId"> · 已加入</template>
                  </span>
                </span>
                <span class="session-option-check" aria-hidden="true"></span>
              </RadioGroupItem>
              <AppClearButton
                v-if="sessionId === session.id"
                label="清空所选会话"
                :disabled="saving"
                @clear="clearSession"
              />
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
      <template v-if="mode === 'member'">
        <fieldset
          class="setup-field"
          :disabled="saving"
          :aria-invalid="!!errors.topics"
          aria-describedby="setup-topics-error"
        >
          <legend>订阅话题 <span class="required-mark">*</span></legend>
          <AppCheckboxGroup
            v-model="topicIds"
            class="setup-topics"
            aria-label="订阅话题"
            clear-label="清空订阅话题"
            :disabled="saving"
            :invalid="!!errors.topics"
            described-by="setup-topics-error"
          >
            <AppCheckbox
              v-for="subscription in topics"
              :key="subscription.id"
              class="routing-choice"
              :value="subscription.id"
            >
              <span># {{ subscription.name }}</span>
            </AppCheckbox>
          </AppCheckboxGroup>
          <p v-if="errors.topics" id="setup-topics-error" class="field-error">
            {{ errors.topics }}
          </p>
          <div class="inline-topic-create">
            <label for="setup-new-topic" class="sr-only">新话题名称</label>
            <AppInput
              id="setup-new-topic"
              v-model="newTopicName"
              maxlength="40"
              placeholder="新话题名称"
              :disabled="saving || topicSaving"
              :invalid="!!topicNameError"
              clear-label="清空新话题名称"
              :aria-describedby="topicNameError ? 'setup-new-topic-error' : undefined"
              @keydown.enter.prevent="createInlineTopic"
            />
            <AppButton
              variant="secondary"
              :loading="topicSaving"
              loading-label="添加中…"
              :disabled="saving"
              @click="createInlineTopic"
            >
              添加话题
            </AppButton>
          </div>
          <p v-if="topicNameError" id="setup-new-topic-error" class="field-error">
            {{ topicNameError }}
          </p>
          <p v-if="topicRequestError" class="field-error" role="alert">{{ topicRequestError }}</p>
        </fieldset>
      </template>
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
          :disabled="
            topicSaving || (!member && mode === 'member' && (sessionsLoading || !!sessionsError))
          "
        >
          {{ member ? "保存成员" : topic ? "保存话题" : title }}
        </AppButton>
      </footer>
    </form>
  </AppDialog>
</template>

<script setup lang="ts">
  import { RadioGroupItem, RadioGroupRoot } from "reka-ui";
  import { computed, nextTick, ref, watch } from "vue";

  import AppButton from "@/components/AppButton.vue";
  import AppCheckbox from "@/components/AppCheckbox.vue";
  import AppCheckboxGroup from "@/components/AppCheckboxGroup.vue";
  import AppClearButton from "@/components/AppClearButton.vue";
  import AppDialog from "@/components/AppDialog.vue";
  import AppInput from "@/components/AppInput.vue";
  import AppLoading from "@/components/AppLoading.vue";
  import { describeApiError } from "@/services/api";
  import type {
    CreateMember,
    CreateRoom,
    CreateTopic,
    Member,
    SessionCandidate,
    Topic,
    UpdateMember,
  } from "@/services/roomApi";
  import { useRoomsStore } from "@/stores/rooms";
  import { useToastsStore } from "@/stores/toasts";

  const props = defineProps<{
    mode: "room" | "member" | "topic" | undefined;
    topics: Topic[];
    saving: boolean;
    error: string | null;
    sessions?: SessionCandidate[];
    sessionsLoading?: boolean;
    sessionsError?: string | null;
    linkedSession?: { id: string; name: string };
    roomId?: string;
    member?: Member;
    topic?: Topic;
  }>();
  const emit = defineEmits<{
    close: [];
    createRoom: [request: CreateRoom];
    createMember: [request: CreateMember];
    updateMember: [memberId: string, request: UpdateMember];
    createTopic: [request: CreateTopic];
    updateTopic: [topicId: string, request: CreateTopic];
    reloadSessions: [];
  }>();

  const name = ref("");
  const roomsStore = useRoomsStore();
  const toasts = useToastsStore();
  const sessionId = ref("");
  const sessionChoices = ref<InstanceType<typeof RadioGroupRoot>>();
  const projectPath = ref("");
  const description = ref("");
  const topicIds = ref<string[]>([]);
  const newTopicName = ref("");
  const topicSaving = ref(false);
  const topicNameError = ref("");
  const topicRequestError = ref("");
  const errors = ref<Record<string, string>>({});
  const title = computed(() =>
    props.mode === "room"
      ? "新建聊天室"
      : props.mode === "member"
        ? props.member
          ? "编辑成员"
          : "添加成员"
        : props.topic
          ? "编辑话题"
          : "新建话题",
  );

  watch(
    [() => props.mode, () => props.member?.id, () => props.topic?.id, () => props.roomId],
    () => {
      name.value = props.member?.name ?? props.topic?.name ?? "";
      sessionId.value = props.member?.sessionId ?? "";
      projectPath.value = "";
      description.value = props.topic?.description ?? "";
      topicIds.value = [...(props.member?.topicIds ?? [])];
      newTopicName.value = "";
      topicNameError.value = "";
      topicRequestError.value = "";
      errors.value = {};
    },
  );

  watch(sessionId, (selected, previous) => {
    if (props.member || props.mode !== "member") return;
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
        !props.member &&
        sessionId.value &&
        !sessions?.some((session) => session.id === sessionId.value && !session.memberId)
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
  watch(newTopicName, () => {
    topicNameError.value = "";
    topicRequestError.value = "";
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

  async function createInlineTopic(): Promise<void> {
    if (props.saving || topicSaving.value || !props.roomId) return;
    const topicName = newTopicName.value.trim();
    topicNameError.value = "";
    topicRequestError.value = "";
    if (!topicName) {
      topicNameError.value = "请输入话题名称";
      return;
    }
    const existing = props.topics.find((topic) => topic.name === topicName);
    if (existing) {
      if (!topicIds.value.includes(existing.id)) topicIds.value = [...topicIds.value, existing.id];
      newTopicName.value = "";
      return;
    }
    const roomId = props.roomId;
    topicSaving.value = true;
    try {
      const topic = await roomsStore.createTopic(roomId, { name: topicName, description: "" });
      toasts.success("话题已创建");
      if (props.roomId === roomId && props.mode === "member") {
        topicIds.value = [...topicIds.value, topic.id];
        newTopicName.value = "";
      }
    } catch (caught) {
      topicRequestError.value = describeApiError(caught, "话题添加失败，请重试。");
      toasts.error(topicRequestError.value);
    } finally {
      topicSaving.value = false;
    }
  }

  function submit(): void {
    if (props.saving || topicSaving.value) return;
    if (props.mode === "member" && !props.member && (props.sessionsLoading || props.sessionsError))
      return;
    errors.value = {};
    if (!name.value.trim()) errors.value.name = "请输入名称";
    if (props.mode === "room") {
      if (!projectPath.value.trim()) errors.value.projectPath = "请输入项目路径";
      else if (!/^([a-zA-Z]:[\\/]|\/|\\\\)/.test(projectPath.value.trim()))
        errors.value.projectPath = "请输入项目的绝对路径";
    }
    if (props.mode === "member") {
      if (
        !props.member &&
        !props.sessions?.some((session) => session.id === sessionId.value && !session.memberId)
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
      if (props.member) emit("updateMember", props.member.id, request);
      else emit("createMember", { ...request, sessionId: sessionId.value });
    }
    if (props.mode === "topic") {
      const request = { name: name.value.trim(), description: description.value.trim() };
      if (props.topic) emit("updateTopic", props.topic.id, request);
      else emit("createTopic", request);
    }
  }
</script>
