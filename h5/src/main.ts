import { createPinia } from "pinia";
import { List, Popup, PullRefresh, Swipe, SwipeItem, Tab, Tabs } from "vant";
import { createApp } from "vue";
import "vant/lib/index.css";

import App from "./App.vue";
import { i18n } from "./i18n";
import { router } from "./router";
import { useAuthStore } from "./stores/auth";
import "./styles/tokens.css";
import "./styles/base.css";

const app = createApp(App)
  .use(createPinia())
  .use(router)
  .use(i18n)
  .use(Swipe)
  .use(SwipeItem)
  .use(PullRefresh)
  .use(List)
  .use(Popup);

// A 401 from any /api/lg call clears the session and bounces to login.
window.addEventListener("lg-unauthorized", () => {
  useAuthStore().signOut();
  if (router.currentRoute.value.meta.requiresAuth) {
    router.replace({ name: "login", query: { redirect: router.currentRoute.value.fullPath } });
  }
});

app.mount("#app");
