<template>
  <div class="app-shell">
    <header class="app-header">
      <RouterLink to="/" class="app-brand" aria-label="Agent Relay 首页">
        <img class="brand-mark" :src="brandIconUrl" alt="" width="32" height="32" />
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

  import AppToasts from "@/components/AppToasts.vue";
  import RoomSwitcher from "@/domains/room/RoomSwitcher.vue";

  const brandIconUrl = `${import.meta.env.BASE_URL}agent-relay.png`;
</script>
