<template>
  <el-container class="layout">
    <el-aside width="200px" class="aside">
      <div class="logo">ZokoDaily</div>
      <el-menu :default-active="route.path" router class="menu">
        <el-menu-item index="/articles">新闻管理</el-menu-item>
        <el-menu-item index="/sites">国家与站点</el-menu-item>
        <el-menu-item index="/pipeline">抓取与翻译</el-menu-item>
        <el-menu-item index="/settings">系统设置</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="user">{{ auth.username }}</span>
        <el-button link type="primary" @click="logout">退出登录</el-button>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

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
.main {
  background: #f5f7fa;
}
</style>
