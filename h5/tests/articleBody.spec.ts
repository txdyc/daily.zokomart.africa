import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import ArticleBody from "../src/components/ArticleBody.vue";

const paragraphs = ["First source para.", "Second source para."];
const paragraphsZh = ["第一段。", "第二段。"];

describe("ArticleBody", () => {
  it("renders source paragraphs in source mode", () => {
    const w = mount(ArticleBody, {
      props: { paragraphs, paragraphsZh, mode: "source" },
    });
    expect(w.findAll("p").map((p) => p.text())).toEqual(paragraphs);
  });

  it("renders zh paragraphs in zh mode", () => {
    const w = mount(ArticleBody, {
      props: { paragraphs, paragraphsZh, mode: "zh" },
    });
    expect(w.findAll("p").map((p) => p.text())).toEqual(paragraphsZh);
  });

  it("interleaves source and zh in bilingual mode, zh styled as translation", () => {
    const w = mount(ArticleBody, {
      props: { paragraphs, paragraphsZh, mode: "bilingual" },
    });
    const texts = w.findAll("p").map((p) => p.text());
    expect(texts).toEqual(["First source para.", "第一段。", "Second source para.", "第二段。"]);
    expect(w.findAll("p")[1].classes()).toContain("zh-trans");
    expect(w.findAll("p")[0].classes()).not.toContain("zh-trans");
  });

  it("falls back to source when zh requested but missing", () => {
    const w = mount(ArticleBody, {
      props: { paragraphs, paragraphsZh: null, mode: "zh" },
    });
    expect(w.findAll("p").map((p) => p.text())).toEqual(paragraphs);
  });
});
