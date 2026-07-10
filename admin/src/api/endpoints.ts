import axios from "axios";

import { api } from "./client";
import type {
  AiConfig,
  ArticleAdmin,
  Country,
  CrawlRun,
  Paginated,
  Site,
  SiteIn,
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
