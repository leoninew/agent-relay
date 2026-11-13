<template>
  <section class="message-detail-section message-queue" :aria-label="t('queue.title')">
    <header class="queue-heading">
      <h3>{{ t("queue.title") }}</h3>
      <div class="queue-heading-actions">
        <button
          type="button"
          class="icon-button"
          :aria-label="t('queue.refresh')"
          :disabled="loading || loadingMore || removingId !== null"
          @click="$emit('refresh')"
        >
          <AppIcon name="refresh" />
        </button>
      </div>
    </header>
    <div class="queue-content" :aria-busy="loading || loadingMore || removingId !== null">
      <div v-if="error" class="queue-error" role="alert">
        <span>{{ translateMessage(error) }}</span>
        <AppButton
          variant="plain"
          :disabled="loading || removingId !== null"
          @click="$emit('refresh')"
        >
          {{ t("common.retry") }}
        </AppButton>
      </div>
      <p v-if="removeError" class="queue-error" role="alert">{{ translateMessage(removeError) }}</p>
      <AppLoading v-if="loading && !messages.length">{{ t("queue.loading") }}</AppLoading>
      <p v-else-if="!messages.length && !error" class="detail-empty">{{ t("queue.empty") }}</p>
      <table v-if="rows.length" class="queue-table" :aria-label="t('queue.records')">
        <thead>
          <tr>
            <th scope="col">{{ t("queue.message") }}</th>
            <th scope="col">{{ t("queue.status") }}</th>
            <th scope="col" class="queue-actions">{{ t("queue.actions") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.message.id">
            <td>
              <button
                type="button"
                class="queue-message"
                :aria-label="t('queue.viewMessage', { seq: row.message.seq })"
                :title="row.text"
                @click="$emit('select', row.message.id)"
              >
                {{ row.preview }}
              </button>
            </td>
            <td>
              <span class="delivery-stage">{{ row.stage ? t(`delivery.${row.stage}`) : "—" }}</span>
            </td>
            <td class="queue-actions">
              <button
                type="button"
                class="icon-button"
                :aria-label="t('queue.removeMessage', { seq: row.message.seq })"
                :title="t('queue.removeHint')"
                :aria-busy="removingId === row.message.id"
                :disabled="loading || loadingMore || removingId !== null"
                @click="$emit('remove', row.message.id)"
              >
                <AppSpinner v-if="removingId === row.message.id" />
                <AppIcon v-else name="trash" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <AppButton
        v-if="hasMore"
        class="queue-load-more"
        variant="plain"
        :loading="loadingMore"
        :loading-label="t('common.loading')"
        :disabled="loading || removingId !== null"
        @click="$emit('loadMore')"
      >
        {{ t("queue.more") }}
      </AppButton>
    </div>
  </section>
</template>

<script setup lang="ts">
  import { computed } from "vue";
  import { useI18n } from "vue-i18n";
  import { translateMessage } from "@/i18n";
  import type { MessageDescriptor } from "@/i18n";

  import AppButton from "@/components/AppButton.vue";
  import AppIcon from "@/components/AppIcon.vue";
  import AppLoading from "@/components/AppLoading.vue";
  import AppSpinner from "@/components/AppSpinner.vue";
  import { deliveryStage } from "@/domains/room/deliveryStage";
  import { messageText } from "@/domains/room/inlineSkills";
  import type { RoomMessage } from "@/services/roomApi";

  const props = defineProps<{
    messages: RoomMessage[];
    hasMore: boolean;
    loading: boolean;
    loadingMore: boolean;
    removingId: string | null;
    error: MessageDescriptor | null;
    removeError: MessageDescriptor | null;
  }>();
  const { t } = useI18n();
  defineEmits<{
    select: [messageId: string];
    refresh: [];
    remove: [messageId: string];
    loadMore: [];
  }>();

  const rows = computed(() =>
    props.messages.map((message) => {
      const text = messageText(message.content, message.capabilities);
      const characters = Array.from(text);
      return {
        message,
        text,
        preview: characters.slice(0, 15).join("") + (characters.length > 15 ? "…" : ""),
        stage: deliveryStage(message.deliveries),
      };
    }),
  );
</script>
