<template>
  <ToastProvider :label="t('common.notifications')" :duration="4000" swipe-direction="right">
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
          <span class="sr-only">{{ t(`common.${toast.tone}`) }}：</span
          >{{ translateMessage(toast.message) }}
        </ToastTitle>
        <ToastClose class="app-toast-close" :aria-label="t('common.closeNotification')">
          <AppIcon name="close" />
        </ToastClose>
      </ToastRoot>
      <ToastViewport class="app-toast-viewport" :label="t('common.notifications')" />
    </Teleport>
  </ToastProvider>
</template>

<script setup lang="ts">
  import { ToastClose, ToastProvider, ToastRoot, ToastTitle, ToastViewport } from "reka-ui";
  import { useI18n } from "vue-i18n";

  import AppIcon from "@/components/AppIcon.vue";
  import { translateMessage } from "@/i18n";
  import { useToastsStore } from "@/stores/toasts";

  const toasts = useToastsStore();
  const { t } = useI18n();
</script>
