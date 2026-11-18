<template>
  <div class="app-menu-actions">
    <a
      class="icon-button app-menu-trigger"
      :href="githubRepositoryUrl"
      target="_blank"
      rel="noopener noreferrer"
      :aria-label="t('appMenu.githubRepository')"
      :title="githubRepositoryUrl"
    >
      <svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true" focusable="false">
        <path
          d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82A7.4 7.4 0 0 1 8 3.86c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8Z"
        />
      </svg>
    </a>
    <DropdownMenuRoot :modal="false" @update:open="onMenuOpen">
      <DropdownMenuTrigger as-child>
        <button
          type="button"
          class="icon-button app-menu-trigger"
          :aria-label="themeLabel"
          :title="themeLabel"
        >
          <AppIcon :name="themeIcons[preferences.theme]" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuPortal>
        <DropdownMenuContent
          class="room-switcher-menu app-menu-content"
          :aria-label="t('settings.appearance')"
          side="bottom"
          align="end"
          :side-offset="8"
          :collision-padding="12"
        >
          <DropdownMenuRadioGroup
            :model-value="preferences.theme"
            :aria-label="t('settings.appearance')"
          >
            <DropdownMenuRadioItem
              v-for="option in themeOptions"
              :key="option.value"
              :value="option.value"
              :disabled="preferences.loading || preferences.saving"
              class="room-menu-action app-menu-option"
              @select.prevent="selectTheme(option.value)"
            >
              <span class="app-menu-option-label">
                <AppIcon :name="themeIcons[option.value]" />
                <span>{{ option.label }}</span>
              </span>
              <DropdownMenuItemIndicator><AppIcon name="check" /></DropdownMenuItemIndicator>
            </DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenuPortal>
    </DropdownMenuRoot>
    <DropdownMenuRoot :modal="false" @update:open="onMenuOpen">
      <DropdownMenuTrigger as-child>
        <button
          type="button"
          class="icon-button app-menu-trigger"
          :aria-label="t('appMenu.title')"
          :title="t('appMenu.title')"
        >
          <AppIcon name="settings" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuPortal>
        <DropdownMenuContent
          class="room-switcher-menu app-menu-content"
          :aria-label="t('appMenu.title')"
          side="bottom"
          align="end"
          :side-offset="8"
          :collision-padding="12"
        >
          <DropdownMenuSub>
            <DropdownMenuSubTrigger class="room-menu-action">
              <AppIcon name="language" />
              <span>{{ t("settings.language") }}</span>
              <AppIcon name="chevron" class="app-menu-chevron" />
            </DropdownMenuSubTrigger>
            <DropdownMenuPortal>
              <DropdownMenuSubContent
                class="room-switcher-menu app-menu-content"
                :side-offset="4"
                :collision-padding="12"
              >
                <DropdownMenuRadioGroup
                  :model-value="preferences.language"
                  :aria-label="t('settings.language')"
                >
                  <DropdownMenuRadioItem
                    v-for="option in options"
                    :key="option.value"
                    :value="option.value"
                    :disabled="preferences.loading || preferences.saving"
                    class="room-menu-action app-menu-option"
                    @select.prevent="selectLanguage(option.value)"
                  >
                    <span>{{ option.label }}</span>
                    <DropdownMenuItemIndicator><AppIcon name="check" /></DropdownMenuItemIndicator>
                  </DropdownMenuRadioItem>
                </DropdownMenuRadioGroup>
              </DropdownMenuSubContent>
            </DropdownMenuPortal>
          </DropdownMenuSub>
          <DropdownMenuItem class="room-menu-action" @select="openAbout">
            <AppIcon name="info" />{{ t("appMenu.about") }}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenuPortal>
    </DropdownMenuRoot>
  </div>
  <AppDialog
    :open="aboutOpen"
    :title="t('appMenu.about')"
    :busy="false"
    content-class="about-dialog"
    @close="aboutOpen = false"
  >
    <div class="about-content">
      <img :src="brandIconUrl" alt="" width="48" height="48" />
      <div class="about-brand">Conflua</div>
      <dl class="about-version">
        <dt>{{ t("appMenu.version") }}</dt>
        <dd>
          {{ loadingVersion ? t("common.loading") : (version ?? t("appMenu.versionUnavailable")) }}
        </dd>
      </dl>
    </div>
  </AppDialog>
