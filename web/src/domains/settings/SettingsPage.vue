<template>
  <section class="settings-page">
    <div class="settings-content">
      <header class="settings-heading">
        <button
          class="icon-button"
          type="button"
          :title="t('settings.back')"
          :aria-label="t('settings.back')"
          @click="goBack"
        >
          <ArrowLeft :size="20" :stroke-width="1.7" />
        </button>
        <h1>{{ t("settings.title") }}</h1>
      </header>
      <form class="settings-form" @submit.prevent="save">
        <fieldset :disabled="preferences.loading || preferences.saving">
          <legend>{{ t("settings.language") }}</legend>
          <div class="language-options">
            <label v-for="option in options" :key="option.value" class="language-option">
              <input v-model="selected" type="radio" name="language" :value="option.value" />
              <span>{{ option.label }}</span>
            </label>
          </div>
        </fieldset>
        <p v-if="preferences.error" role="alert" class="settings-error">
          {{ translateMessage(preferences.error) }}
        </p>
        <div class="settings-actions">
          <AppButton
            type="submit"
            :disabled="preferences.loading || preferences.saving"
            :loading="preferences.saving"
            :loading-label="t('settings.saving')"
          >
            {{ t("settings.save") }}
          </AppButton>
          <AppButton v-if="preferences.error" type="button" variant="secondary" @click="reload">
            {{ t("common.retry") }}
          </AppButton>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
  import { ArrowLeft } from "@lucide/vue";
  import { computed, onMounted, ref } from "vue";
  import { useRouter } from "vue-router";
  import { useI18n } from "vue-i18n";

  import AppButton from "@/components/AppButton.vue";
  import { translateMessage } from "@/i18n";
  import type { LanguagePreference } from "@/services/preferencesApi";
  import { usePreferencesStore } from "@/stores/preferences";
  import { useRoomsStore } from "@/stores/rooms";
  import { useToastsStore } from "@/stores/toasts";

  const { t } = useI18n();
  const router = useRouter();
  const preferences = usePreferencesStore();
  const rooms = useRoomsStore();
  const toasts = useToastsStore();
  const selected = ref<LanguagePreference>(preferences.language);
  const options = computed(() => [
    { value: "system" as const, label: t("settings.system") },
    { value: "zh-CN" as const, label: "简体中文" },
    { value: "en" as const, label: "English" },
  ]);

  async function reload(): Promise<void> {
    if (await preferences.load()) selected.value = preferences.language;
  }
  async function save(): Promise<void> {
    if (await preferences.save(selected.value)) toasts.success({ key: "settings.saved" });
  }
  function goBack(): void {
    const roomId = rooms.recentRoomId;
    void router.push(
      roomId && rooms.rooms.some((room) => room.id === roomId)
        ? { name: "room-detail", params: { roomId } }
        : { name: "room" },
    );
  }
  onMounted(reload);
</script>

<style scoped>
  .settings-page {
    min-height: calc(100dvh - var(--app-header-height));
    background: hsl(var(--card));
  }
  .settings-content {
    width: min(100%, 760px);
    margin: 0 auto;
    padding: 8px 24px 40px;
  }
  .settings-heading {
    display: flex;
    align-items: center;
    gap: 12px;
    min-height: 64px;
    border-bottom: 1px solid hsl(var(--border));
  }
  h1 {
    margin: 0;
    font-size: var(--font-size-title);
    line-height: var(--line-height-title);
    font-weight: 600;
  }
  fieldset {
    min-width: 0;
    border: 0;
    padding: 0;
    margin: 0;
  }
  legend {
    padding: 0;
    font-weight: 600;
    margin-bottom: 16px;
  }
  .settings-form {
    max-width: 480px;
    padding: 28px 0;
  }
  .language-options {
    display: grid;
    gap: 8px;
  }
  .language-option {
    display: flex;
    align-items: center;
    gap: 12px;
    min-height: 48px;
    padding: 10px 12px;
    border: 1px solid hsl(var(--border));
    border-radius: 6px;
    cursor: pointer;
  }
  .language-option:hover {
    background: hsl(var(--muted) / 0.5);
  }
  .language-option:has(input:checked) {
    border-color: hsl(var(--primary));
    background: hsl(var(--primary) / 0.05);
  }
  .language-option:has(input:focus-visible) {
    outline: 1px dashed hsl(var(--muted-foreground) / 0.7);
    outline-offset: 2px;
  }
  .language-option:has(input:disabled) {
    cursor: not-allowed;
    opacity: 0.6;
  }
  .language-option input {
    flex: none;
    width: 16px;
    height: 16px;
    accent-color: hsl(var(--primary));
  }
  .settings-error {
    margin-top: 16px;
    color: hsl(var(--destructive));
  }
  .settings-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 24px;
  }
  .settings-heading button:focus-visible {
    outline: 1px dashed hsl(var(--muted-foreground) / 0.7);
    outline-offset: 3px;
  }
  @media (max-width: 480px) {
    .settings-content {
      padding-inline: 16px;
    }
  }
</style>
