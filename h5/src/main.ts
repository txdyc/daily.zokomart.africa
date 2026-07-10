import { createPinia } from "pinia";
import { List, Popup, PullRefresh, Swipe, SwipeItem } from "vant";
import { createApp } from "vue";
import "vant/lib/index.css";

import App from "./App.vue";
import { i18n } from "./i18n";
import { router } from "./router";
import "./styles/tokens.css";
import "./styles/base.css";

createApp(App)
  .use(createPinia())
  .use(router)
  .use(i18n)
  .use(Swipe)
  .use(SwipeItem)
  .use(PullRefresh)
  .use(List)
  .use(Popup)
  .mount("#app");
