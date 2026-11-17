<template>
  <RoomSidebarSection
    :title="t('channel.label')"
    :action-label="t('channel.create')"
    :busy="disabled"
    @create="$emit('create')"
  >
    <nav class="sidebar-list" :aria-label="t('channel.navigation')">
      <div v-if="defaultChannel" class="sidebar-node sidebar-node-fixed">
        <RouterLink
          v-slot="{ href }"
          :to="{
            name: 'channel',
            params: { roomId: defaultChannel.roomId, channelId: defaultChannel.id },
          }"
          custom
        >
          <a
            :href="href"
            class="sidebar-list-item channel-item"
            :class="{ 'is-active': defaultChannel.id === channelId }"
            :aria-current="defaultChannel.id === channelId ? 'page' : undefined"
            :aria-label="t('channel.switch', { name: t('channel.default') })"
            :title="defaultChannel.description"
            @click.left.exact.prevent="$emit('select', defaultChannel.id)"
          >
            <AppIcon name="chat" class="sidebar-item-icon" />
            <span class="sidebar-node-name">{{ t("channel.default") }}</span>
          </a>
        </RouterLink>
      </div>
      <VueDraggable
        v-model="channels"
        class="sidebar-sortable-list"
        draggable=".sidebar-node"
        handle=".sidebar-drag-handle"
        ghost-class="sidebar-drag-ghost"
        chosen-class="sidebar-drag-chosen"
        :animation="150"
        :disabled="disabled"
      >
        <div v-for="item in channels" :key="item.id" class="sidebar-node channel-node">
          <button
            type="button"
            class="sidebar-drag-handle"
            :aria-label="t('channel.reorder', { name: item.name })"
            :title="t('sidebar.reorder')"
            :disabled="disabled || channels.length < 2"
            @keydown.up.prevent="$emit('move', item.id, -1)"
            @keydown.down.prevent="$emit('move', item.id, 1)"
          >
            <AppIcon name="grip" />
          </button>
          <RouterLink
            v-slot="{ href }"
            :to="{ name: 'channel', params: { roomId: item.roomId, channelId: item.id } }"
            custom
          >
            <a
              :href="href"
              class="sidebar-list-item channel-item"
              :class="{ 'is-active': item.id === channelId }"
              :aria-current="item.id === channelId ? 'page' : undefined"
              :aria-label="t('channel.switch', { name: item.name })"
              :title="item.description"
              @click.left.exact.prevent="$emit('select', item.id)"
            >
              <AppIcon name="chat" class="sidebar-item-icon" />
              <span class="sidebar-node-name">{{ item.name }}</span>
            </a>
          </RouterLink>
          <button
            v-if="canArchiveChannel(item, channelId)"
            type="button"
            class="channel-archive-button"
            :aria-label="t('channel.archiveNamed', { name: item.name })"
            :disabled="disabled"
            @click.stop="$emit('archive', item)"
          >
            {{ t("channel.archive") }}
          </button>
        </div>
      </VueDraggable>
    </nav>
  </RoomSidebarSection>
</template>

<script setup lang="ts">
  import { VueDraggable } from "vue-draggable-plus";
  import { RouterLink } from "vue-router";
  import { useI18n } from "vue-i18n";

  import AppIcon from "@/components/AppIcon.vue";
  import RoomSidebarSection from "@/domains/room/RoomSidebarSection.vue";
  import { canArchiveChannel } from "@/domains/channel/useChannelArchive";
  import type { Channel } from "@/services/channelApi";

  const { t } = useI18n();
  defineProps<{
    defaultChannel?: Channel;
    channelId?: string;
    disabled: boolean;
  }>();
  defineEmits<{
    create: [];
    select: [channelId: string];
    move: [channelId: string, offset: number];
    archive: [channel: Channel];
  }>();
  const channels = defineModel<Channel[]>("channels", { required: true });
</script>

<style scoped>
  .channel-item {
    text-decoration: none;
  }
  .channel-node:hover > .channel-item {
    background: hsl(var(--foreground) / 0.04);
  }
  .channel-archive-button {
    position: absolute;
    top: 50%;
    right: 8px;
    height: 28px;
    padding: 0;
    color: hsl(var(--muted-foreground));
    font-size: var(--font-size-caption);
    line-height: var(--line-height-caption);
    transform: translateY(-50%);
    opacity: 0;
    pointer-events: none;
  }
  .channel-node:hover > .channel-archive-button,
  .channel-archive-button:focus-visible {
    opacity: 1;
    pointer-events: auto;
  }
  .channel-archive-button:hover:not(:disabled) {
    color: hsl(var(--foreground));
  }
  .channel-node:has(> .channel-archive-button):hover > .channel-item,
  .channel-node:has(> .channel-archive-button:focus-visible) > .channel-item {
    padding-right: 44px;
  }
</style>
