<template>
  <el-container class="layout">
    <el-aside width="200px" class="aside">
      <div class="logo">ZokoDaily</div>
      <el-menu :default-active="route.path" router class="menu">
        <el-menu-item index="/articles">新闻管理</el-menu-item>
        <el-menu-item index="/sites">国家与站点</el-menu-item>
        <el-menu-item index="/pipeline">抓取与翻译</el-menu-item>
        <el-menu-item index="/settings">系统设置</el-menu-item>
        <el-sub-menu v-if="lgItems.length" index="lg">
          <template #title>物流</template>
          <el-menu-item
            v-for="item in lgItems"
            :key="item.path"
            :index="item.path"
          >{{ item.label }}</el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="user">{{ auth.username }}</span>
        <el-tag v-if="auth.role" size="small" type="info" class="role-tag">{{ auth.role }}</el-tag>
        <el-button link type="primary" @click="logout">退出登录</el-button>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

interface MenuItem {
  path: string;
  label: string;
  roles: string[];
}

const ALL_LG_ITEMS: MenuItem[] = [
  { path: "/lg/dashboard", label: "物流看板", roles: ["admin", "auditor", "cs"] },
  { path: "/lg/drivers", label: "司机审核", roles: ["admin", "auditor"] },
  { path: "/lg/vehicles", label: "车辆审核", roles: ["admin", "auditor"] },
  { path: "/lg/routes", label: "线路审核", roles: ["admin", "auditor"] },
  { path: "/lg/orders", label: "订单工作台", roles: ["admin", "cs"] },
  { path: "/lg/commissions", label: "佣金结算", roles: ["admin", "cs"] },
  { path: "/lg/config", label: "物流设置", roles: ["admin"] },
  { path: "/lg/staff", label: "员工管理", roles: ["admin"] },
  { path: "/lg/blacklist", label: "黑名单", roles: ["admin"] },
];

const lgItems = computed(() =>
  ALL_LG_ITEMS.filter((item) => item.roles.includes(auth.role)),
);

function logout() {
  auth.logout();
  router.push("/login");
}
</script>

<style scoped>
.layout {
  min-height: 100vh;
}
.aside {
  border-right: 1px solid #e4e7ed;
  background: #fff;
}
.logo {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 500;
  color: #1d9e75;
}
.menu {
  border-right: none;
}
.header {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  border-bottom: 1px solid #e4e7ed;
  background: #fff;
}
.user {
  color: #606266;
  font-size: 14px;
}
.role-tag {
  text-transform: uppercase;
}
.main {
  background: #f5f7fa;
}
</style>
