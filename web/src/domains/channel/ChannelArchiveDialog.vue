<template>
  <AppDialog
    :open="channel !== undefined"
    :title="t('channel.archiveTitle')"
    :busy="busy"
    initial-focus="#cancel-channel-archive"
    @close="$emit('close')"
  >
    <div class="setup-form">
      <p>{{ t("channel.archiveConfirm", { name: channel?.name ?? "" }) }}</p>
      <p v-if="error" class="field-error" role="alert">{{ translateMessage(error) }}</p>
      <footer class="dialog-actions">
        <AppButton
          id="cancel-channel-archive"
          variant="secondary"
          :disabled="busy"
          @click="$emit('close')"
        >
          {{ t("common.cancel") }}
        </AppButton>
        <AppButton
          :loading="busy"
          :loading-label="t('channel.archiving')"
          @click="$emit('confirm')"
        >
          {{ t("channel.archive") }}
        </AppButton>
      </footer>
    </div>
  </AppDialog>
</template>

<script setup lang="ts">
  import { useI18n } from "vue-i18n";

  import AppButton from "@/components/AppButton.vue";
  import AppDialog from "@/components/AppDialog.vue";
  import { translateMessage } from "@/i18n";
  import type { MessageDescriptor } from "@/i18n";
  import type { Channel } from "@/services/channelApi";

  const { t } = useI18n();
  defineProps<{ channel?: Channel; busy: boolean; error: MessageDescriptor | null }>();
  defineEmits<{ close: []; confirm: [] }>();
</script>
