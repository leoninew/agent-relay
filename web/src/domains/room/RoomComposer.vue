<template>
  <form class="room-composer" aria-label="发送消息" novalidate @submit.prevent="submit">
    <div v-if="replyTo" class="composer-reply">
      <AppIcon name="reply" />
      <span>
        回复 <strong>{{ replyToMember?.name ?? replyTo.senderId }}</strong> · {{ replyTo.content }}
      </span>
      <button type="button" class="icon-button" aria-label="取消引用" @click="$emit('cancelReply')">
        <AppIcon name="close" />
      </button>
    </div>
    <div class="composer-fields">
      <fieldset class="composer-routing" :disabled="sending || locked">
        <legend class="sr-only">消息路由</legend>
        <div class="routing-row">
          <span class="routing-label"> <AppIcon name="hash" />话题 </span>
          <AppCheckboxGroup
            v-model="topicIds"
            class="routing-options"
            aria-label="消息话题"
            clear-label="清空消息话题"
            :disabled="sending || locked"
            :invalid="showRecipientError"
            :described-by="showRecipientError ? 'routing-error' : undefined"
          >
            <AppCheckbox
              v-for="topic in topics"
              :key="topic.id"
              class="routing-choice"
              :data-topic="topic.id"
              :value="topic.id"
              :aria-label="`消息话题：${topic.name}`"
              :aria-invalid="showRecipientError"
              :aria-describedby="showRecipientError ? 'routing-error' : undefined"
            >
              <span># {{ topic.name }}</span>
            </AppCheckbox>
          </AppCheckboxGroup>
        </div>
        <div class="routing-row">
          <span class="routing-label"><AppIcon name="at" />成员</span>
          <AppCheckboxGroup
            v-model="mentionedMemberIds"
            class="routing-options"
            aria-label="@ 成员"
            clear-label="清空 @ 成员"
            :disabled="sending || locked"
            :invalid="showRecipientError"
            :described-by="showRecipientError ? 'routing-error' : undefined"
          >
            <AppCheckbox
              v-for="member in agentMembers"
              :key="member.id"
              class="recipient-choice"
              :value="member.id"
              :aria-label="`@ ${member.name}`"
              :aria-invalid="showRecipientError"
              :aria-describedby="showRecipientError ? 'routing-error' : undefined"
            >
              <MemberIdentity
                :member="member"
                :session-name="memberSessionName(member, members, sessions)"
                appearance="text"
              />
            </AppCheckbox>
          </AppCheckboxGroup>
        </div>
        <p
          v-if="showRecipientError"
          id="routing-error"
          class="field-error routing-error"
          role="alert"
          :title="routingError"
        >
          {{ routingError }}
        </p>
      </fieldset>
      <CapabilityTags
        :capabilities="draft.capabilities"
        removable
        :disabled="sending || locked"
        @remove="removeCapability"
      />
      <label for="message-content" class="sr-only">消息内容</label>
      <div class="composer-editor">
        <div class="capability-input">
          <AppInput
            id="message-content"
            ref="textarea"
            v-model="content"
            name="content"
            maxlength="6000"
            rows="2"
            placeholder="发送消息，输入 $ 选择 Skill…"
            clear-label="清空消息内容"
            multiline
            autoresize
            :disabled="sending || locked"
            :invalid="showContentError"
            aria-describedby="content-error"
            :role="pickerOpen ? 'combobox' : undefined"
            :aria-expanded="pickerOpen"
            :aria-controls="pickerOpen ? 'capability-options' : undefined"
            :aria-activedescendant="
              pickerOpen && options[activeIndex] ? `capability-${activeIndex}` : undefined
            "
            aria-autocomplete="list"
            @input="syncQuery"
            @click="syncQuery"
            @keyup="syncQuery"
            @select="syncQuery"
            @focus="syncQuery"
            @blur="query = undefined"
            @compositionstart="
              composing = true;
              query = undefined;
            "
            @compositionend="finishComposition"
            @keydown="onKeydown"
          />
          <div v-if="pickerOpen" class="capability-picker">
            <div class="capability-picker-heading">
              <span>选择 Skill</span>
              <button
                type="button"
                class="icon-button"
                aria-label="刷新 Skill 目录"
                :disabled="catalog?.skillsLoading"
                @mousedown.prevent
                @click="$emit('refreshCapabilities')"
              >
                <AppIcon name="refresh" />
              </button>
            </div>
            <div id="capability-options" role="listbox" aria-label="可用 Skill">
              <button
                v-for="option in options"
                :id="`capability-${option.index}`"
                :key="option.id"
                type="button"
                role="option"
                tabindex="-1"
                class="capability-option"
                :aria-selected="activeIndex === option.index"
                @mousedown.prevent
                @mouseenter="activeIndex = option.index"
                @click="selectCapability(option)"
              >
                <AppIcon name="skill" />
                <span>
                  <span class="capability-option-label">{{ option.label }}</span>
                  <span class="capability-option-description">{{ option.description }}</span>
                </span>
              </button>
            </div>
            <div class="capability-picker-status" role="status">
              <p v-if="catalog?.skillsLoading">正在加载 Skill…</p>
              <p v-if="!options.length && !catalog?.skillsLoading">未找到可选 Skill</p>
              <p v-for="issue in catalog?.issues" :key="issue">{{ issue }}</p>
            </div>
          </div>
        </div>
        <AppButton
          type="submit"
          class="composer-send-button"
          title="Enter 发送，Shift+Enter 换行"
          aria-keyshortcuts="Enter"
          :aria-label="sending ? '正在发送' : '发送消息'"
          :loading="sending"
          :disabled="locked"
          loading-label="发送中…"
        >
          <template #icon><AppIcon name="enter" /></template>
          发送
        </AppButton>
      </div>
      <p v-if="showContentError" id="content-error" class="field-error" role="alert">
        请输入消息内容
      </p>
      <p v-if="error" class="field-error send-error" role="alert">{{ error }}</p>
    </div>
  </form>
