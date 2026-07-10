import { defineStore } from "pinia";

import { listArticles } from "../api/articles";
import type { ArticleCard } from "../api/types";

const PAGE_SIZE = 20;

export const useFeedStore = defineStore("feed", {
  state: () => ({
    items: [] as ArticleCard[],
    page: 0,
    total: 0,
    keyword: "",
    country: "",
    loading: false,
    error: "",
  }),
  getters: {
    finished: (s) => s.page > 0 && s.items.length >= s.total,
  },
  actions: {
    async refresh() {
      this.page = 0;
      this.total = 0;
      this.items = [];
      await this.loadMore();
    },
    async loadMore() {
      if (this.loading) return;
      this.loading = true;
      this.error = "";
      try {
        const data = await listArticles({
          page: this.page + 1,
          page_size: PAGE_SIZE,
          search: this.keyword || undefined,
          country: this.country || undefined,
        });
        this.page = data.page;
        this.total = data.total;
        this.items.push(...data.items);
      } catch (e) {
        this.error = e instanceof Error ? e.message : String(e);
      } finally {
        this.loading = false;
      }
    },
    async search(keyword: string) {
      this.keyword = keyword.trim();
      await this.refresh();
    },
    async setCountry(code: string) {
      this.country = code;
      await this.refresh();
    },
  },
});
