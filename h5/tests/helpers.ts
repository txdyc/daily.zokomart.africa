import { createPinia, setActivePinia } from "pinia";
import { createI18n } from "vue-i18n";
import { createRouter, createWebHistory } from "vue-router";

import en from "../src/i18n/en";
import zh from "../src/i18n/zh";

export function freshPinia() {
  const pinia = createPinia();
  setActivePinia(pinia);
  return pinia;
}

export function testI18n(locale: "zh" | "en" = "zh") {
  return createI18n({ legacy: false, locale, fallbackLocale: "zh", messages: { zh, en } });
}

export function testRouter() {
  return createRouter({
    history: createWebHistory(),
    routes: [
      { path: "/", name: "news", component: { template: "<div />" } },
      { path: "/lg", name: "logistics", component: { template: "<div />" } },
      { path: "/me", name: "me", component: { template: "<div />" } },
      { path: "/me/login", name: "login", component: { template: "<div />" } },
      { path: "/me/orders", name: "my-orders", component: { template: "<div />" } },
      { path: "/me/orders/:id", name: "order-detail", component: { template: "<div />" } },
      { path: "/me/notifications", name: "notifications", component: { template: "<div />" } },
      { path: "/lg/trip/:id", name: "trip", component: { template: "<div />" } },
      { path: "/lg/order/new/:tripId", name: "order-new", component: { template: "<div />" } },
    ],
  });
}

export function setLgToken(token = "test-token") {
  localStorage.setItem("lg-token", token);
}
