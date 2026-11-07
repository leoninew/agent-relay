<template>
  <AppDialog
    :open="target !== undefined"
    :title="`删除${kind}`"
    :busy="saving"
    @close="$emit('close')"
  >
    <div class="setup-form">
      <p>确定删除{{ kind }}“{{ target?.node.name }}”吗？</p>
      <p class="delete-description">
        {{
          target?.kind === "topic"
            ? "删除后将移除成员对此话题的订阅，已有消息和分发记录会保留。"
            : "删除后该成员将退出聊天室，已有消息和分发记录会保留，关联的 Codex 会话不受影响。"
        }}
      </p>
      <p v-if="error" class="field-error" role="alert">{{ error }}</p>
      <footer class="dialog-actions">
        <AppButton variant="secondary" :disabled="saving" @click="$emit('close')">取消</AppButton>
        <AppButton
          class="delete-confirm"
          :loading="saving"
          loading-label="删除中…"
          @click="$emit('confirm')"
        >
          <span>确认删除</span>
        </AppButton>
      </footer>
    </div>
  </AppDialog>
</template>

<script setup lang="ts">
  import { computed } from "vue";

  import AppButton from "@/components/AppButton.vue";
  import AppDialog from "@/components/AppDialog.vue";
  import type { Member, Topic } from "@/services/roomApi";

  export type DeleteTarget = { kind: "topic"; node: Topic } | { kind: "member"; node: Member };

  const props = defineProps<{ target?: DeleteTarget; saving: boolean; error: string | null }>();
  defineEmits<{ close: []; confirm: [] }>();
  const kind = computed(() => (props.target?.kind === "topic" ? "话题" : "成员"));
</script>
