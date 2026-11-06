<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAuthStore } from '../../stores/auth'

const authStore = useAuthStore()
const stats = ref([
  { label: '班级数', value: '--', color: '#6366f1' },
  { label: '作业数', value: '--', color: '#10b981' },
  { label: '待批改', value: '--', color: '#f59e0b' },
  { label: '学生数', value: '--', color: '#3b82f6' },
])

onMounted(() => {
  // TODO: fetch actual stats from API
})
</script>

<template>
  <div class="dashboard">
    <header class="page-header">
      <h1>教师工作台</h1>
      <p class="welcome">欢迎回来，{{ authStore.user?.display_name }}</p>
    </header>

    <div class="stats-grid">
      <div v-for="s in stats" :key="s.label" class="stat-card" :style="{ borderLeftColor: s.color }">
        <div class="stat-value">{{ s.value }}</div>
        <div class="stat-label">{{ s.label }}</div>
      </div>
    </div>

    <div class="placeholder-card">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="12" y2="17"/></svg>
      <h3>更多功能开发中</h3>
      <p>班级管理、布置作业、批改审核等功能即将上线</p>
    </div>
  </div>
</template>

<style scoped>
.dashboard { padding: 32px; max-width: 1200px; margin: 0 auto; }
.page-header { margin-bottom: 32px; }
.page-header h1 { margin: 0; font-size: 24px; font-weight: 700; color: #1e293b; }
.welcome { margin: 4px 0 0; color: #64748b; font-size: 14px; }
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 32px; }
.stat-card {
  background: #fff; border-radius: 12px; padding: 24px;
  border-left: 4px solid; box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.stat-value { font-size: 32px; font-weight: 700; color: #1e293b; }
.stat-label { font-size: 14px; color: #64748b; margin-top: 4px; }
.placeholder-card {
  background: #fff; border-radius: 12px; padding: 48px;
  text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.placeholder-card h3 { margin: 16px 0 8px; color: #475569; }
.placeholder-card p { color: #94a3b8; font-size: 14px; }
</style>
