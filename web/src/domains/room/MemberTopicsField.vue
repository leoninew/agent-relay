<template>
  <fieldset
    class="setup-field"
    :disabled="disabled"
    :aria-invalid="!!error"
    :aria-describedby="`${idPrefix}-topics-error`"
  >
    <legend>{{ t("forms.subscribeOptional") }}</legend>
    <AppCheckboxGroup
      v-model="topicIds"
      class="setup-topics"
      :aria-label="t('forms.subscribe')"
      :clear-label="t('forms.clearSubscriptions')"
      :disabled="disabled"
      :invalid="!!error"
      :described-by="`${idPrefix}-topics-error`"
    >
      <AppCheckbox v-for="topic in topics" :key="topic.id" class="routing-choice" :value="topic.id">
        <span># {{ topic.name }}</span>
      </AppCheckbox>
    </AppCheckboxGroup>
    <p v-if="error" :id="`${idPrefix}-topics-error`" class="field-error">
      {{ translateMessage(error) }}
    </p>
    <div class="inline-topic-create">
      <label :for="`${idPrefix}-new-topic`" class="sr-only">{{ t("forms.newTopicName") }}</label>
      <AppInput
        :id="`${idPrefix}-new-topic`"
        v-model="newTopicName"
        maxlength="40"
        :placeholder="t('forms.newTopicName')"
        :disabled="disabled || busy"
        :invalid="!!topicNameError"
        :clear-label="t('forms.clearNewTopic')"
        :aria-describedby="topicNameError ? `${idPrefix}-new-topic-error` : undefined"
        @keydown.enter.prevent="createInlineTopic"
      />
      <AppButton
        variant="secondary"
        :loading="busy"
        :loading-label="t('forms.adding')"
        :disabled="disabled"
        @click="createInlineTopic"
      >
        {{ t("forms.addTopic") }}
      </AppButton>
    </div>
    <p v-if="topicNameError" :id="`${idPrefix}-new-topic-error`" class="field-error">
      {{ translateMessage(topicNameError) }}
    </p>
    <p v-if="topicRequestError" class="field-error" role="alert">
      {{ translateMessage(topicRequestError) }}
    </p>
  </fieldset>
</template>

<script setup lang="ts">
  import { translateMessage } from "@/i18n";
  import type { MessageDescriptor } from "@/i18n";
  import { ref, watch } from "vue";
  import { useI18n } from "vue-i18n";

  import AppButton from "@/components/AppButton.vue";
  import AppCheckbox from "@/components/AppCheckbox.vue";
  import AppCheckboxGroup from "@/components/AppCheckboxGroup.vue";
  import AppInput from "@/components/AppInput.vue";
  import { describeApiError } from "@/services/api";
  import type { Topic } from "@/services/roomApi";
  import { useRoomsStore } from "@/stores/rooms";
  import { useToastsStore } from "@/stores/toasts";

  const { t } = useI18n();
  const props = defineProps<{
    idPrefix: string;
    topics: Topic[];
    roomId?: string;
    disabled: boolean;
    error?: MessageDescriptor;
  }>();
  const topicIds = defineModel<string[]>({ required: true });
  const busy = defineModel<boolean>("busy", { default: false });
  const roomsStore = useRoomsStore();
  const toasts = useToastsStore();
  const newTopicName = ref("");
  const topicNameError = ref<MessageDescriptor | null>(null);
  const topicRequestError = ref<MessageDescriptor | null>(null);

  watch(newTopicName, () => {
    topicNameError.value = null;
    topicRequestError.value = null;
  });

  async function createInlineTopic(): Promise<void> {
    if (props.disabled || busy.value || !props.roomId) return;
    const topicName = newTopicName.value.trim();
    topicNameError.value = null;
    topicRequestError.value = null;
    if (!topicName) {
      topicNameError.value = { key: "validation.topic" };
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
      toasts.success({ key: "notice.topicCreated" });
      if (props.roomId === roomId) {
        topicIds.value = [...topicIds.value, topic.id];
        newTopicName.value = "";
      }
    } catch (caught) {
      topicRequestError.value = describeApiError(caught, "errors.topicAdd");
      toasts.error(topicRequestError.value);
    } finally {
      busy.value = false;
    }
  }
</script>
