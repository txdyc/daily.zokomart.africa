import axios from "axios";

import { api } from "./client";
import type {
  AiConfig,
  ArticleAdmin,
  BlacklistEntry,
  Country,
  CrawlRun,
  LgCommission,
  LgConfig,
  LgDriver,
  LgOrder,
  LgOrderRemark,
  LgRoute,
  LgVehicle,
  Paginated,
  Site,
  SiteIn,
  Staff,
  StatsOverview,
} from "./types";

export async function login(username: string, password: string) {
  const { data } = await axios.post<{ access_token: string }>(
    "/api/admin/auth/login",
    { username, password },
  );
  return data;
}

export async function listCountries(): Promise<Country[]> {
  return (await api.get<Country[]>("/countries")).data;
}
export async function createCountry(body: Omit<Country, "id">): Promise<Country> {
  return (await api.post<Country>("/countries", body)).data;
}
export async function updateCountry(id: number, body: Omit<Country, "id">): Promise<Country> {
  return (await api.put<Country>(`/countries/${id}`, body)).data;
}
export async function deleteCountry(id: number): Promise<void> {
  await api.delete(`/countries/${id}`);
}

export async function listSites(): Promise<Site[]> {
  return (await api.get<Site[]>("/sites")).data;
}
export async function createSite(body: SiteIn): Promise<Site> {
  return (await api.post<Site>("/sites", body)).data;
}
export async function updateSite(id: number, body: SiteIn): Promise<Site> {
  return (await api.put<Site>(`/sites/${id}`, body)).data;
}
export async function deleteSite(id: number): Promise<void> {
  await api.delete(`/sites/${id}`);
}
export async function triggerCrawl(siteId: number): Promise<{ crawl_run_id: number }> {
  return (await api.post<{ crawl_run_id: number }>(`/sites/${siteId}/crawl`)).data;
}

export interface ArticleFilters {
  status?: string;
  country?: string;
  site_id?: number;
  page?: number;
  page_size?: number;
}
export async function listArticles(filters: ArticleFilters): Promise<Paginated<ArticleAdmin>> {
  return (await api.get<Paginated<ArticleAdmin>>("/articles", { params: filters })).data;
}
export async function patchArticle(
  id: number,
  body: Partial<
    Pick<
      ArticleAdmin,
      "title" | "title_zh" | "category" | "main_image_url" | "paragraphs" | "paragraphs_zh" | "is_banner" | "status"
    >
  >,
): Promise<ArticleAdmin> {
  return (await api.patch<ArticleAdmin>(`/articles/${id}`, body)).data;
}
export async function retranslateArticle(id: number): Promise<ArticleAdmin> {
  return (await api.post<ArticleAdmin>(`/articles/${id}/retranslate`)).data;
}
export async function deleteArticle(id: number): Promise<void> {
  await api.delete(`/articles/${id}`);
}

export async function listCrawlRuns(params: {
  site_id?: number;
  page?: number;
  page_size?: number;
}): Promise<Paginated<CrawlRun>> {
  return (await api.get<Paginated<CrawlRun>>("/crawl-runs", { params })).data;
}

export async function getConfig(): Promise<AiConfig> {
  return (await api.get<AiConfig>("/config")).data;
}
export async function updateConfig(body: {
  ai_base_url?: string;
  ai_api_key?: string;
  ai_model?: string;
}): Promise<AiConfig> {
  return (await api.put<AiConfig>("/config", body)).data;
}
export interface TestTranslationResult {
  ok: boolean;
  title_zh?: string;
  paragraph_zh?: string;
  latency_ms?: number;
  error?: string;
}
export async function testTranslation(): Promise<TestTranslationResult> {
  return (await api.post<TestTranslationResult>("/config/test-translation")).data;
}

// ── Logistics admin endpoints (Plan 5) ──

export async function me(): Promise<{ username: string; role: string }> {
  return (await api.get<{ username: string; role: string }>("/auth/me")).data;
}

export async function lgStats(params?: {
  start?: string;
  end?: string;
}): Promise<StatsOverview> {
  return (await api.get<StatsOverview>("/lg/stats/overview", { params })).data;
}

export interface LgListParams {
  status?: string;
  page?: number;
  page_size?: number;
}

export async function lgDrivers(params: LgListParams): Promise<Paginated<LgDriver>> {
  return (await api.get<Paginated<LgDriver>>("/lg/drivers", { params })).data;
}
export async function lgDriver(id: number): Promise<LgDriver> {
  return (await api.get<LgDriver>(`/lg/drivers/${id}`)).data;
}
export async function lgReviewDriver(
  id: number,
  action: "approve" | "reject",
  reason: string,
): Promise<LgDriver> {
  return (await api.post<LgDriver>(`/lg/drivers/${id}/review`, { action, reason })).data;
}
export async function lgFreezeDriver(id: number, reason: string): Promise<LgDriver> {
  return (await api.post<LgDriver>(`/lg/drivers/${id}/freeze`, { reason })).data;
}
export async function lgUnfreezeDriver(id: number): Promise<LgDriver> {
  return (await api.post<LgDriver>(`/lg/drivers/${id}/unfreeze`)).data;
}

