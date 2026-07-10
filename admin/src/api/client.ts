import axios from "axios";
import { ElMessage } from "element-plus";

export const TOKEN_KEY = "zoko-admin-token";
export const USER_KEY = "zoko-admin-user";

export const api = axios.create({ baseURL: "/api/admin" });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function redirectToLogin(): void {
  if (window.location.pathname.startsWith("/admin/login")) return;
  const current = window.location.pathname.replace(/^\/admin/, "") + window.location.search;
  window.location.href = "/admin/login?redirect=" + encodeURIComponent(current || "/articles");
}

export function handleApiError(
  error: unknown,
  redirect: () => void = redirectToLogin,
): Promise<never> {
  const err = error as { response?: { status?: number; data?: { detail?: unknown } } };
  const status = err.response?.status;
  const detail = err.response?.data?.detail;
  if (status === 401) {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    redirect();
  } else if (status === 409 || status === 422) {
    ElMessage.warning(typeof detail === "string" ? detail : "数据校验失败");
  } else if (status !== undefined) {
    ElMessage.error("请求失败，请重试");
    console.error(error);
  } else {
    ElMessage.error("网络错误，请检查后端服务");
    console.error(error);
  }
  return Promise.reject(error);
}

api.interceptors.response.use((resp) => resp, (error) => handleApiError(error));
