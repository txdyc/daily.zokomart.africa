<template>
  <div class="auth-image-wrap">
    <div v-if="loading" class="placeholder loading">
      <el-icon class="icon-spin"><Loading /></el-icon>
    </div>
    <div v-else-if="error" class="placeholder error">
      <el-icon><Picture /></el-icon>
      <span>加载失败</span>
    </div>
    <img v-else-if="src" :src="src" class="auth-image" loading="lazy" />
  </div>
</template>

<script setup lang="ts">
import { Loading, Picture } from "@element-plus/icons-vue";
import { onBeforeUnmount, ref, watch } from "vue";

import { TOKEN_KEY } from "../api/client";

const props = defineProps<{ id: string }>();

const src = ref("");
const loading = ref(false);
const error = ref(false);
let objectUrl = "";

async function load() {
  if (!props.id) {
    src.value = "";
    loading.value = false;
    error.value = false;
    return;
  }
  loading.value = true;
  error.value = false;
  src.value = "";
  // Fetch the image as a blob with the admin bearer token attached
  const token = localStorage.getItem(TOKEN_KEY);
  try {
    const resp = await fetch(`/api/lg/uploads/${props.id}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const blob = await resp.blob();
    // Reject non-image content types (e.g. HTML error pages)
    if (!blob.type.startsWith("image/")) throw new Error("Not an image");
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = URL.createObjectURL(blob);
    src.value = objectUrl;
  } catch {
    error.value = true;
    src.value = "";
  } finally {
    loading.value = false;
  }
}

watch(() => props.id, load, { immediate: true });

onBeforeUnmount(() => {
  if (objectUrl) URL.revokeObjectURL(objectUrl);
});
</script>

<style scoped>
.auth-image-wrap {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.auth-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font-size: 12px;
  color: #909399;
}
.placeholder.loading .icon-spin {
  animation: spin 1s linear infinite;
}
.placeholder.error {
  color: #c0c4cc;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