export async function lgVehicles(params: LgListParams): Promise<Paginated<LgVehicle>> {
  return (await api.get<Paginated<LgVehicle>>("/lg/vehicles", { params })).data;
}
export async function lgReviewVehicle(
  id: number,
  action: "approve" | "reject",
  reason: string,
): Promise<LgVehicle> {
  return (await api.post<LgVehicle>(`/lg/vehicles/${id}/review`, { action, reason })).data;
}

export async function lgRoutes(params: LgListParams): Promise<Paginated<LgRoute>> {
  return (await api.get<Paginated<LgRoute>>("/lg/routes", { params })).data;
}
export async function lgReviewRoute(
  id: number,
  action: "approve" | "reject",
  reason: string,
): Promise<LgRoute> {
  return (await api.post<LgRoute>(`/lg/routes/${id}/review`, { action, reason })).data;
}
export async function lgSuspendRoute(id: number, reason: string): Promise<LgRoute> {
  return (await api.post<LgRoute>(`/lg/routes/${id}/suspend`, { reason })).data;
}
export async function lgResumeRoute(id: number): Promise<LgRoute> {
  return (await api.post<LgRoute>(`/lg/routes/${id}/resume`)).data;
}

export async function lgOrders(params: LgListParams): Promise<Paginated<LgOrder>> {
  return (await api.get<Paginated<LgOrder>>("/lg/orders", { params })).data;
}
// Detail endpoint overwrites the shipper's `remarks` string with the CS
// timeline array; we reshape it to `remarks_timeline` for clean typing.
export async function lgOrder(id: number): Promise<LgOrder> {
  const raw = (
    await api.get<LgOrder & { remarks: LgOrderRemark[] | string; reject_count: number }>(
      `/lg/orders/${id}`,
    )
  ).data;
  const timeline = Array.isArray(raw.remarks) ? raw.remarks : [];
  return { ...raw, remarks: "", remarks_timeline: timeline, reject_count: raw.reject_count };
}
export async function lgConfirmPrice(
  id: number,
  body: {
    freight_ghs: number;
    pickup_time: string;
    commission_ghs?: number | null;
    override_reason?: string;
  },
): Promise<LgOrder> {
  return (await api.post<LgOrder>(`/lg/orders/${id}/confirm-price`, body)).data;
}
export async function lgReassign(id: number, tripId: number): Promise<LgOrder> {
  return (await api.post<LgOrder>(`/lg/orders/${id}/reassign`, { trip_id: tripId })).data;
}
export async function lgCancelOrder(id: number, reason: string): Promise<LgOrder> {
  return (await api.post<LgOrder>(`/lg/orders/${id}/cancel`, { reason })).data;
}
export async function lgExceptionClose(id: number, reason: string): Promise<LgOrder> {
  return (await api.post<LgOrder>(`/lg/orders/${id}/exception-close`, { reason })).data;
}
export async function lgCompleteOrder(id: number): Promise<LgOrder> {
  return (await api.post<LgOrder>(`/lg/orders/${id}/complete`)).data;
}
export async function lgAddRemark(id: number, body: string): Promise<{ ok: boolean }> {
  return (await api.post<{ ok: boolean }>(`/lg/orders/${id}/remarks`, { body })).data;
}

export async function lgCommissions(params: {
  status?: string;
  driver_id?: number;
  page?: number;
  page_size?: number;
}): Promise<Paginated<LgCommission>> {
  return (await api.get<Paginated<LgCommission>>("/lg/commissions", { params })).data;
}
export async function lgSettleCommission(
  id: number,
  method: string,
  reference: string,
): Promise<LgCommission> {
  return (await api.post<LgCommission>(`/lg/commissions/${id}/settle`, { method, reference })).data;
}
export async function lgWaiveCommission(id: number, reason: string): Promise<LgCommission> {
  return (await api.post<LgCommission>(`/lg/commissions/${id}/waive`, { reason })).data;
}

export async function lgConfig(): Promise<LgConfig> {
  return (await api.get<LgConfig>("/lg/config")).data;
}
export async function lgUpdateConfig(body: Partial<Record<keyof LgConfig, string>>): Promise<{ ok: boolean }> {
  return (await api.put<{ ok: boolean }>("/lg/config", body)).data;
}

export async function lgStaff(): Promise<Staff[]> {
  return (await api.get<Staff[]>("/lg/staff")).data;
}
export async function lgCreateStaff(body: {
  username: string;
  password: string;
  role: string;
}): Promise<Staff> {
  return (await api.post<Staff>("/lg/staff", body)).data;
}

export async function lgBlacklist(): Promise<BlacklistEntry[]> {
  return (await api.get<BlacklistEntry[]>("/lg/blacklist")).data;
}
export async function lgAddBlacklist(body: {
  value_type: string;
  value: string;
  reason: string;
}): Promise<BlacklistEntry> {
  return (await api.post<BlacklistEntry>("/lg/blacklist", body)).data;
}
export async function lgDeleteBlacklist(id: number): Promise<{ ok: boolean }> {
  return (await api.delete<{ ok: boolean }>(`/lg/blacklist/${id}`)).data;
}
