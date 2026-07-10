import axios from "axios";

export const api = axios.create({ baseURL: "/api/public", timeout: 15000 });

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const message =
      error?.response?.data?.detail ?? error?.message ?? "Network error";
    return Promise.reject(new Error(String(message)));
  },
);
