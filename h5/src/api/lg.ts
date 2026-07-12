import { lgApi } from "./lgClient";
import type {
  AuthSession,
  NotificationList,
  OrderDraft,
  OrderList,
  OrderView,
  RouteDetail,
  TripList,
  UploadResult,
} from "./lgTypes";

export interface BrowseParams {
  origin_town?: string;
  dest_town?: string;
  origin_region?: string;
  dest_region?: string;
  date?: string;
  page?: number;
  page_size?: number;
}

export async function requestOtp(phone: string): Promise<{ ok: boolean }> {
  const { data } = await lgApi.post("/auth/request-otp", { phone });
  return data;
}

export async function login(phone: string, code: string): Promise<AuthSession> {
  const { data } = await lgApi.post<AuthSession>("/auth/login", { phone, code });
  return data;
}

export async function me(): Promise<{ id: number; phone: string }> {
  const { data } = await lgApi.get("/auth/me");
  return data;
}

export async function browseTrips(params: BrowseParams): Promise<TripList> {
  const { data } = await lgApi.get<TripList>("/trips", { params });
  return data;
}

export async function routeDetail(id: number | string): Promise<RouteDetail> {
  const { data } = await lgApi.get<RouteDetail>(`/routes/${id}`);
  return data;
}

export async function uploadImage(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await lgApi.post<UploadResult>("/uploads", form);
  return data;
}

export async function submitOrder(draft: OrderDraft): Promise<OrderView> {
  const { data } = await lgApi.post<OrderView>("/orders", draft);
  return data;
}

export async function myOrders(page = 1): Promise<OrderList> {
  const { data } = await lgApi.get<OrderList>("/orders/mine", { params: { page } });
  return data;
}

export async function orderDetail(id: number | string): Promise<OrderView> {
  const { data } = await lgApi.get<OrderView>(`/orders/${id}`);
  return data;
}

export async function cancelOrder(id: number | string, reason: string): Promise<OrderView> {
  const { data } = await lgApi.post<OrderView>(`/orders/${id}/cancel`, { reason });
  return data;
}

export async function listNotifications(page = 1): Promise<NotificationList> {
  const { data } = await lgApi.get<NotificationList>("/notifications", { params: { page } });
  return data;
}

export async function markNotificationRead(id: number): Promise<void> {
  await lgApi.post(`/notifications/${id}/read`);
}
