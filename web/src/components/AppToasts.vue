<template>
  <ToastProvider label="操作提示" :duration="4000" swipe-direction="right">
    <Teleport to="body">
      <ToastRoot
        v-for="toast in toasts.items"
        :key="toast.id"
        class="app-toast"
        :data-tone="toast.tone"
        :duration="toast.tone === 'error' ? 8000 : 4000"
        :open="true"
        @update:open="!$event && toasts.dismiss(toast.id)"
      >
        <AppIcon :name="toast.tone === 'success' ? 'check' : 'info'" class="app-toast-icon" />
        <ToastTitle class="app-toast-message">
          <span class="sr-only">{{ toneLabels[toast.tone] }}：</span>{{ toast.message }}
        </ToastTitle>
        <ToastClose class="app-toast-close" aria-label="关闭提示">
          <AppIcon name="close" />
        </ToastClose>
      </ToastRoot>
      <ToastViewport class="app-toast-viewport" label="操作提示（{hotkey}）" />
    </Teleport>
  </ToastProvider>
</template>

<script setup lang="ts">
  import { ToastClose, ToastProvider, ToastRoot, ToastTitle, ToastViewport } from "reka-ui";

  import AppIcon from "@/components/AppIcon.vue";
  import { useToastsStore } from "@/stores/toasts";

  const toasts = useToastsStore();
  const toneLabels = { success: "已完成", error: "错误", info: "提示" };
</script>
