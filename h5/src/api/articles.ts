import { api } from "./client";
import type { ArticleCard, ArticleDetail, Paginated } from "./types";

export interface ListParams {
  page?: number;
  page_size?: number;
  search?: string;
  country?: string;
  category?: string;
}

export async function listArticles(params: ListParams): Promise<Paginated<ArticleCard>> {
  const { data } = await api.get<Paginated<ArticleCard>>("/articles", { params });
  return data;
}

export async function getBanner(): Promise<ArticleCard[]> {
  const { data } = await api.get<ArticleCard[]>("/articles/banner");
  return data;
}

export async function getArticle(id: number | string): Promise<ArticleDetail> {
  const { data } = await api.get<ArticleDetail>(`/articles/${id}`);
  return data;
}
