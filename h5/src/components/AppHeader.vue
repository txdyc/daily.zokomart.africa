<script setup lang="ts">
import { nextTick, ref } from "vue";
import { useI18n } from "vue-i18n";

import { usePrefsStore } from "../stores/prefs";

const emit = defineEmits<{ search: [string] }>();
const { t } = useI18n();
const prefs = usePrefsStore();

const searching = ref(false);
const keyword = ref("");
const inputEl = ref<HTMLInputElement | null>(null);

async function openSearch() {
  searching.value = true;
  await nextTick();
  inputEl.value?.focus();
}

function submit() {
  emit("search", keyword.value.trim());
}

function cancel() {
  searching.value = false;
  keyword.value = "";
  emit("search", "");
}
</script>

<template>
  <header class="header hairline">
    <template v-if="!searching">
      <span class="logo" aria-hidden="true"></span>
      <span class="wordmark">{{ t("appName") }}</span>
      <span class="spacer" />
      <button type="button" class="lang-pill" @click="prefs.toggle()">中 / EN</button>
      <button type="button" class="search-btn" :aria-label="t('searchPlaceholder')" @click="openSearch">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
      </button>
    </template>
    <template v-else>
      <input
        ref="inputEl"
        v-model="keyword"
        class="search-input"
        type="search"
        :placeholder="t('searchPlaceholder')"
        @keyup.enter="submit"
      />
      <button type="button" class="cancel-btn" @click="cancel">{{ t("cancel") }}</button>
    </template>
  </header>
</template>

<style scoped>
.header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  background: var(--bg);
}
.logo {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  background: var(--brand-500);
}
.wordmark {
  font-size: 15px;
  font-weight: 500;
}
.spacer {
  flex: 1;
}
.lang-pill {
  font-size: 11px;
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  padding: 4px 10px;
  background: transparent;
  color: var(--text-secondary);
  min-height: 24px;
}
.search-btn,
.cancel-btn {
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  min-width: 40px;
  min-height: 24px;
  justify-content: center;
}
.cancel-btn {
  font-size: 13px;
}
.search-input {
  flex: 1;
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  padding: 6px 12px;
  font-size: 14px;
  background: var(--surface);
  outline: none;
}
</style>
