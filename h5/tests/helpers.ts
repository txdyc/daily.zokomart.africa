import { createPinia, setActivePinia } from "pinia";
import { createI18n } from "vue-i18n";

import en from "../src/i18n/en";
import zh from "../src/i18n/zh";

export function freshPinia() {
  const pinia = createPinia();
  setActivePinia(pinia);
  return pinia;
}

export function testI18n(locale: "zh" | "en" = "zh") {
  return createI18n({ legacy: false, locale, fallbackLocale: "zh", messages: { zh, en } });
}
