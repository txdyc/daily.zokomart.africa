<template>
  <img v-if="src" :src="src" class="auth-image" loading="lazy" />
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from "vue";

import { TOKEN_KEY } from "../api/client";

const props = defineProps<{ id: string }>();

const src = ref("");
let objectUrl = "";

async function load() {
  if (!props.id) {
    src.value = "";
    return;
  }
  // Fetch the image as a blob with the admin bearer token attached
  const token = localStorage.getItem(TOKEN_KEY);
  try {
    const resp = await fetch(`/api/lg/uploads/${props.id}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const blob = await resp.blob();
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = URL.createObjectURL(blob);
    src.value = objectUrl;
  } catch {
    src.value = "";
  }
}

watch(() => props.id, load, { immediate: true });

onBeforeUnmount(() => {
  if (objectUrl) URL.revokeObjectURL(objectUrl);
});
</script>

<style scoped>
.auth-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
