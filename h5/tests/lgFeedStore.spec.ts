import { beforeEach, describe, expect, it, vi } from "vitest";

import { useLgFeedStore } from "../src/stores/lgFeed";
import type { TripCard, TripList } from "../src/api/lgTypes";
import { freshPinia } from "./helpers";

vi.mock("../src/api/lg", () => ({ browseTrips: vi.fn() }));
import { browseTrips } from "../src/api/lg";
const mockBrowse = vi.mocked(browseTrips);

function trip(id: number): TripCard {
  return {
    trip_id: id, route_id: 1, depart_date: "2026-07-14", depart_time: "08:00",
    origin_region: "Greater Accra", origin_town: "Accra", dest_region: "Ashanti",
    dest_town: "Kumasi", via_towns: [], est_duration_hours: 6, vehicle_type: "box_truck",
    brand_model: "Kia K2700", remaining_load_kg: 2000, remaining_volume_m3: 10,
    rate_per_ton: 350, rate_per_m3: 60, min_charge: 80, negotiable: false, cargo_types: ["general"],
  };
}
function page(items: TripCard[], p: number, total: number): TripList {
  return { items, total, page: p, page_size: 20 };
}

describe("lgFeed store", () => {
  beforeEach(() => {
    freshPinia();
    mockBrowse.mockReset();
  });

  it("refresh loads page 1 with filters", async () => {
    mockBrowse.mockResolvedValueOnce(page([trip(1), trip(2)], 1, 3));
    const feed = useLgFeedStore();
    feed.filters.dest_town = "Kumasi";
    await feed.refresh();
    expect(mockBrowse).toHaveBeenCalledWith({ page: 1, page_size: 20, dest_town: "Kumasi" });
    expect(feed.items).toHaveLength(2);
    expect(feed.finished).toBe(false);
  });

  it("loadMore appends and finishes at total", async () => {
    mockBrowse
      .mockResolvedValueOnce(page([trip(1), trip(2)], 1, 3))
      .mockResolvedValueOnce(page([trip(3)], 2, 3));
    const feed = useLgFeedStore();
    await feed.refresh();
    await feed.loadMore();
    expect(feed.items.map((t) => t.trip_id)).toEqual([1, 2, 3]);
    expect(feed.finished).toBe(true);
  });

  it("guards against concurrent loads via inFlight, not the van-list flag", async () => {
    mockBrowse.mockResolvedValueOnce(page([trip(1)], 1, 1));
    const feed = useLgFeedStore();
    feed.loading = true; // van-list pre-sets this before emitting @load
    await feed.loadMore();
    expect(mockBrowse).toHaveBeenCalledTimes(1);
    expect(feed.items).toHaveLength(1);
    expect(feed.loading).toBe(false);
  });
});
