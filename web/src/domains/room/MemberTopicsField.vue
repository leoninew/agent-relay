<template>
  <fieldset
    class="setup-field"
    :disabled="disabled"
    :aria-invalid="!!error"
    :aria-describedby="`${idPrefix}-topics-error`"
  >
    <legend>订阅话题（可选）</legend>
    <AppCheckboxGroup
      v-model="topicIds"
      class="setup-topics"
      aria-label="订阅话题"
      clear-label="清空订阅话题"
      :disabled="disabled"
      :invalid="!!error"
      :described-by="`${idPrefix}-topics-error`"
    >
      <AppCheckbox v-for="topic in topics" :key="topic.id" class="routing-choice" :value="topic.id">
        <span># {{ topic.name }}</span>
      </AppCheckbox>
    </AppCheckboxGroup>
    <p v-if="error" :id="`${idPrefix}-topics-error`" class="field-error">{{ error }}</p>
    <div class="inline-topic-create">
      <label :for="`${idPrefix}-new-topic`" class="sr-only">新话题名称</label>
      <AppInput
        :id="`${idPrefix}-new-topic`"
        v-model="newTopicName"
        maxlength="40"
        placeholder="新话题名称"
        :disabled="disabled || busy"
        :invalid="!!topicNameError"
        clear-label="清空新话题名称"
        :aria-describedby="topicNameError ? `${idPrefix}-new-topic-error` : undefined"
        @keydown.enter.prevent="createInlineTopic"
      />
      <AppButton
        variant="secondary"
        :loading="busy"
        loading-label="添加中…"
        :disabled="disabled"
        @click="createInlineTopic"
      >
        添加话题
      </AppButton>
    </div>
    <p v-if="topicNameError" :id="`${idPrefix}-new-topic-error`" class="field-error">
      {{ topicNameError }}
    </p>
    <p v-if="topicRequestError" class="field-error" role="alert">{{ topicRequestError }}</p>
  </fieldset>
</template>

<script setup lang="ts">
  import { ref, watch } from "vue";

  import AppButton from "@/components/AppButton.vue";
  import AppCheckbox from "@/components/AppCheckbox.vue";
  import AppCheckboxGroup from "@/components/AppCheckboxGroup.vue";
  import AppInput from "@/components/AppInput.vue";
  import { describeApiError } from "@/services/api";
  import type { Topic } from "@/services/roomApi";
  import { useRoomsStore } from "@/stores/rooms";
  import { useToastsStore } from "@/stores/toasts";

  const props = defineProps<{
    idPrefix: string;
    topics: Topic[];
    roomId?: string;
    disabled: boolean;
    error?: string;
  }>();
  const topicIds = defineModel<string[]>({ required: true });
  const busy = defineModel<boolean>("busy", { default: false });
  const roomsStore = useRoomsStore();
  const toasts = useToastsStore();
  const newTopicName = ref("");
  const topicNameError = ref("");
  const topicRequestError = ref("");

  watch(newTopicName, () => {
    topicNameError.value = "";
    topicRequestError.value = "";
  });

  async function createInlineTopic(): Promise<void> {
    if (props.disabled || busy.value || !props.roomId) return;
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
    busy.value = true;
    try {
      const topic = await roomsStore.createTopic(roomId, { name: topicName, description: "" });
      toasts.success("话题已创建");
      if (props.roomId === roomId) {
        topicIds.value = [...topicIds.value, topic.id];
        newTopicName.value = "";
      }
    } catch (caught) {
      topicRequestError.value = describeApiError(caught, "话题添加失败，请重试。");
      toasts.error(topicRequestError.value);
    } finally {
      busy.value = false;
    }
  }
</script>
