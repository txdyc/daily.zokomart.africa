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
        // Logistics (Plan 5)
        {
          path: "lg/dashboard", name: "lg-dashboard",
          component: () => import("./views/lg/LgDashboardView.vue"),
          meta: { roles: ["admin", "auditor", "cs"] },
        },
        {
          path: "lg/drivers", name: "lg-drivers",
          component: () => import("./views/lg/LgDriversView.vue"),
          meta: { roles: ["admin", "auditor"] },
        },
        {
          path: "lg/vehicles", name: "lg-vehicles",
          component: () => import("./views/lg/LgVehiclesView.vue"),
          meta: { roles: ["admin", "auditor"] },
        },
        {
          path: "lg/routes", name: "lg-routes",
          component: () => import("./views/lg/LgRoutesView.vue"),
          meta: { roles: ["admin", "auditor"] },
        },
        {
          path: "lg/orders", name: "lg-orders",
          component: () => import("./views/lg/LgOrdersView.vue"),
          meta: { roles: ["admin", "cs"] },
        },
        {
          path: "lg/commissions", name: "lg-commissions",
          component: () => import("./views/lg/LgCommissionsView.vue"),
          meta: { roles: ["admin", "cs"] },
        },
        {
          path: "lg/config", name: "lg-config",
          component: () => import("./views/lg/LgConfigView.vue"),
          meta: { roles: ["admin"] },
        },
        {
          path: "lg/staff", name: "lg-staff",
          component: () => import("./views/lg/LgStaffView.vue"),
          meta: { roles: ["admin"] },
        },
        {
          path: "lg/blacklist", name: "lg-blacklist",
          component: () => import("./views/lg/LgBlacklistView.vue"),
          meta: { roles: ["admin"] },
        },
      ],
    },
  ],
});

router.beforeEach((to) => {
  if (to.name !== "login" && !localStorage.getItem(TOKEN_KEY)) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  // Role guard: if the route has meta.roles, check the stored role
  const roles = to.meta?.roles as string[] | undefined;
  if (roles && roles.length > 0) {
    const role = localStorage.getItem("zoko-admin-role") ?? "";
    if (!roles.includes(role)) {
      return { name: "lg-dashboard" };
    }
  }
});
