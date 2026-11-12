<template>
  <AppDialog :open="room !== undefined" title="清空聊天室" :busy="saving" @close="$emit('close')">
    <div class="setup-form">
      <p>确定清空聊天室“{{ room?.name }}”吗？</p>
      <p class="delete-description">
        将清空此聊天室所有话题下的消息和投递记录，并移除当前无法连接的成员。清空后无法在界面恢复。
      </p>
      <p v-if="error" class="field-error" role="alert">{{ error }}</p>
      <footer class="dialog-actions">
        <AppButton variant="secondary" :disabled="saving" @click="$emit('close')">取消</AppButton>
        <AppButton
          variant="warning"
          :loading="saving"
          loading-label="清空中…"
          @click="$emit('confirm')"
        >
          确认清空
        </AppButton>
      </footer>
    </div>
  </AppDialog>
</template>

<script setup lang="ts">
  import AppButton from "@/components/AppButton.vue";
  import AppDialog from "@/components/AppDialog.vue";
  import type { Room } from "@/services/roomApi";

  defineProps<{ room?: Room; saving: boolean; error: string | null }>();
  defineEmits<{ close: []; confirm: [] }>();
</script>
