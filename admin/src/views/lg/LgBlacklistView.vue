<template>
  <div class="toolbar">
    <el-button type="primary" @click="openCreate">新增</el-button>
    <el-button :loading="loading" @click="load">刷新</el-button>
  </div>

  <el-table v-loading="loading" :data="rows">
    <el-table-column prop="id" label="ID" width="70" />
    <el-table-column label="类型" width="120">
      <template #default="{ row }">{{ typeLabel(row.value_type) }}</template>
    </el-table-column>
    <el-table-column prop="value" label="值" min-width="180" />
    <el-table-column prop="reason" label="原因" min-width="180" />
    <el-table-column prop="created_by" label="操作人" width="120" />
    <el-table-column label="操作" width="100" fixed="right">
      <template #default="{ row }">
        <el-button link type="danger" @click="remove(row)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>

  <el-dialog v-model="createDialog" title="新增黑名单" width="460px">
    <el-form label-width="90px">
      <el-form-item label="类型">
        <el-select v-model="form.value_type">
          <el-option value="phone" label="手机号" />
          <el-option value="ghana_card" label="Ghana Card" />
        </el-select>
      </el-form-item>
      <el-form-item label="值">
        <el-input v-model="form.value" placeholder="手机号或 Ghana Card 号" />
      </el-form-item>
      <el-form-item label="原因">
        <el-input
          v-model="form.reason"
          type="textarea"
          :rows="3"
          placeholder="拉黑原因"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="createDialog = false">取消</el-button>
      <el-button type="primary" :loading="acting" @click="submitCreate">添加</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import { onMounted, reactive, ref } from "vue";

import { lgAddBlacklist, lgBlacklist, lgDeleteBlacklist } from "../../api/endpoints";
import type { BlacklistEntry } from "../../api/types";

const loading = ref(false);
const acting = ref(false);
const rows = ref<BlacklistEntry[]>([]);

const createDialog = ref(false);
const form = reactive({ value_type: "phone", value: "", reason: "" });

const TYPE_LABELS: Record<string, string> = {
  phone: "手机号",
  ghana_card: "Ghana Card",
};

function typeLabel(v: string): string {
  return TYPE_LABELS[v] ?? v;
}

onMounted(load);

async function load() {
  loading.value = true;
  try {
    rows.value = await lgBlacklist();
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  form.value_type = "phone";
  form.value = "";
  form.reason = "";
  createDialog.value = true;
}

async function submitCreate() {
  if (!form.value.trim()) {
    ElMessage.warning("值必填");
    return;
  }
  acting.value = true;
  try {
    await lgAddBlacklist({
      value_type: form.value_type,
      value: form.value.trim(),
      reason: form.reason.trim(),
    });
    ElMessage.success("已添加");
    createDialog.value = false;
    await load();
  } catch {
    /* interceptor toasted */
  } finally {
    acting.value = false;
  }
}

async function remove(row: BlacklistEntry) {
  await ElMessageBox.confirm(
    `确定删除「${typeLabel(row.value_type)}: ${row.value}」？`,
    "删除确认",
    { type: "warning" },
  );
  acting.value = true;
  try {
    await lgDeleteBlacklist(row.id);
    ElMessage.success("已删除");
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
