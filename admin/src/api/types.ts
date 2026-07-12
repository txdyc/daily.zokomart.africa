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

// ── Logistics types (Plan 5) ──

export interface LgDriver {
  id: number;
  user_id: number;
  phone: string;
  full_name: string;
  gender: string;
  date_of_birth: string;
  ghana_card_number: string;
  ghana_card_front_id: string;
  ghana_card_back_id: string;
  licence_number: string;
  licence_class: string;
  licence_expiry: string;
  licence_photo_id: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
  status: string;
  availability: string;
  review_remark: string;
}

export interface LgVehicle {
  id: number;
  driver_id: number;
  plate_number: string;
  brand_model: string;
  vehicle_type: string;
  year: number;
  vin: string;
  cargo_length_m: number;
  cargo_width_m: number;
  cargo_height_m: number;
  max_load_kg: number;
  max_volume_m3: number;
  photo_front_id: string;
  photo_left_id: string;
  photo_right_id: string;
  photo_rear_id: string;
  photo_interior_id: string;
  reg_cert_id: string;
  roadworthy_cert_id: string;
  roadworthy_expiry: string;
  insurance_cert_id: string;
  insurance_expiry: string;
  status: string;
  review_remark: string;
}

export interface LgRoute {
  id: number;
  driver_id: number;
  origin_region: string;
  origin_town: string;
  dest_region: string;
  dest_town: string;
  via_towns: string[];
  frequency: string;
  weekdays: number[];
  once_date: string | null;
  depart_time: string;
  est_duration_hours: number;
  default_vehicle_id: number;
  cargo_types: string[];
  prohibited_notes: string;
  rate_per_ton: number | null;
  rate_per_m3: number | null;
  min_charge: number | null;
  negotiable: boolean;
  status: string;
  review_remark: string;
}

export interface LgOrderParty {
  full_name?: string;
  plate_number?: string;
  phone?: string;
  contact_name?: string;
  contact_phone?: string;
  pickup_details?: string;
  delivery_details?: string;
  consignee_name?: string;
  consignee_phone?: string;
}

export interface LgOrderRemark {
  author: string;
  body: string;
  created_at: string;
}

export interface LgOrder {
  id: number;
  status: string;
  trip_id: number;
  depart_date: string;
  depart_time: string;
  origin_town: string;
  dest_town: string;
  cargo_name: string;
  cargo_category: string;
  packaging: string;
  pieces: number;
  weight_kg: number;
  volume_m3: number;
  fragile: boolean;
  needs_loading: boolean;
  needs_pickup: boolean;
  pickup_window: string;
  remarks: string;
  photo_ids: string[];
  freight_ghs: number | null;
  commission_ghs: number | null;
  pickup_time: string;
  cancel_reason: string;
  created_at: string;
  pickup_town: string;
  delivery_town: string;
  driver: LgOrderParty | null;
  shipper: LgOrderParty | null;
  remarks_timeline?: LgOrderRemark[];
  reject_count?: number;
}

export interface LgCommission {
  id: number;
  order_id: number;
  driver_id: number;
  freight_ghs: number;
  rate: number;
  amount_ghs: number;
  status: string;
  method: string;
  reference: string;
  note: string;
  settled_by: string;
}

export interface StatsOverview {
  drivers: Record<string, number>;
  vehicles: number;
  routes_active: number;
  trips_upcoming: number;
  orders: Record<string, number>;
  orders_total: number;
  gmv_ghs: number;
  commission: { pending_ghs: number; settled_ghs: number };
  top_lanes: { lane: string; orders: number }[];
  completion_rate: number;
  cancellation_rate: number;
  capacity_utilization: number;
}

export interface Staff {
  id: number;
  username: string;
  role: string;
}

export interface BlacklistEntry {
  id: number;
  value_type: string;
  value: string;
  reason: string;
  created_by: string;
}

export interface LgConfig {
  lg_commission_rate: string;
  lg_payment_instructions: string;
  lg_sms_provider: string;
  lg_sms_sender_id: string;
  lg_sms_api_key: string;
}

export const LG_DRIVER_STATUSES = [
  { value: "draft", label: "草稿", tag: "info" },
  { value: "pending_review", label: "待审核", tag: "warning" },
  { value: "approved", label: "已通过", tag: "success" },
  { value: "rejected", label: "已驳回", tag: "danger" },
  { value: "frozen", label: "已冻结", tag: "danger" },
] as const;

export const LG_VEHICLE_STATUSES = [
  { value: "pending_review", label: "待审核", tag: "warning" },
  { value: "approved", label: "已通过", tag: "success" },
  { value: "rejected", label: "已驳回", tag: "danger" },
  { value: "deactivated", label: "已停用", tag: "info" },
] as const;

export const LG_ROUTE_STATUSES = [
  { value: "pending_review", label: "待审核", tag: "warning" },
  { value: "approved", label: "已通过", tag: "success" },
  { value: "rejected", label: "已驳回", tag: "danger" },
  { value: "suspended", label: "已暂停", tag: "info" },
] as const;

export const LG_ORDER_STATUSES = [
  { value: "submitted", label: "待处理", tag: "warning" },
  { value: "price_confirmed", label: "已报价", tag: "primary" },
  { value: "awaiting_pickup", label: "待取货", tag: "primary" },
  { value: "in_transit", label: "运输中", tag: "primary" },
  { value: "delivered", label: "已送达", tag: "success" },
  { value: "completed", label: "已完成", tag: "success" },
  { value: "cancelled", label: "已取消", tag: "info" },
  { value: "exception_closed", label: "异常关闭", tag: "danger" },
] as const;

export const LG_COMMISSION_STATUSES = [
  { value: "pending", label: "待结算", tag: "warning" },
  { value: "settled", label: "已结算", tag: "success" },
  { value: "waived", label: "已豁免", tag: "info" },
] as const;
