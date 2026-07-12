import { defineStore } from "pinia";

import { ROLE_KEY, TOKEN_KEY, USER_KEY } from "../api/client";
import { login as apiLogin, me as apiMe } from "../api/endpoints";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) ?? "",
    username: localStorage.getItem(USER_KEY) ?? "",
    role: localStorage.getItem(ROLE_KEY) ?? "",
  }),
  getters: {
    isLoggedIn: (state) => state.token.length > 0,
  },
  actions: {
    async login(username: string, password: string) {
      const { access_token } = await apiLogin(username, password);
      this.token = access_token;
      localStorage.setItem(TOKEN_KEY, access_token);
      // Fetch role + canonical username from backend
      try {
        const info = await apiMe();
        this.username = info.username;
        this.role = info.role;
      } catch {
        this.username = username;
        this.role = "admin";
      }
      localStorage.setItem(USER_KEY, this.username);
      localStorage.setItem(ROLE_KEY, this.role);
    },
    logout() {
      this.token = "";
      this.username = "";
      this.role = "";
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      localStorage.removeItem(ROLE_KEY);
    },
  },
});
