import { defineStore } from "pinia";

import { TOKEN_KEY, USER_KEY } from "../api/client";
import { login as apiLogin } from "../api/endpoints";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) ?? "",
    username: localStorage.getItem(USER_KEY) ?? "",
  }),
  getters: {
    isLoggedIn: (state) => state.token.length > 0,
  },
  actions: {
    async login(username: string, password: string) {
      const { access_token } = await apiLogin(username, password);
      this.token = access_token;
      this.username = username;
      localStorage.setItem(TOKEN_KEY, access_token);
      localStorage.setItem(USER_KEY, username);
    },
    logout() {
      this.token = "";
      this.username = "";
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    },
  },
});
