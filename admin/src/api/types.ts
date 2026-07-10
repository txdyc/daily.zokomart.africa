export interface Country {
  id: number;
  code: string;
  name_en: string;
  name_zh: string;
  flag_emoji: string;
  tier: number;
  enabled: boolean;
}

export interface Site {
  id: number;
  country_id: number;
  name: string;
  base_url: string;
  language: "en" | "fr";
  discovery_method: "rss" | "listing";
  feed_url: string | null;
  listing_url: string | null;
  listing_selector: string | null;
  title_selector: string | null;
  body_selector: string | null;
  image_selector: string | null;
  date_selector: string | null;
  tier: number;
  enabled: boolean;
  last_crawl_at: string | null;
  last_crawl_status: string | null;
  country: Country | null;
}

export type SiteIn = Omit<Site, "id" | "last_crawl_at" | "last_crawl_status" | "country">;

export interface ArticleAdmin {
  id: number;
  site_id: number;
  site_name: string;
  country_code: string;
  source_url: string;
  source_language: string;
  title: string;
  title_zh: string | null;
  category: string | null;
  main_image_url: string | null;
  published_at: string | null;
  paragraphs: string[];
  paragraphs_zh: string[] | null;
  status: string;
  translation_error: string | null;
  is_banner: boolean;
  created_at: string;
}

export interface CrawlRun {
  id: number;
  site_id: number;
  site_name: string;
  started_at: string | null;
  finished_at: string | null;
  status: string;
  articles_found: number;
  articles_new: number;
  error: string | null;
}

export interface AiConfig {
  ai_base_url: string;
  ai_api_key_masked: string;
  ai_model: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export const ARTICLE_STATUSES = [
  { value: "pending_translation", label: "待翻译", tag: "warning" },
  { value: "published", label: "已发布", tag: "success" },
  { value: "translation_failed", label: "翻译失败", tag: "danger" },
  { value: "hidden", label: "已隐藏", tag: "info" },
] as const;

export const CATEGORIES = [
  { value: "politics", label: "政治" },
  { value: "business", label: "商业" },
  { value: "sports", label: "体育" },
  { value: "entertainment", label: "娱乐" },
  { value: "society", label: "社会" },
  { value: "technology", label: "科技" },
  { value: "health", label: "健康" },
] as const;
