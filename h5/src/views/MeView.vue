<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import TabBar from "../components/TabBar.vue";
import { useAuthStore } from "../stores/auth";

const { t } = useI18n();
const auth = useAuthStore();
const router = useRouter();

function signOut() {
  auth.signOut();
}
</script>

<template>
  <div class="page">
    <header class="hero">
      <h1>{{ t("lg.me.account") }}</h1>
      <p v-if="auth.loggedIn" class="phone">{{ auth.phone }}</p>
    </header>

    <div v-if="!auth.loggedIn" class="guest">
      <p>{{ t("lg.me.guest") }}</p>
      <button class="primary" @click="router.push('/me/login')">{{ t("lg.me.signIn") }}</button>
    </div>

    <nav v-else class="menu">
      <RouterLink class="row" to="/me/orders">{{ t("lg.me.myOrders") }}</RouterLink>
      <RouterLink class="row" to="/me/notifications">{{ t("lg.me.notifications") }}</RouterLink>
      <button class="row sign-out" @click="signOut">{{ t("lg.me.signOut") }}</button>
    </nav>

    <TabBar />
  </div>
</template>

<style scoped>
.page { min-height: 100vh; background: var(--surface); padding-bottom: 64px; }
.hero { background: var(--brand-700); color: #fff; padding: 28px 18px 22px; }
.hero h1 { font-size: 20px; font-weight: 600; }
.phone { margin-top: 4px; font-size: 13px; opacity: 0.85; }
.guest { padding: 40px 20px; text-align: center; color: var(--text-secondary); display: flex; flex-direction: column; gap: 16px; align-items: center; }
.primary { border: 0; border-radius: var(--radius-pill); background: var(--brand-500); color: #fff; padding: 10px 28px; font-size: 15px; }
.menu { margin-top: 10px; background: var(--bg); }
.row {
  display: block; width: 100%; text-align: left; padding: 15px 18px; font-size: 15px;
  color: var(--text-primary); text-decoration: none; border: 0; border-bottom: 1px solid var(--border); background: var(--bg);
}
.sign-out { color: #c0392b; }
</style>
