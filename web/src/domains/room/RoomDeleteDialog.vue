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
        {{ target ? descriptions[target.kind] : "" }}
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
  import type { Member, Room, Topic } from "@/services/roomApi";

  export type DeleteTarget =
    | { kind: "room"; node: Room }
    | { kind: "topic"; node: Topic }
    | { kind: "member"; node: Member };

  const props = defineProps<{ target?: DeleteTarget; saving: boolean; error: string | null }>();
  defineEmits<{ close: []; confirm: [] }>();
  const labels = { room: "聊天室", topic: "话题", member: "成员" };
  const descriptions = {
    room: "删除后将永久移除此聊天室的话题、成员、消息和投递记录，无法恢复。关联的 Codex 会话不受影响。",
    topic: "删除后将移除成员对此话题的订阅，已有消息和分发记录会保留。",
    member: "删除后该成员将退出聊天室，已有消息和分发记录会保留，关联的 Codex 会话不受影响。",
  };
  const kind = computed(() => (props.target ? labels[props.target.kind] : ""));
</script>
