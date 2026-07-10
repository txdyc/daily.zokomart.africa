import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ArticleCard, Paginated } from "../src/api/types";
import { useFeedStore } from "../src/stores/feed";
import { freshPinia } from "./helpers";

vi.mock("../src/api/articles", () => ({ listArticles: vi.fn() }));
import { listArticles } from "../src/api/articles";

const mockList = vi.mocked(listArticles);

function card(id: number): ArticleCard {
  return {
    id,
    title: `Story ${id}`,
    title_zh: `新闻 ${id}`,
    main_image_url: null,
    published_at: "2026-07-10T08:00:00",
    category: "business",
    country: { code: "GH", name_en: "Ghana", name_zh: "加纳", flag_emoji: "🇬🇭" },
  };
}

function page(items: ArticleCard[], pageNo: number, total: number): Paginated<ArticleCard> {
  return { items, total, page: pageNo, page_size: 2 };
}

describe("feed store", () => {
  beforeEach(() => {
    freshPinia();
    mockList.mockReset();
  });

  it("refresh loads page 1", async () => {
    mockList.mockResolvedValueOnce(page([card(1), card(2)], 1, 3));
    const feed = useFeedStore();
    await feed.refresh();
    expect(mockList).toHaveBeenCalledWith({ page: 1, page_size: 20, search: undefined });
    expect(feed.items).toHaveLength(2);
    expect(feed.finished).toBe(false);
  });

  it("loadMore appends and finishes at total", async () => {
    mockList
      .mockResolvedValueOnce(page([card(1), card(2)], 1, 3))
      .mockResolvedValueOnce(page([card(3)], 2, 3));
    const feed = useFeedStore();
    await feed.refresh();
    await feed.loadMore();
    expect(feed.items.map((a) => a.id)).toEqual([1, 2, 3]);
    expect(feed.finished).toBe(true);
  });

  it("search resets and passes the keyword", async () => {
    mockList.mockResolvedValue(page([card(9)], 1, 1));
    const feed = useFeedStore();
    await feed.search("  外汇  ");
    expect(mockList).toHaveBeenCalledWith({ page: 1, page_size: 20, search: "外汇" });
    expect(feed.items.map((a) => a.id)).toEqual([9]);
  });

  it("records error message on failure", async () => {
    mockList.mockRejectedValueOnce(new Error("Network error"));
    const feed = useFeedStore();
    await feed.refresh();
    expect(feed.error).toBe("Network error");
    expect(feed.loading).toBe(false);
  });
});
