<template>
  <AppDialog :open="!!channel" :title="t('channel.edit')" :busy="saving" @close="$emit('close')">
    <form class="setup-form" novalidate @submit.prevent="submit">
      <div class="setup-form-content">
        <div class="setup-field">
          <label for="edit-channel-name">
            {{ t("channel.name") }} <span class="required-mark">*</span>
          </label>
          <AppInput
            id="edit-channel-name"
            v-model="name"
            maxlength="40"
            :disabled="saving || channel?.isDefault"
            :invalid="nameError"
            :clear-label="t('channel.clearName')"
            :aria-describedby="nameError ? 'edit-channel-name-error' : undefined"
            autocomplete="off"
          />
          <p v-if="nameError" id="edit-channel-name-error" class="field-error" role="alert">
            {{ t("validation.name") }}
          </p>
        </div>
        <div class="setup-field">
          <label for="edit-channel-description">{{ t("channel.description") }}</label>
          <AppInput
            id="edit-channel-description"
            v-model="description"
            maxlength="300"
            :disabled="saving"
            :clear-label="t('channel.clearDescription')"
          />
        </div>
        <p v-if="error" class="field-error" role="alert">{{ translateMessage(error) }}</p>
      </div>
      <footer class="dialog-actions">
        <AppButton variant="secondary" :disabled="saving" @click="$emit('close')">
          {{ t("common.cancel") }}
        </AppButton>
        <AppButton type="submit" :loading="saving" :loading-label="t('settings.saving')">
          {{ t("channel.save") }}
        </AppButton>
      </footer>
    </form>
  </AppDialog>
</template>

<script setup lang="ts">
  import { computed, ref, watch } from "vue";
  import { useI18n } from "vue-i18n";

  import AppButton from "@/components/AppButton.vue";
  import AppDialog from "@/components/AppDialog.vue";
  import AppInput from "@/components/AppInput.vue";
  import { translateMessage } from "@/i18n";
  import type { MessageDescriptor } from "@/i18n";
  import type { Channel, UpdateChannel } from "@/services/channelApi";

  const props = defineProps<{
    channel?: Channel;
    saving: boolean;
    error: MessageDescriptor | null;
  }>();
  const emit = defineEmits<{
    close: [];
    save: [channelId: string, request: UpdateChannel];
  }>();
  const { t } = useI18n();
  const name = ref("");
  const description = ref("");
  const attempted = ref(false);
  const nameError = computed(() => attempted.value && !name.value.trim());

  watch(
    () => props.channel,
    (channel) => {
      name.value = channel?.name ?? "";
      description.value = channel?.description ?? "";
      attempted.value = false;
    },
    { immediate: true },
  );

  function submit(): void {
    if (!props.channel || props.saving) return;
    attempted.value = true;
    if (nameError.value) return;
    emit("save", props.channel.id, { name: name.value.trim(), description: description.value });
  }
</script>
