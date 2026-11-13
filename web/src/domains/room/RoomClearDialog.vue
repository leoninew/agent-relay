<template>
  <AppDialog
    :open="room !== undefined"
    :title="t('room.clearTitle')"
    :busy="saving"
    @close="$emit('close')"
  >
    <div class="setup-form">
      <p>{{ t("room.clearConfirm", { name: room?.name ?? "" }) }}</p>
      <p class="delete-description">
        {{ t("room.clearWarning") }}
      </p>
      <p v-if="error" class="field-error" role="alert">{{ translateMessage(error) }}</p>
      <footer class="dialog-actions">
        <AppButton variant="secondary" :disabled="saving" @click="$emit('close')">{{
          t("common.cancel")
        }}</AppButton>
        <AppButton
          variant="warning"
          :loading="saving"
          :loading-label="t('room.clearing')"
          @click="$emit('confirm')"
        >
          {{ t("room.clearAction") }}
        </AppButton>
      </footer>
    </div>
  </AppDialog>
</template>

<script setup lang="ts">
  import { useI18n } from "vue-i18n";
  import { translateMessage } from "@/i18n";
  import type { MessageDescriptor } from "@/i18n";

  const { t } = useI18n();
  import AppButton from "@/components/AppButton.vue";
  import AppDialog from "@/components/AppDialog.vue";
  import type { Room } from "@/services/roomApi";

  defineProps<{ room?: Room; saving: boolean; error: MessageDescriptor | null }>();
  defineEmits<{ close: []; confirm: [] }>();
</script>
