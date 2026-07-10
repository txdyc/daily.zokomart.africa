import { createI18n } from "vue-i18n";

import en from "./en";
import zh from "./zh";

export type UiLang = "zh" | "en";

export function initialLang(): UiLang {
  const stored = localStorage.getItem("zoko-lang");
  return stored === "en" ? "en" : "zh";
}

export const i18n = createI18n({
  legacy: false,
  locale: initialLang(),
  fallbackLocale: "zh",
  messages: { zh, en },
});
