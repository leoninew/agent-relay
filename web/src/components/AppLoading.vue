<template>
  <div class="app-loading" role="status" aria-live="polite" aria-busy="true">
    <AppSpinner />
    <span
      ><slot>{{ t("common.loading") }}</slot></span
    >
  </div>
</template>

<script setup lang="ts">
  import AppSpinner from "@/components/AppSpinner.vue";
  import { useI18n } from "vue-i18n";
  const { t } = useI18n();
</script>
