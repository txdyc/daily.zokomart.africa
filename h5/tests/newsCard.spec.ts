import { RouterLinkStub, mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import type { ArticleCard } from "../src/api/types";
import NewsCard from "../src/components/NewsCard.vue";
import { usePrefsStore } from "../src/stores/prefs";
import { freshPinia, testI18n } from "./helpers";

const article: ArticleCard = {
  id: 7,
  title: "Bank of Ghana unveils policy",
  title_zh: "加纳央行宣布政策",
  main_image_url: null,
  published_at: "2026-07-09T10:30:00",
  category: "business",
  country: { code: "GH", name_en: "Ghana", name_zh: "加纳", flag_emoji: "🇬🇭" },
};

function mountCard(a: ArticleCard, lang: "zh" | "en") {
  const pinia = freshPinia();
  usePrefsStore().setLang(lang);
  return mount(NewsCard, {
    props: { article: a },
    global: { plugins: [pinia, testI18n(lang)], stubs: { RouterLink: RouterLinkStub } },
  });
}

describe("NewsCard", () => {
  it("shows zh headline and zh country name in zh mode", () => {
    const w = mountCard(article, "zh");
    expect(w.text()).toContain("加纳央行宣布政策");
    expect(w.text()).toContain("加纳");
    expect(w.text()).toContain("07-09");
  });

  it("shows source headline and en country name in en mode", () => {
    const w = mountCard(article, "en");
    expect(w.text()).toContain("Bank of Ghana unveils policy");
    expect(w.text()).toContain("Ghana");
  });

  it("falls back to source title when title_zh is null", () => {
    const w = mountCard({ ...article, title_zh: null }, "zh");
    expect(w.text()).toContain("Bank of Ghana unveils policy");
  });

  it("links to the article detail route", () => {
    const w = mountCard(article, "zh");
    expect(w.findComponent(RouterLinkStub).props("to")).toBe("/article/7");
  });
});
