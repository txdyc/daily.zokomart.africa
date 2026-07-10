export interface CountryInfo {
  code: string;
  name_en: string;
  name_zh: string;
  flag_emoji: string;
}

export interface ArticleCard {
  id: number;
  title: string;
  title_zh: string | null;
  main_image_url: string | null;
  published_at: string | null;
  category: string | null;
  country: CountryInfo;
}

export interface ArticleDetail extends ArticleCard {
  source_language: "en" | "fr";
  paragraphs: string[];
  paragraphs_zh: string[] | null;
  site: { name: string; url: string };
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export type ContentMode = "source" | "zh" | "bilingual";
