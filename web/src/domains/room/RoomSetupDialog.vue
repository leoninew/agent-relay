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
                :aria-invalid="!!errors.session"
              >
                <span class="session-option-label">
                  <strong>{{ session.name }}</strong>
                  <span :title="session.id">{{ session.id }}</span>
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
          <p v-if="!sessions?.length" class="session-state">暂无可加入的会话</p>
        </template>
        <p v-if="errors.session" id="setup-session-error" class="field-error">
          {{ errors.session }}
        </p>
      </div>
      <div class="setup-field">
        <label for="setup-name">
          {{ mode === "room" ? "项目名称" : mode === "member" ? "成员名称" : "主题名称" }}
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
        <div class="setup-field">
          <label for="setup-role">角色 <span class="required-mark">*</span></label>
          <AppInput
            id="setup-role"
            v-model="role"
            maxlength="80"
            :disabled="saving"
            :invalid="!!errors.role"
            clear-label="清空角色"
            aria-describedby="setup-role-error"
            placeholder="输入新角色，或选择已有角色"
          />
          <p v-if="errors.role" id="setup-role-error" class="field-error">{{ errors.role }}</p>
          <div v-if="roles?.length" class="setup-roles" aria-label="已有角色">
            <button
              v-for="existingRole in roles"
              :key="existingRole"
              type="button"
              class="routing-choice"
              :class="{ 'is-selected': role === existingRole }"
              :aria-pressed="role === existingRole"
              :disabled="saving"
              @click="role = existingRole"
            >
              {{ existingRole }}
            </button>
          </div>
        </div>
        <fieldset
          class="setup-field"
          :disabled="saving"
          :aria-invalid="!!errors.topics"
          aria-describedby="setup-topics-error"
        >
          <legend>关注主题 <span class="required-mark">*</span></legend>
          <AppCheckboxGroup
            v-model="topicIds"
            class="setup-topics"
            aria-label="关注主题"
            clear-label="清空关注主题"
            :disabled="saving"
            :invalid="!!errors.topics"
            described-by="setup-topics-error"
          >
            <AppCheckbox
              v-for="topic in topics"
              :key="topic.id"
              class="routing-choice"
              :value="topic.id"
            >
              <span># {{ topic.name }}</span>
            </AppCheckbox>
          </AppCheckboxGroup>
          <p v-if="errors.topics" id="setup-topics-error" class="field-error">
            {{ errors.topics }}
          </p>
          <div class="inline-topic-create">
            <label for="setup-new-topic" class="sr-only">新主题名称</label>
            <AppInput
              id="setup-new-topic"
              v-model="newTopicName"
              maxlength="40"
              placeholder="新主题名称"
              :disabled="saving || topicSaving"
              :invalid="!!topicNameError"
              clear-label="清空新主题名称"
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
              添加主题
            </AppButton>
          </div>
          <p v-if="topicNameError" id="setup-new-topic-error" class="field-error">
            {{ topicNameError }}
          </p>
          <p v-if="topicRequestError" class="field-error" role="alert">{{ topicRequestError }}</p>
        </fieldset>
      </template>
      <div v-if="mode === 'topic'" class="setup-field">
        <label for="setup-description">主题说明</label>
        <AppInput
          id="setup-description"
          v-model="description"
          maxlength="300"
          :disabled="saving"
          clear-label="清空主题说明"
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
          :disabled="topicSaving || sessionsLoading"
        >
          {{ member ? "保存成员" : title }}
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
    Session,
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
    sessions?: Session[];
    sessionsLoading?: boolean;
    roomId?: string;
    member?: Member;
    roles?: string[];
  }>();
  const emit = defineEmits<{
    close: [];
    createRoom: [request: CreateRoom];
    createMember: [request: CreateMember];
    updateMember: [memberId: string, request: UpdateMember];
    createTopic: [request: CreateTopic];
    reloadSessions: [];
  }>();

  const name = ref("");
  const roomsStore = useRoomsStore();
  const toasts = useToastsStore();
  const sessionId = ref("");
  const sessionChoices = ref<InstanceType<typeof RadioGroupRoot>>();
  const projectPath = ref("");
  const role = ref("");
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
        : "新建主题",
  );

  watch([() => props.mode, () => props.member?.id], () => {
    name.value = props.member?.name ?? "";
    sessionId.value = props.member?.sessionId ?? "";
    projectPath.value = "";
    role.value = props.member?.role ?? "";
    description.value = "";
    topicIds.value = [...(props.member?.topicIds ?? [])];
    newTopicName.value = "";
    topicNameError.value = "";
    topicRequestError.value = "";
    errors.value = {};
  });

  watch(sessionId, (selected, previous) => {
    const previousName = props.sessions?.find((session) => session.id === previous)?.name;
    if (!name.value || name.value === previousName)
      name.value = props.sessions?.find((session) => session.id === selected)?.name ?? "";
    if (selected) delete errors.value.session;
  });
  watch(name, (value) => {
    if (value.trim()) delete errors.value.name;
  });
  watch(projectPath, (value) => {
    if (value.trim()) delete errors.value.projectPath;
  });
  watch(role, (value) => {
    if (value.trim()) delete errors.value.role;
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
      topicNameError.value = "请输入主题名称";
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
      toasts.success("主题已创建");
      if (props.roomId === roomId && props.mode === "member") {
        topicIds.value = [...topicIds.value, topic.id];
        newTopicName.value = "";
      }
    } catch (caught) {
      topicRequestError.value = describeApiError(caught, "主题添加失败，请重试。");
      toasts.error(topicRequestError.value);
    } finally {
      topicSaving.value = false;
    }
  }

  function submit(): void {
    if (props.saving || topicSaving.value || props.sessionsLoading) return;
    errors.value = {};
    if (!name.value.trim()) errors.value.name = "请输入名称";
    if (props.mode === "room") {
      if (!projectPath.value.trim()) errors.value.projectPath = "请输入项目路径";
      else if (!/^([a-zA-Z]:[\\/]|\/|\\\\)/.test(projectPath.value.trim()))
        errors.value.projectPath = "请输入项目的绝对路径";
    }
    if (props.mode === "member") {
      if (!sessionId.value) errors.value.session = "请选择要加入的会话";
      if (!role.value.trim()) errors.value.role = "请输入角色";
      if (!topicIds.value.length) errors.value.topics = "请至少选择一个关注主题";
    }
    if (Object.keys(errors.value).length) return;
    if (props.mode === "room")
      emit("createRoom", { name: name.value.trim(), projectPath: projectPath.value.trim() });
    if (props.mode === "member") {
      const request = {
        name: name.value.trim(),
        role: role.value.trim(),
        topicIds: [...topicIds.value],
      };
      if (props.member) emit("updateMember", props.member.id, request);
      else emit("createMember", { ...request, sessionId: sessionId.value });
    }
    if (props.mode === "topic")
      emit("createTopic", { name: name.value.trim(), description: description.value.trim() });
  }
</script>
