import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import ContentLangToggle from "../src/components/ContentLangToggle.vue";

describe("ContentLangToggle", () => {
  it("shows EN labels for English sources", () => {
    const w = mount(ContentLangToggle, {
      props: { sourceLang: "en", modelValue: "source", hasTranslation: true },
    });
    expect(w.findAll(".seg").map((s) => s.text())).toEqual(["EN", "中", "双语"]);
  });

  it("shows FR labels for French sources", () => {
    const w = mount(ContentLangToggle, {
      props: { sourceLang: "fr", modelValue: "source", hasTranslation: true },
    });
    expect(w.findAll(".seg")[0].text()).toBe("FR");
  });

  it("hides zh segments when there is no translation", () => {
    const w = mount(ContentLangToggle, {
      props: { sourceLang: "en", modelValue: "source", hasTranslation: false },
    });
    expect(w.findAll(".seg")).toHaveLength(1);
  });

  it("emits the selected mode and marks it active", async () => {
    const w = mount(ContentLangToggle, {
      props: { sourceLang: "en", modelValue: "source", hasTranslation: true },
    });
    await w.findAll(".seg")[2].trigger("click");
    expect(w.emitted("update:modelValue")![0]).toEqual(["bilingual"]);
    await w.setProps({ modelValue: "bilingual" });
    expect(w.findAll(".seg")[2].classes()).toContain("active");
  });
});
