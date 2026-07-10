import { defineStore } from "pinia";

import { i18n, initialLang, type UiLang } from "../i18n";

export const usePrefsStore = defineStore("prefs", {
  state: () => ({ uiLang: initialLang() }),
  actions: {
    setLang(lang: UiLang) {
      this.uiLang = lang;
      localStorage.setItem("zoko-lang", lang);
      i18n.global.locale.value = lang;
    },
    toggle() {
      this.setLang(this.uiLang === "zh" ? "en" : "zh");
    },
  },
});
