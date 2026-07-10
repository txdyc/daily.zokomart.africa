import { createRouter, createWebHistory } from "vue-router";

import { TOKEN_KEY } from "./api/client";

export const router = createRouter({
  history: createWebHistory("/admin/"),
  routes: [
    { path: "/login", name: "login", component: () => import("./views/LoginView.vue") },
    {
      path: "/",
      component: () => import("./layout/AdminLayout.vue"),
      children: [
        { path: "", redirect: "/articles" },
        { path: "articles", name: "articles", component: () => import("./views/ArticlesView.vue") },
        { path: "sites", name: "sites", component: () => import("./views/SitesView.vue") },
        { path: "pipeline", name: "pipeline", component: () => import("./views/PipelineView.vue") },
        { path: "settings", name: "settings", component: () => import("./views/SettingsView.vue") },
      ],
    },
  ],
});

router.beforeEach((to) => {
  if (to.name !== "login" && !localStorage.getItem(TOKEN_KEY)) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
});
