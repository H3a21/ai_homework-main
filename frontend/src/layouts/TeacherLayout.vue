<script setup lang="ts">
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'
import { Menu, X } from '@lucide/vue'
import { ref, watch } from 'vue'

const authStore = useAuthStore()
const router = useRouter()
const navigationOpen = ref(false)

watch(
  () => router.currentRoute.value.fullPath,
  () => { navigationOpen.value = false },
)

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>

<template>
  <div class="layout">
    <header class="mobile-header">
      <strong>智学批改</strong>
      <button
        class="mobile-nav-button"
        type="button"
        title="打开导航"
        aria-label="打开导航"
        :aria-expanded="navigationOpen"
        @click="navigationOpen = true"
      >
        <Menu :size="20" aria-hidden="true" />
      </button>
    </header>
    <button
      v-if="navigationOpen"
      class="sidebar-backdrop"
      type="button"
      aria-label="关闭导航"
      @click="navigationOpen = false"
    />
    <aside class="sidebar" :class="{ open: navigationOpen }">
      <div class="sidebar-header">
        <div>
          <h2>智学批改</h2>
          <span class="role-badge teacher">教师端</span>
        </div>
        <button
          class="sidebar-close"
          type="button"
          title="关闭导航"
          aria-label="关闭导航"
          @click="navigationOpen = false"
        >
          <X :size="20" aria-hidden="true" />
        </button>
      </div>
      <nav class="sidebar-nav">
        <router-link to="/teacher/dashboard" class="nav-item">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
          工作台
        </router-link>
        <router-link to="/teacher/classes" class="nav-item">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>
          班级管理
        </router-link>
        <router-link to="/teacher/assignments" class="nav-item">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
          作业管理
        </router-link>
        <router-link to="/teacher/grading" class="nav-item">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
          批改审核
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
.mobile-header, .sidebar-backdrop, .sidebar-close { display: none; }
.sidebar {
  width: 240px; background: #1e293b; color: #fff;
  display: flex; flex-direction: column; flex-shrink: 0;
}
.sidebar-header { display: flex; justify-content: space-between; padding: 24px 20px; border-bottom: 1px solid #334155; }
.sidebar-header h2 { margin: 0; font-size: 18px; font-weight: 600; }
.role-badge {
  display: inline-block; margin-top: 6px; padding: 2px 10px;
  border-radius: 12px; font-size: 12px; font-weight: 500;
}
.role-badge.teacher { background: #6366f1; color: #fff; }
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
@media (max-width: 720px) {
  .layout { display: block; min-height: 100vh; }
  .mobile-header {
    display: flex; height: 56px; padding: 0 16px; align-items: center;
    justify-content: space-between; background: #1e293b; color: #fff;
  }
  .mobile-nav-button, .sidebar-close {
    display: inline-flex; width: 36px; height: 36px; padding: 0;
    align-items: center; justify-content: center; border: 0; border-radius: 6px;
    background: transparent; color: inherit; cursor: pointer;
  }
  .mobile-nav-button:hover, .sidebar-close:hover { background: #334155; }
  .sidebar-backdrop {
    display: block; position: fixed; inset: 0; z-index: 20;
    width: 100%; height: 100%; border: 0; background: rgba(15, 23, 42, 0.52);
  }
  .sidebar {
    position: fixed; inset: 0 auto 0 0; z-index: 30;
    width: min(280px, 82vw); transform: translateX(-100%);
    transition: transform 0.2s ease;
  }
  .sidebar.open { transform: translateX(0); }
  .main-content { height: calc(100vh - 56px); }
}
</style>
