<template>
  <RoomSidebarSection
    :title="t('channel.label')"
    :action-label="t('channel.create')"
    :busy="disabled"
    @create="$emit('create')"
  >
    <nav class="sidebar-list" :aria-label="t('channel.navigation')">
      <div v-for="item in channels" :key="item.id" class="sidebar-node sidebar-node-fixed">
        <RouterLink
          :to="{ name: 'channel', params: { roomId: item.roomId, channelId: item.id } }"
          class="sidebar-list-item channel-item"
          :class="{ 'is-active': item.id === channelId }"
          :aria-current="item.id === channelId ? 'page' : undefined"
          :aria-label="
            t('channel.switch', { name: item.isDefault ? t('channel.default') : item.name })
          "
          :title="item.description"
          @click.left.exact="$emit('select', item.id)"
        >
          <AppIcon name="chat" class="sidebar-item-icon" />
          <span class="sidebar-node-name">{{
            item.isDefault ? t("channel.default") : item.name
          }}</span>
        </RouterLink>
      </div>
    </nav>
  </RoomSidebarSection>
</template>

<script setup lang="ts">
  import { RouterLink } from "vue-router";
  import { useI18n } from "vue-i18n";

  import AppIcon from "@/components/AppIcon.vue";
  import RoomSidebarSection from "@/domains/room/RoomSidebarSection.vue";
  import type { Channel } from "@/services/channelApi";

  const { t } = useI18n();
  defineProps<{
    channels: Channel[];
    channelId?: string;
    disabled: boolean;
  }>();
  defineEmits<{ create: []; select: [channelId: string] }>();
</script>

<style scoped>
  .channel-item {
    text-decoration: none;
  }
</style>
