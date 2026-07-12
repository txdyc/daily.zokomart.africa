import { defineStore } from "pinia";

import { login, requestOtp } from "../api/lg";
import { LG_TOKEN_KEY } from "../api/lgClient";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: localStorage.getItem(LG_TOKEN_KEY) ?? "",
    phone: "",
    userId: 0,
  }),
  getters: {
    loggedIn: (s) => !!s.token,
  },
  actions: {
    async requestCode(phone: string) {
      await requestOtp(phone);
    },
    async signIn(phone: string, code: string) {
      const session = await login(phone, code);
      this.token = session.access_token;
      this.phone = session.phone;
      this.userId = session.user_id;
      localStorage.setItem(LG_TOKEN_KEY, session.access_token);
    },
    signOut() {
      this.token = "";
      this.phone = "";
      this.userId = 0;
      localStorage.removeItem(LG_TOKEN_KEY);
    },
  },
});