</template>

<script setup lang="ts">
  import {
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuItemIndicator,
    DropdownMenuPortal,
    DropdownMenuRadioGroup,
    DropdownMenuRadioItem,
    DropdownMenuRoot,
    DropdownMenuSub,
    DropdownMenuSubContent,
    DropdownMenuSubTrigger,
    DropdownMenuTrigger,
  } from "reka-ui";
  import { computed, ref } from "vue";
  import { useI18n } from "vue-i18n";

  import AppDialog from "@/components/AppDialog.vue";
  import AppIcon from "@/components/AppIcon.vue";
  import { fetchAppInfo } from "@/services/appInfoApi";
  import type { LanguagePreference, ThemePreference } from "@/services/preferencesApi";
  import { usePreferencesStore } from "@/stores/preferences";
  import { useToastsStore } from "@/stores/toasts";

  const { t } = useI18n();
  const preferences = usePreferencesStore();
  const toasts = useToastsStore();
  const aboutOpen = ref(false);
  const version = ref<string | null>(null);
  const loadingVersion = ref(false);
  const brandIconUrl = `${import.meta.env.BASE_URL}conflua.png`;
  const githubRepositoryUrl = "https://github.com/leoninew/conflua";
  const options = computed(() => [
    { value: "system" as const, label: t("settings.system") },
    { value: "zh-CN" as const, label: "简体中文" },
    { value: "en" as const, label: "English" },
  ]);
  const themeOptions = computed(() => [
    { value: "system" as const, label: t("settings.system") },
    { value: "light" as const, label: t("settings.light") },
    { value: "dark" as const, label: t("settings.dark") },
  ]);
  const themeIcons = { system: "monitor", light: "sun", dark: "moon" } as const;
  const themeLabel = computed(
    () => `${t("settings.appearance")}: ${t(`settings.${preferences.theme}`)}`,
  );

  function onMenuOpen(open: boolean): void {
    if (open && !preferences.saving && !preferences.loading) {
      void preferences.load();
    }
  }

  async function selectLanguage(language: LanguagePreference): Promise<void> {
    if (preferences.loading || preferences.saving || language === preferences.language) {
      return;
    }
    if (await preferences.save(language)) {
      toasts.success({ key: "appMenu.languageSaved" });
    }
  }

  async function selectTheme(theme: ThemePreference): Promise<void> {
    if (preferences.loading || preferences.saving || theme === preferences.theme) {
      return;
    }
    if (await preferences.saveTheme(theme)) {
      toasts.success({ key: "appMenu.themeSaved" });
    }
  }

  async function openAbout(): Promise<void> {
    aboutOpen.value = true;
    loadingVersion.value = true;
    try {
      version.value = (await fetchAppInfo()).version;
    } catch {
      version.value = null;
    } finally {
      loadingVersion.value = false;
    }
  }
</script>

<style scoped>
  .app-menu-actions {
    display: flex;
    flex: none;
    align-items: center;
    gap: 4px;
  }
  .app-menu-trigger {
    flex: none;
    width: 32px;
    height: 32px;
  }
  .app-menu-trigger :deep(svg) {
    width: 20px;
    height: 20px;
  }
  .app-menu-content {
    min-width: 160px;
  }
  .app-menu-chevron {
    margin-left: auto;
  }
  .app-menu-option {
    justify-content: space-between;
    gap: 16px;
  }
  .app-menu-option[data-disabled] {
    opacity: 0.5;
  }
  .app-menu-option-label {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .about-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 12px 8px 16px;
    text-align: center;
  }
  .about-content img {
    flex: none;
  }
  .about-brand {
    margin-top: 12px;
    font-size: var(--font-size-title);
    line-height: var(--line-height-title);
    font-weight: 600;
  }
  .about-version {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    column-gap: 8px;
    margin: 6px 0 0;
  }
  .about-version dt {
    color: hsl(var(--muted-foreground));
  }
  .about-version dd {
    min-width: 0;
    margin: 0;
    overflow-wrap: anywhere;
  }
</style>

<style>
  .app-dialog.about-dialog {
    width: min(360px, calc(100vw - 32px));
  }
  .app-dialog.about-dialog .dialog-heading {
    margin-bottom: 12px;
  }
</style>
