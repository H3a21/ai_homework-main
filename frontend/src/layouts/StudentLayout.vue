<script setup lang="ts">
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'
import { ChartNoAxesCombined } from '@lucide/vue'

const authStore = useAuthStore()
const router = useRouter()

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="sidebar-header">
        <h2>智学批改</h2>
        <span class="role-badge student">学生端</span>
      </div>
      <nav class="sidebar-nav">
        <router-link to="/student/dashboard" class="nav-item">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
          我的作业
        </router-link>
        <router-link to="/student/profile" class="nav-item">
          <ChartNoAxesCombined :size="20" />
          我的学情
        </router-link>
      </nav>
      <div class="sidebar-footer">
        <span class="user-name">{{ authStore.user?.display_name }}</span>
        <button class="logout-btn" @click="handleLogout">退出登录</button>
      </div>
    </aside>
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.layout { display: flex; height: 100vh; }
.sidebar {
  width: 240px; background: #1e293b; color: #fff;
  display: flex; flex-direction: column; flex-shrink: 0;
}
.sidebar-header { padding: 24px 20px; border-bottom: 1px solid #334155; }
.sidebar-header h2 { margin: 0; font-size: 18px; font-weight: 600; }
.role-badge {
  display: inline-block; margin-top: 6px; padding: 2px 10px;
  border-radius: 12px; font-size: 12px; font-weight: 500;
}
.role-badge.student { background: #10b981; color: #fff; }
.sidebar-nav { flex: 1; padding: 12px; }
.nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px; border-radius: 8px; color: #94a3b8;
  text-decoration: none; font-size: 14px; transition: all 0.2s;
}
.nav-item:hover, .nav-item.router-link-active { background: #334155; color: #fff; }
.sidebar-footer {
  padding: 16px 20px; border-top: 1px solid #334155;
  display: flex; justify-content: space-between; align-items: center;
}
.user-name { font-size: 14px; color: #94a3b8; }
.logout-btn {
  background: none; border: 1px solid #475569; color: #94a3b8;
  padding: 4px 12px; border-radius: 6px; cursor: pointer; font-size: 12px;
}
.logout-btn:hover { border-color: #ef4444; color: #ef4444; }
.main-content { flex: 1; overflow-y: auto; background: #f8fafc; }
</style>
