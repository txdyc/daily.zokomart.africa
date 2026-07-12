<script setup lang="ts">
import { ref } from "vue";

import { uploadImage } from "../api/lg";

const props = defineProps<{ modelValue: string[]; max?: number }>();
const emit = defineEmits<{ "update:modelValue": [string[]] }>();

const busy = ref(false);
const error = ref("");

async function onPick(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  if (props.modelValue.length >= (props.max ?? 6)) return;
  busy.value = true;
  error.value = "";
  try {
    const res = await uploadImage(file);
    emit("update:modelValue", [...props.modelValue, res.id]);
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    busy.value = false;
    input.value = "";
  }
}

function removeAt(i: number) {
  emit("update:modelValue", props.modelValue.filter((_, idx) => idx !== i));
}
</script>

<template>
  <div class="uploader">
    <span v-for="(id, i) in modelValue" :key="id" class="thumb">
      <img :src="`/api/lg/uploads/${id}`" alt="" />
      <button type="button" class="rm" @click="removeAt(i)">×</button>
    </span>
    <label v-if="modelValue.length < (max ?? 6)" class="add">
      <input type="file" accept="image/*" hidden @change="onPick" />
      <span>{{ busy ? "…" : "+" }}</span>
    </label>
    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<style scoped>
.uploader { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.thumb { position: relative; width: 60px; height: 60px; border-radius: 8px; overflow: hidden; }
.thumb img { width: 100%; height: 100%; object-fit: cover; }
.rm { position: absolute; top: 0; right: 0; border: 0; background: rgba(0,0,0,.55); color: #fff; width: 18px; height: 18px; line-height: 16px; }
.add { width: 60px; height: 60px; border: 1px dashed var(--border); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 24px; color: var(--text-muted); }
.error { color: #c0392b; font-size: 12px; width: 100%; }
</style>
