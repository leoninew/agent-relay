<template>
  <div class="app-shell">
    <header class="app-header">
      <RouterLink to="/" class="app-brand" aria-label="Agent Relay 首页">
        <span class="brand-mark"><AppIcon name="relay" /></span>
        <span>Agent Relay</span>
      </RouterLink>
      <nav aria-label="主导航" class="app-navigation">
        <RoomSwitcher />
      </nav>
    </header>
    <main><RouterView /></main>
    <AppToasts />
  </div>
</template>

<script setup lang="ts">
  import { RouterLink, RouterView } from "vue-router";

  import AppIcon from "@/components/AppIcon.vue";
  import AppToasts from "@/components/AppToasts.vue";
  import RoomSwitcher from "@/domains/room/RoomSwitcher.vue";
</script>
