<template>
  <AppDialog
    :open="target !== undefined"
    :title="t('forms.removeTitle', { kind })"
    :busy="saving"
    @close="$emit('close')"
  >
    <div class="setup-form">
      <p>{{ t("forms.removeConfirm", { kind, name: target?.node.name ?? "" }) }}</p>
      <p class="delete-description">
        {{ target ? t(`forms.remove${target.kind[0].toUpperCase()}${target.kind.slice(1)}`) : "" }}
      </p>
      <p v-if="error" class="field-error" role="alert">{{ translateMessage(error) }}</p>
      <footer class="dialog-actions">
        <AppButton variant="secondary" :disabled="saving" @click="$emit('close')">{{
          t("common.cancel")
        }}</AppButton>
        <AppButton
          class="delete-confirm"
          :loading="saving"
          :loading-label="t('forms.deleting')"
          @click="$emit('confirm')"
        >
          <span>{{ t("forms.confirmDelete") }}</span>
        </AppButton>
      </footer>
    </div>
  </AppDialog>
</template>

<script setup lang="ts">
  import { translateMessage } from "@/i18n";
  import type { MessageDescriptor } from "@/i18n";
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";

  import AppButton from "@/components/AppButton.vue";
  import AppDialog from "@/components/AppDialog.vue";
  import type { Member, Room, Topic } from "@/services/roomApi";

  export type DeleteTarget =
    | { kind: "room"; node: Room }
    | { kind: "topic"; node: Topic }
    | { kind: "member"; node: Member };

  const props = defineProps<{
    target?: DeleteTarget;
    saving: boolean;
    error: MessageDescriptor | null;
  }>();
  defineEmits<{ close: []; confirm: [] }>();
  const { t } = useI18n();
  const kind = computed(() =>
    props.target
      ? t(`forms.kind${props.target.kind[0].toUpperCase()}${props.target.kind.slice(1)}`)
      : "",
  );
</script>
