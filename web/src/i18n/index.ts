import { createI18n } from "vue-i18n";

import en from "./en";
import zhCN from "./zh-CN";

export type ResolvedLanguage = "zh-CN" | "en";
export type MessageDescriptor = {
  key: string;
  params?: Record<string, string | number>;
  requestId?: string;
};

export function createAppI18n(locale: ResolvedLanguage = "en") {
  return createI18n({
    legacy: false,
    locale,
    fallbackLocale: "en",
    messages: { en, "zh-CN": zhCN },
  });
}

export const i18n = createAppI18n();

export function translateMessage(message: MessageDescriptor): string {
  const text = i18n.global.t(message.key, message.params ?? {});
  return message.requestId
    ? `${text} (${i18n.global.t("common.requestId", { requestId: message.requestId })})`
    : text;
}
