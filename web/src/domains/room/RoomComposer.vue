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
              :title="member.activity"
              :value="member.id"
              :aria-label="`@ ${member.name}`"
              :aria-invalid="showRecipientError"
              :aria-describedby="showRecipientError ? 'routing-error' : undefined"
            >
              <span>{{ member.name }}</span>
            </AppCheckbox>
          </AppCheckboxGroup>
        </div>
        <p v-if="showRecipientError" id="routing-error" class="field-error" role="alert">
          {{ routingError }}
        </p>
      </fieldset>
      <label for="message-content" class="sr-only">消息内容</label>
      <AppInput
        id="message-content"
        ref="textarea"
        v-model="content"
        name="content"
        maxlength="6000"
        rows="3"
        placeholder="发送消息…"
        clear-label="清空消息内容"
        multiline
        :disabled="sending || locked"
        :invalid="showContentError"
        aria-describedby="content-error"
        @keydown.enter="onEnter"
      />
      <p v-if="showContentError" id="content-error" class="field-error" role="alert">
        请输入消息内容
      </p>
      <p v-if="error" class="field-error send-error" role="alert">{{ error }}</p>
      <div class="composer-footer">
        <div class="composer-actions">
          <AppButton
            type="submit"
            class="composer-send-button"
            :aria-label="sending ? '正在发送' : '发送消息'"
            :loading="sending"
            :disabled="locked"
            loading-label="发送中…"
          >
            <template #icon><AppIcon name="enter" /></template>
            发送
          </AppButton>
        </div>
      </div>
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
  import type { MessageDraft, Member, RoomMessage, Topic } from "@/services/roomApi";

  const props = defineProps<{
    roomId: string;
    topics: Topic[];
    members: Member[];
    replyTo?: RoomMessage;
    sending: boolean;
    locked?: boolean;
    error: string | null;
  }>();
  const emit = defineEmits<{
    send: [message: MessageDraft];
    cancelReply: [];
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

  watch(
    () => props.replyTo,
    async (message) => {
      if (message) {
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
    },
    { immediate: true },
  );

  function submit(): void {
    if (props.sending || props.locked) return;
    attempted.value = true;
    if (showContentError.value || showRecipientError.value) return;
    emit("send", {
      content: content.value.trim(),
      topicIds: [...topicIds.value],
      mentionedMemberIds: [...mentionedMemberIds.value],
      ...(props.replyTo ? { replyToMessageId: props.replyTo.id } : {}),
    });
  }

  function onEnter(event: KeyboardEvent): void {
    if ((event.ctrlKey || event.metaKey) && !event.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  function reset(): void {
    draft.value = { ...draft.value, content: "", mentionedMemberIds: [] };
    attempted.value = false;
    textarea.value?.focus();
  }

  defineExpose({ reset });
</script>
