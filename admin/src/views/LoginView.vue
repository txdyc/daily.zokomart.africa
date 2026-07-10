<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2>ZokoDaily 管理后台</h2>
      <el-form @submit.prevent="submit">
        <el-form-item>
          <el-input v-model="username" placeholder="用户名" autofocus />
        </el-form-item>
        <el-form-item>
          <el-input v-model="password" type="password" placeholder="密码" show-password />
        </el-form-item>
        <el-alert
          v-if="error"
          :title="error"
          type="error"
          :closable="false"
          class="login-error"
        />
        <el-button
          type="primary"
          native-type="submit"
          :loading="loading"
          class="login-btn"
        >登录</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "../stores/auth";

const username = ref("");
const password = ref("");
const error = ref("");
const loading = ref(false);
const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

async function submit() {
  if (!username.value || !password.value) {
    error.value = "请输入用户名和密码";
    return;
  }
  error.value = "";
  loading.value = true;
  try {
    await auth.login(username.value, password.value);
    router.push((route.query.redirect as string) || "/articles");
  } catch (e) {
    const err = e as { response?: { data?: { detail?: string } } };
    error.value = err.response?.data?.detail ?? "登录失败，请重试";
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
}
.login-card {
  width: 360px;
}
h2 {
  text-align: center;
  margin: 0 0 24px;
  font-weight: 500;
}
.login-error {
  margin-bottom: 12px;
}
.login-btn {
  width: 100%;
}
</style>
