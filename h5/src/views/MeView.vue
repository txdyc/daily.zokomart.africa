<script setup lang="ts">
import TabBar from "../components/TabBar.vue";
</script>

<template>
  <div class="page">
    <main class="body"></main>
    <TabBar />
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: var(--surface);
}
.body {
  padding-bottom: 64px;
}
</style>
