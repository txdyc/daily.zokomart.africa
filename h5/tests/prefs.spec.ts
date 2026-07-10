import { beforeEach, describe, expect, it } from "vitest";

import { i18n } from "../src/i18n";
import { usePrefsStore } from "../src/stores/prefs";
import { freshPinia } from "./helpers";

describe("prefs store", () => {
  beforeEach(() => {
    localStorage.clear();
    freshPinia();
  });

  it("defaults to zh", () => {
    expect(usePrefsStore().uiLang).toBe("zh");
  });

  it("toggle switches language, persists, and updates i18n locale", () => {
    const prefs = usePrefsStore();
    prefs.toggle();
    expect(prefs.uiLang).toBe("en");
    expect(localStorage.getItem("zoko-lang")).toBe("en");
    expect(i18n.global.locale.value).toBe("en");
    prefs.toggle();
    expect(prefs.uiLang).toBe("zh");
  });

  it("reads persisted language on init", () => {
    localStorage.setItem("zoko-lang", "en");
    freshPinia();
    expect(usePrefsStore().uiLang).toBe("en");
  });
});
