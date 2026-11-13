<template>
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
  <AppDialog
    :open="aboutOpen"
    :title="t('appMenu.about')"
    :busy="false"
    content-class="about-dialog"
    @close="aboutOpen = false"
  >
    <div class="about-content">
      <img :src="brandIconUrl" alt="" width="48" height="48" />
      <div class="about-brand">Agent Relay</div>
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
  import type { LanguagePreference } from "@/services/preferencesApi";
  import { usePreferencesStore } from "@/stores/preferences";
  import { useToastsStore } from "@/stores/toasts";

  const { t } = useI18n();
  const preferences = usePreferencesStore();
  const toasts = useToastsStore();
  const aboutOpen = ref(false);
  const version = ref<string | null>(null);
  const loadingVersion = ref(false);
  const brandIconUrl = `${import.meta.env.BASE_URL}agent-relay.png`;
  const options = computed(() => [
    { value: "system" as const, label: t("settings.system") },
    { value: "zh-CN" as const, label: "简体中文" },
    { value: "en" as const, label: "English" },
  ]);

  function onMenuOpen(open: boolean): void {
    if (open && !preferences.saving && !preferences.loading) void preferences.load();
  }

  async function selectLanguage(language: LanguagePreference): Promise<void> {
    if (preferences.loading || preferences.saving || language === preferences.language) return;
    if (await preferences.save(language)) toasts.success({ key: "appMenu.languageSaved" });
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
  .app-menu-trigger {
    flex: none;
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
