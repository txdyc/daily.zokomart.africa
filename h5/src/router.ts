import { createRouter, createWebHistory } from "vue-router";

import { useAuthStore } from "./stores/auth";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "news", component: () => import("./views/HomeView.vue") },
    { path: "/article/:id", name: "article", component: () => import("./views/ArticleView.vue") },
    { path: "/lg", name: "logistics", component: () => import("./views/LogisticsView.vue") },
    { path: "/lg/trip/:id", name: "trip", component: () => import("./views/TripDetailView.vue") },
    {
      path: "/lg/order/new/:tripId",
      name: "order-new",
      component: () => import("./views/OrderFormView.vue"),
      meta: { requiresAuth: true },
    },
    { path: "/me", name: "me", component: () => import("./views/MeView.vue") },
    { path: "/me/login", name: "login", component: () => import("./views/LoginView.vue") },
    {
      path: "/me/orders",
      name: "my-orders",
      component: () => import("./views/MyOrdersView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/me/orders/:id",
      name: "order-detail",
      component: () => import("./views/OrderDetailView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/me/notifications",
      name: "notifications",
      component: () => import("./views/NotificationsView.vue"),
      meta: { requiresAuth: true },
    },
  ],
});

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !useAuthStore().loggedIn) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
});
