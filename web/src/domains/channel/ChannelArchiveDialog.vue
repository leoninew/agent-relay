<template>
  <AppDialog
    :open="channel !== undefined"
    :title="t('channel.archiveTitle')"
    :busy="busy"
    initial-focus="#archive-channel-name"
    @close="$emit('close')"
  >
    <form class="setup-form" novalidate @submit.prevent="submit">
      <div class="setup-form-content">
        <p>{{ t("channel.archiveConfirm") }}</p>
        <div class="setup-field">
          <label for="archive-channel-name">
            {{ t("channel.name") }} <span class="required-mark">*</span>
          </label>
          <AppInput
            id="archive-channel-name"
            v-model="name"
            maxlength="40"
            :disabled="busy"
            :invalid="nameError"
            :clear-label="t('channel.clearName')"
            :aria-describedby="nameError ? 'archive-channel-name-error' : undefined"
            autocomplete="off"
          />
          <p v-if="nameError" id="archive-channel-name-error" class="field-error" role="alert">
            {{ t("validation.name") }}
          </p>
        </div>
        <p v-if="error" class="field-error" role="alert">{{ translateMessage(error) }}</p>
      </div>
      <footer class="dialog-actions">
        <AppButton variant="secondary" :disabled="busy" @click="$emit('close')">
          {{ t("common.cancel") }}
        </AppButton>
        <AppButton type="submit" :loading="busy" :loading-label="t('channel.archiving')">
          {{ t("channel.archive") }}
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
  import type { Channel } from "@/services/channelApi";

  const { t } = useI18n();
  const props = defineProps<{
    channel?: Channel;
    busy: boolean;
    error: MessageDescriptor | null;
  }>();
  const emit = defineEmits<{ close: []; confirm: [name: string] }>();
  const name = ref("");
  const attempted = ref(false);
  const nameError = computed(() => attempted.value && !name.value.trim());

  watch(
    () => props.channel,
    (channel) => {
      name.value = channel?.name ?? "";
      attempted.value = false;
    },
    { immediate: true },
  );

  function submit(): void {
    if (!props.channel || props.busy) return;
    attempted.value = true;
    if (nameError.value) return;
    emit("confirm", name.value.trim());
  }
</script>
