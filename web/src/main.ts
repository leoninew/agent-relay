import { createPinia } from "pinia";
import { createApp, watch } from "vue";

import "./style.css";
import App from "./App.vue";
import { i18n } from "./i18n";
import { router } from "./router";
import { usePreferencesStore } from "./stores/preferences";
import { createSystemThemeMediaQuery, createThemeRuntime } from "./theme";

const pinia = createPinia();
const preferences = usePreferencesStore(pinia);
const themeRuntime = createThemeRuntime(document.documentElement, createSystemThemeMediaQuery());
watch(
  () => preferences.resolvedLanguage,
  (language) => {
    i18n.global.locale.value = language;
    document.documentElement.lang = language;
  },
  { immediate: true },
);
watch(
  () => preferences.theme,
  (theme) => themeRuntime.setPreference(theme),
  { immediate: true },
);
async function start(): Promise<void> {
  await preferences.load();
  createApp(App).use(pinia).use(i18n).use(router).mount("#app");
}

void start();
