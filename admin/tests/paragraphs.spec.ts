import { describe, expect, it } from "vitest";

import { joinParagraphs, splitParagraphs } from "../src/utils/paragraphs";

describe("splitParagraphs", () => {
  it("splits on blank lines and trims", () => {
    expect(splitParagraphs("First para.\n\nSecond para.\n\n\nThird para.")).toEqual([
      "First para.",
      "Second para.",
      "Third para.",
    ]);
  });

  it("drops whitespace-only segments", () => {
    expect(splitParagraphs("A\n\n   \n\nB")).toEqual(["A", "B"]);
  });

  it("normalizes CRLF", () => {
    expect(splitParagraphs("A\r\n\r\nB")).toEqual(["A", "B"]);
  });

  it("returns empty array for empty input", () => {
    expect(splitParagraphs("")).toEqual([]);
    expect(splitParagraphs("   ")).toEqual([]);
  });
});

describe("joinParagraphs", () => {
  it("joins with blank lines and round-trips", () => {
    const paragraphs = ["第一段。", "第二段。"];
    expect(splitParagraphs(joinParagraphs(paragraphs))).toEqual(paragraphs);
  });

  it("handles null and undefined", () => {
    expect(joinParagraphs(null)).toBe("");
    expect(joinParagraphs(undefined)).toBe("");
  });
});
