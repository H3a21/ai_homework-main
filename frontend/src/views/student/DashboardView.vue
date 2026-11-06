<script setup lang="ts">
import { useAuthStore } from '../../stores/auth'

const authStore = useAuthStore()
</script>

<template>
  <div class="dashboard">
    <header class="page-header">
      <h1>我的作业</h1>
      <p class="welcome">你好，{{ authStore.user?.display_name }}</p>
    </header>

    <div class="placeholder-card">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
      <h3>暂无作业</h3>
      <p>当老师布置作业后，你会在这里看到</p>
    </div>
  </div>
</template>

<style scoped>
.dashboard { padding: 32px; max-width: 1200px; margin: 0 auto; }
.page-header { margin-bottom: 32px; }
.page-header h1 { margin: 0; font-size: 24px; font-weight: 700; color: #1e293b; }
.welcome { margin: 4px 0 0; color: #64748b; font-size: 14px; }
.placeholder-card {
  background: #fff; border-radius: 12px; padding: 64px 48px;
  text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.placeholder-card h3 { margin: 16px 0 8px; color: #475569; }
.placeholder-card p { color: #94a3b8; font-size: 14px; }
</style>
