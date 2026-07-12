import { defineStore } from "pinia";

import { browseTrips, type BrowseParams } from "../api/lg";
import type { TripCard } from "../api/lgTypes";

const PAGE_SIZE = 20;

interface Filters {
  origin_town: string;
  dest_town: string;
  date: string;
}

export const useLgFeedStore = defineStore("lgFeed", {
  state: () => ({
    items: [] as TripCard[],
    page: 0,
    total: 0,
    loading: false, // bound to van-list v-model:loading
    inFlight: false, // real dedupe guard
    error: "",
    filters: { origin_town: "", dest_town: "", date: "" } as Filters,
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
      if (this.inFlight) return;
      this.inFlight = true;
      this.loading = true;
      this.error = "";
      try {
        const params: BrowseParams = { page: this.page + 1, page_size: PAGE_SIZE };
        if (this.filters.origin_town) params.origin_town = this.filters.origin_town;
        if (this.filters.dest_town) params.dest_town = this.filters.dest_town;
        if (this.filters.date) params.date = this.filters.date;
        const data = await browseTrips(params);
        this.page = data.page;
        this.total = data.total;
        this.items.push(...data.items);
      } catch (e) {
        this.error = e instanceof Error ? e.message : String(e);
      } finally {
        this.inFlight = false;
        this.loading = false;
      }
    },
  },
});