</template>

<script setup lang="ts">
  import { computed, nextTick, ref, watch } from "vue";

  import AppButton from "@/components/AppButton.vue";
  import AppCheckbox from "@/components/AppCheckbox.vue";
  import AppCheckboxGroup from "@/components/AppCheckboxGroup.vue";
  import AppIcon from "@/components/AppIcon.vue";
  import AppInput from "@/components/AppInput.vue";
  import MemberIdentity from "@/domains/room/MemberIdentity.vue";
  import CapabilityTags from "@/domains/room/CapabilityTags.vue";
  import type { ComposerCatalog } from "@/domains/room/useRoomCapabilities";
  import { memberSessionName } from "@/domains/room/memberSessionName";
  import type {
    CapabilityReference,
    MessageDraft,
    Member,
    RoomMessage,
    Session,
    SkillReference,
    Topic,
  } from "@/services/roomApi";

  const props = withDefaults(
    defineProps<{
      roomId: string;
      topics: Topic[];
      members: Member[];
      sessions: Session[];
      replyTo?: RoomMessage;
      sending: boolean;
      locked?: boolean;
      error: string | null;
      catalog?: ComposerCatalog;
    }>(),
    { replyTo: undefined, catalog: undefined },
  );
  const emit = defineEmits<{
    send: [message: MessageDraft];
    cancelReply: [];
    refreshCapabilities: [];
  }>();

  const draft = defineModel<MessageDraft>("draft", {
    default: () => ({ content: "", topicIds: [], mentionedMemberIds: [] }),
  });
  const content = computed({
    get: () => draft.value.content,
    set: (content) => {
      draft.value = { ...draft.value, content };
    },
  });
  const topicIds = computed({
    get: () => draft.value.topicIds,
    set: (topicIds) => {
      draft.value = { ...draft.value, topicIds };
    },
  });
  const mentionedMemberIds = computed({
    get: () => draft.value.mentionedMemberIds,
    set: (mentionedMemberIds) => {
      draft.value = { ...draft.value, mentionedMemberIds };
    },
  });
  const attempted = ref(false);
  const textarea = ref<InstanceType<typeof AppInput>>();
  const composing = ref(false);
  const query = ref<{ start: number; end: number; text: string }>();
  const activeIndex = ref(0);
  let dismissed: string | undefined;
  const pickerOpen = computed(() => Boolean(query.value && !props.sending && !props.locked));
  const options = computed(() => {
    const search = query.value?.text.toLocaleLowerCase() ?? "";
    return (props.catalog?.skills ?? [])
      .filter((skill) => skill.enabled)
      .map((skill) => ({
        type: skill.type,
        id: skill.id,
        name: skill.name,
        label: skill.displayName,
        description: `${skill.source}${skill.pluginId ? ` · ${skill.pluginId}` : ""} · ${skill.description}`,
      }))
      .filter(
        (option) =>
          `${option.name} ${option.label} ${option.description}`
            .toLocaleLowerCase()
            .includes(search) &&
          !(draft.value.capabilities ?? []).some(
            (reference) => reference.type === option.type && reference.id === option.id,
          ),
      )
      .map((option, index) => ({ ...option, index }));
  });
  watch(options, () => {
    activeIndex.value = 0;
  });
  watch(
    () => [props.roomId, props.sending, props.locked],
    () => {
      query.value = undefined;
    },
  );

  async function syncQuery(): Promise<void> {
    await nextTick();
    const range = textarea.value?.selection();
    if (
      composing.value ||
      props.sending ||
      props.locked ||
      !range ||
      range.start !== range.end ||
      dismissed === `${content.value}:${range.start}`
    ) {
      query.value = undefined;
      return;
    }
    const prefix = content.value
      .slice(0, range.start)
      .match(/(?:^|[\s(（])\$([\p{L}\p{N}_:./@-]*)$/u);
    if (!prefix) {
      query.value = undefined;
      return;
    }
    const suffix = content.value.slice(range.start).match(/^[\p{L}\p{N}_:./@-]*/u)?.[0] ?? "";
    const nextQuery = {
      start: range.start - prefix[1].length - 1,
      end: range.start + suffix.length,
      text: prefix[1],
    };
    if (JSON.stringify(nextQuery) !== JSON.stringify(query.value)) query.value = nextQuery;
  }

  function finishComposition(): void {
    composing.value = false;
    void syncQuery();
  }

  async function selectCapability(reference: SkillReference): Promise<void> {
    if (!query.value || props.sending || props.locked) return;
    const range = query.value;
    query.value = undefined;
    const currentDraft = draft.value;
    const capabilities = currentDraft.capabilities ?? [];
    draft.value = {
      ...currentDraft,
      content: currentDraft.content.slice(0, range.start) + currentDraft.content.slice(range.end),
      capabilities: capabilities.some(
        (item) => item.type === reference.type && item.id === reference.id,
      )
        ? capabilities
        : [...capabilities, { type: reference.type, id: reference.id, name: reference.name }],
    };
    await textarea.value?.setSelection(range.start);
  }

  function removeCapability(reference: CapabilityReference): void {
    if (props.sending || props.locked) return;
    draft.value = {
      ...draft.value,
      capabilities: draft.value.capabilities?.filter(
        (item) => item.type !== reference.type || item.id !== reference.id,
      ),
    };
  }
  const showContentError = computed(() => attempted.value && !content.value.trim());
  const replyToMember = computed(() =>
    props.members.find((member) => member.id === props.replyTo?.senderId),
  );
  const agentMembers = computed(() =>
    props.members.filter((member) => member.kind === "agent" && !member.deletedAt),
  );
  const recipients = computed(() =>
    agentMembers.value.filter(
      (member) =>
        mentionedMemberIds.value.includes(member.id) ||
        member.topicIds.some((topicId) => topicIds.value.includes(topicId)),
    ),
  );
  const showRecipientError = computed(() => attempted.value && recipients.value.length === 0);
  const routingError = computed(() =>
    topicIds.value.length || mentionedMemberIds.value.length
      ? "所选话题暂无成员，请选择其他话题或 @ 成员"
      : "请选择至少一个话题或 @ 一位成员",
  );

  watch(
    [() => props.topics, () => props.members],
    () => {
      draft.value = {
        ...draft.value,
        topicIds: topicIds.value.filter((id) => props.topics.some((topic) => topic.id === id)),
        mentionedMemberIds: mentionedMemberIds.value.filter((id) =>
          agentMembers.value.some((member) => member.id === id),
        ),
      };
    },
    { immediate: true },
  );

  function addTopic(topicId: string): void {
    if (props.sending || props.locked || topicIds.value.includes(topicId)) return;
    if (!props.topics.some((topic) => topic.id === topicId && !topic.deletedAt)) return;
    topicIds.value = [...topicIds.value, topicId];
  }

  function addMember(memberId: string): void {
    if (props.sending || props.locked || mentionedMemberIds.value.includes(memberId)) return;
    if (!agentMembers.value.some((member) => member.id === memberId)) return;
    mentionedMemberIds.value = [...mentionedMemberIds.value, memberId];
  }

  function selectTopic(topicId?: string): void {
    if (props.sending || props.locked) return;
    topicIds.value =
      topicId && props.topics.some((topic) => topic.id === topicId && !topic.deletedAt)
        ? [topicId]
        : [];
  }

  function selectMember(memberId?: string): void {
    if (props.sending || props.locked) return;
    mentionedMemberIds.value =
      memberId && agentMembers.value.some((member) => member.id === memberId) ? [memberId] : [];
  }

  async function quote(message: RoomMessage): Promise<void> {
    draft.value = {
      ...draft.value,
      topicIds: message.topicIds.filter((id) => props.topics.some((topic) => topic.id === id)),
      mentionedMemberIds: message.mentionedMemberIds.filter((id) =>
        agentMembers.value.some((member) => member.id === id),
      ),
    };
    await nextTick();
    textarea.value?.focus();
  }

  function submit(): void {
    if (props.sending || props.locked) return;
    attempted.value = true;
    if (showContentError.value || showRecipientError.value) return;
    emit("send", {
      content: content.value.trim(),
      topicIds: [...topicIds.value],
      mentionedMemberIds: [...mentionedMemberIds.value],
      ...(draft.value.capabilities?.length ? { capabilities: [...draft.value.capabilities] } : {}),
      ...(props.replyTo ? { replyToMessageId: props.replyTo.id } : {}),
    });
  }

  function onKeydown(event: KeyboardEvent): void {
    if (composing.value || event.isComposing || event.keyCode === 229 || event.shiftKey) return;
    if (pickerOpen.value) {
      if (event.key === "Escape") {
        event.preventDefault();
        dismissed = `${content.value}:${textarea.value?.selection()?.start}`;
        query.value = undefined;
        return;
      }
      if (["ArrowDown", "ArrowUp"].includes(event.key)) {
        event.preventDefault();
        activeIndex.value =
          (activeIndex.value + (event.key === "ArrowDown" ? 1 : -1) + options.value.length) %
          (options.value.length || 1);
        void nextTick(() =>
          document
            .getElementById(`capability-${activeIndex.value}`)
            ?.scrollIntoView?.({ block: "nearest" }),
        );
        return;
      }
      if (event.key === "Enter" || (event.key === "Tab" && options.value.length)) {
        event.preventDefault();
        const option = options.value[activeIndex.value];
        if (option) void selectCapability(option);
        return;
      }
    }
    if (event.key === "Enter") {
      event.preventDefault();
      submit();
    }
  }

  function reset(): void {
    draft.value = { ...draft.value, content: "", mentionedMemberIds: [], capabilities: [] };
    query.value = undefined;
    attempted.value = false;
    textarea.value?.focus();
  }

  defineExpose({ reset, quote, addTopic, addMember, selectTopic, selectMember });
</script>

<style scoped>
  .capability-input {
    position: relative;
    flex: 1;
    min-width: 0;
  }
  .capability-picker {
    position: absolute;
    z-index: 20;
    bottom: calc(100% + 8px);
    left: 0;
    width: 100%;
    min-width: 260px;
    max-height: 320px;
    overflow-y: auto;
    border: 1px solid hsl(var(--border));
    border-radius: 6px;
    background: hsl(var(--popover));
    color: hsl(var(--popover-foreground));
    box-shadow: 0 6px 20px hsl(var(--foreground) / 0.1);
  }
  .capability-picker-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 12px;
  }
  .capability-picker-status {
    padding: 4px 12px;
    color: hsl(var(--muted-foreground));
  }
  .capability-option {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 8px 12px;
    text-align: left;
  }
  .capability-option[aria-selected="true"] {
    background: hsl(var(--accent));
    color: hsl(var(--accent-foreground));
  }
  .capability-option > svg {
    flex: none;
  }
  .capability-option > span {
    min-width: 0;
  }
  .capability-option-label,
  .capability-option-description {
    display: block;
  }
  .capability-option-description {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: hsl(var(--muted-foreground));
  }
</style>
