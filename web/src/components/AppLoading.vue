<template>
  <div class="app-loading" role="status" aria-live="polite" aria-busy="true">
    <AppSpinner />
    <span><slot>正在加载…</slot></span>
  </div>
</template>

<script setup lang="ts">
  import AppSpinner from "@/components/AppSpinner.vue";
</script>
