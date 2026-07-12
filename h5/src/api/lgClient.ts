import axios from "axios";

export const LG_TOKEN_KEY = "lg-token";

export const lgApi = axios.create({ baseURL: "/api/lg", timeout: 15000 });

lgApi.interceptors.request.use((config) => {
  const token = localStorage.getItem(LG_TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

lgApi.interceptors.response.use(
  (resp) => resp,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem(LG_TOKEN_KEY);
      window.dispatchEvent(new Event("lg-unauthorized"));
    }
    const message = error?.response?.data?.detail ?? error?.message ?? "Network error";
    return Promise.reject(new Error(String(message)));
  },
);
