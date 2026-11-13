<template>
  <div class="app-shell">
    <header class="app-header">
      <RouterLink to="/" class="app-brand" :aria-label="t('settings.home')">
        <img class="brand-mark" :src="brandIconUrl" alt="" width="32" height="32" />
        <span>Agent Relay</span>
      </RouterLink>
      <nav :aria-label="t('settings.navigation')" class="app-navigation">
        <RoomSwitcher />
      </nav>
      <AppMenu />
    </header>
    <div v-if="preferences.error" class="preferences-alert" role="status">
      <span>{{ translateMessage(preferences.error) }}</span>
      <button type="button" @click="preferences.load">{{ t("common.retry") }}</button>
    </div>
    <main>
      <RouterView v-slot="{ Component }">
        <KeepAlive :max="1">
          <component :is="Component" />
        </KeepAlive>
      </RouterView>
    </main>
    <AppToasts />
  </div>
</template>

<script setup lang="ts">
  import { RouterLink, RouterView } from "vue-router";
  import { useI18n } from "vue-i18n";

  import AppMenu from "@/components/AppMenu.vue";
  import AppToasts from "@/components/AppToasts.vue";
  import RoomSwitcher from "@/domains/room/RoomSwitcher.vue";
  import { translateMessage } from "@/i18n";
  import { usePreferencesStore } from "@/stores/preferences";

  const { t } = useI18n();
  const preferences = usePreferencesStore();
  const brandIconUrl = `${import.meta.env.BASE_URL}agent-relay.png`;
</script>

<style scoped>
  .app-shell {
    display: flex;
    flex-direction: column;
    height: 100dvh;
  }
  .app-header {
    flex-shrink: 0;
  }
  main {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }
  .preferences-alert {
    display: flex;
    flex-shrink: 0;
    gap: 12px;
    padding: 8px 16px;
    background: #fff4d6;
    color: #563d00;
  }
  .preferences-alert button {
    text-decoration: underline;
  }
</style>
