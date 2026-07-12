export interface AuthSession {
  access_token: string;
  token_type: string;
  user_id: number;
  phone: string;
}

export interface TripCard {
  trip_id: number;
  route_id: number;
  depart_date: string;
  depart_time: string;
  origin_region: string;
  origin_town: string;
  dest_region: string;
  dest_town: string;
  via_towns: string[];
  est_duration_hours: number;
  vehicle_type: string;
  brand_model: string;
  remaining_load_kg: number;
  remaining_volume_m3: number;
  rate_per_ton: number | null;
  rate_per_m3: number | null;
  min_charge: number | null;
  negotiable: boolean;
  cargo_types: string[];
}

export interface TripList {
  items: TripCard[];
  total: number;
  page: number;
  page_size: number;
}

export interface UpcomingTrip {
  trip_id: number;
  depart_date: string;
  depart_time: string;
  remaining_load_kg: number;
  remaining_volume_m3: number;
}

export interface RouteDetail {
  id: number;
  origin_region: string;
  origin_town: string;
  dest_region: string;
  dest_town: string;
  via_towns: string[];
  est_duration_hours: number;
  cargo_types: string[];
  prohibited_notes: string;
  rate_per_ton: number | null;
  rate_per_m3: number | null;
  min_charge: number | null;
  negotiable: boolean;
  vehicle: {
    vehicle_type: string;
    brand_model: string;
    max_load_kg: number;
    max_volume_m3: number;
    cargo_length_m: number;
    cargo_width_m: number;
    cargo_height_m: number;
  };
  upcoming_trips: UpcomingTrip[];
}

export interface OrderDraft {
  trip_id: number;
  contact_name: string;
  contact_phone: string;
  pickup_region: string;
  pickup_town: string;
  pickup_details: string;
  delivery_region: string;
  delivery_town: string;
  delivery_details: string;
  consignee_name: string;
  consignee_phone: string;
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
}

export interface OrderParty {
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

export interface OrderView {
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
  driver: OrderParty | null;
  shipper: OrderParty | null;
}

export interface OrderList {
  items: OrderView[];
  total: number;
  page: number;
  page_size: number;
}

export interface NotificationItem {
  id: number;
  kind: string;
  title: string;
  body: string;
  read: boolean;
  created_at: string;
}

export interface NotificationList {
  items: NotificationItem[];
  total: number;
  unread: number;
  page: number;
  page_size: number;
}

export interface UploadResult {
  id: string;
  url: string;
}
