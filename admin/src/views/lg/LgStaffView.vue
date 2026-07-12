<template>
  <div class="toolbar">
    <el-button type="primary" @click="openCreate">新增员工</el-button>
    <el-button :loading="loading" @click="load">刷新</el-button>
  </div>

  <el-table v-loading="loading" :data="rows">
    <el-table-column prop="id" label="ID" width="70" />
    <el-table-column prop="username" label="用户名" min-width="150" />
    <el-table-column label="角色" width="120">
      <template #default="{ row }">
        <el-tag :type="roleTag(row.role)">{{ roleLabel(row.role) }}</el-tag>
      </template>
    </el-table-column>
  </el-table>

  <el-dialog v-model="createDialog" title="新增员工" width="420px">
    <el-form label-width="90px">
      <el-form-item label="用户名">
        <el-input v-model="form.username" placeholder="登录用户名" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input v-model="form.password" type="password" show-password placeholder="初始密码" />
      </el-form-item>
      <el-form-item label="角色">
        <el-select v-model="form.role">
          <el-option value="admin" label="管理员 (admin)" />
          <el-option value="auditor" label="审核员 (auditor)" />
          <el-option value="cs" label="客服 (cs)" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="createDialog = false">取消</el-button>
      <el-button type="primary" :loading="acting" @click="submitCreate">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage } from "element-plus";
import { onMounted, reactive, ref } from "vue";

import { lgCreateStaff, lgStaff } from "../../api/endpoints";
import type { Staff } from "../../api/types";

const loading = ref(false);
const acting = ref(false);
const rows = ref<Staff[]>([]);

const createDialog = ref(false);
const form = reactive({ username: "", password: "", role: "cs" });

const ROLE_LABELS: Record<string, string> = {
  admin: "管理员",
  auditor: "审核员",
  cs: "客服",
};
const ROLE_TAGS: Record<string, string> = {
  admin: "danger",
  auditor: "warning",
  cs: "primary",
};

function roleLabel(v: string): string {
  return ROLE_LABELS[v] ?? v;
}
function roleTag(v: string): string {
  return ROLE_TAGS[v] ?? "info";
}

onMounted(load);

async function load() {
  loading.value = true;
  try {
    rows.value = await lgStaff();
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  form.username = "";
  form.password = "";
  form.role = "cs";
  createDialog.value = true;
}

async function submitCreate() {
  if (!form.username.trim()) {
    ElMessage.warning("用户名必填");
    return;
  }
  if (!form.password) {
    ElMessage.warning("密码必填");
    return;
  }
  acting.value = true;
  try {
    await lgCreateStaff({
      username: form.username.trim(),
      password: form.password,
      role: form.role,
    });
    ElMessage.success("已创建");
    createDialog.value = false;
    await load();
  } catch {
    /* interceptor toasted */
  } finally {
    acting.value = false;
  }
}
</script>

<style scoped>
.toolbar {
  margin-bottom: 12px;
  display: flex;
  gap: 8px;
}
</style>
