<template>
  <section class="message-detail-section message-queue" aria-label="队列">
    <header class="queue-heading">
      <h3>队列</h3>
      <div class="queue-heading-actions">
        <button
          type="button"
          class="icon-button"
          aria-label="刷新队列"
          :disabled="loading || loadingMore || clearing"
          @click="$emit('refresh')"
        >
          <AppIcon name="refresh" />
        </button>
        <button
          type="button"
          class="icon-button"
          aria-label="清空队列"
          :aria-busy="clearing"
          :disabled="loading || loadingMore || clearing || totalMessages === 0"
          @click="$emit('clear')"
        >
          <AppIcon name="trash" />
        </button>
      </div>
    </header>
    <div class="queue-content" :aria-busy="loading || loadingMore || clearing">
      <div v-if="error" class="queue-error" role="alert">
        <span>{{ error }}</span>
        <AppButton variant="plain" :disabled="loading || clearing" @click="$emit('refresh')">
          重试
        </AppButton>
      </div>
      <p v-if="clearError" class="queue-error" role="alert">{{ clearError }}</p>
      <AppLoading v-if="loading && !messages.length">正在加载队列…</AppLoading>
      <p v-else-if="!messages.length && !error" class="detail-empty">暂无入队中或接收中的消息</p>
      <table v-if="rows.length" class="queue-table" aria-label="队列记录">
        <thead>
          <tr>
            <th scope="col">消息</th>
            <th scope="col">状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.message.id">
            <td>
              <button
                type="button"
                class="queue-message"
                :aria-label="`查看消息 #${row.message.seq} 详情`"
                :title="row.message.content"
                @click="$emit('select', row.message.id)"
              >
                {{ row.preview }}
              </button>
            </td>
            <td>
              <span class="delivery-stage">{{ row.stage ?? "—" }}</span>
            </td>
          </tr>
        </tbody>
      </table>
      <AppButton
        v-if="hasMore"
        class="queue-load-more"
        variant="plain"
        :loading="loadingMore"
        loading-label="加载中…"
        :disabled="loading || clearing"
        @click="$emit('loadMore')"
      >
        加载更多消息
      </AppButton>
    </div>
  </section>
</template>

<script setup lang="ts">
  import { computed } from "vue";

  import AppButton from "@/components/AppButton.vue";
  import AppIcon from "@/components/AppIcon.vue";
  import AppLoading from "@/components/AppLoading.vue";
  import { deliveryStage } from "@/domains/room/deliveryStage";
  import type { RoomMessage } from "@/services/roomApi";

  const props = defineProps<{
    messages: RoomMessage[];
    totalMessages: number;
    hasMore: boolean;
    loading: boolean;
    loadingMore: boolean;
    clearing: boolean;
    error: string | null;
    clearError: string | null;
  }>();
  defineEmits<{
    select: [messageId: string];
    refresh: [];
    clear: [];
    loadMore: [];
  }>();

  const rows = computed(() =>
    props.messages.map((message) => {
      const characters = Array.from(message.content);
      return {
        message,
        preview: characters.slice(0, 15).join("") + (characters.length > 15 ? "…" : ""),
        stage: deliveryStage(message.deliveries),
      };
    }),
  );
</script>
