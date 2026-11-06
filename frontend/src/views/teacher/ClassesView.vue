<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { classesApi, type ClassInfo } from '../../api/classes'

const router = useRouter()
const classes = ref<ClassInfo[]>([])
const loading = ref(false)
const showCreate = ref(false)
const newName = ref('')
const newGrade = ref('')

async function fetchClasses() {
  loading.value = true
  try {
    const res = await classesApi.list()
    classes.value = res.data
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!newName.value.trim()) return
  await classesApi.create(newName.value.trim(), newGrade.value.trim())
  showCreate.value = false
  newName.value = ''
  newGrade.value = ''
  await fetchClasses()
}

function viewDetail(id: number) {
  router.push(`/teacher/classes/${id}`)
}

onMounted(fetchClasses)
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1>班级管理</h1>
        <p class="subtitle">管理您的班级和学生</p>
      </div>
      <button class="btn btn-primary" @click="showCreate = true">创建班级</button>
    </header>

    <div v-if="showCreate" class="create-card">
      <h3>创建新班级</h3>
      <div class="form-row">
        <input v-model="newName" placeholder="班级名称（如：六年级一班）" class="input" />
        <input v-model="newGrade" placeholder="年级（如：六年级）" class="input" style="max-width: 160px" />
        <button class="btn btn-primary" @click="handleCreate">创建</button>
        <button class="btn btn-ghost" @click="showCreate = false">取消</button>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="classes.length === 0" class="empty">
      <p>暂无班级，点击右上角创建</p>
    </div>
    <div v-else class="class-grid">
      <div v-for="c in classes" :key="c.id" class="class-card" @click="viewDetail(c.id)">
        <div class="card-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>
        </div>
        <h3>{{ c.name }}</h3>
        <p class="card-grade">{{ c.grade || '未设置年级' }}</p>
        <p class="card-code">邀请码: {{ c.invite_code }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 32px; max-width: 1200px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 32px; }
.page-header h1 { margin: 0; font-size: 24px; font-weight: 700; color: #1e293b; }
.subtitle { margin: 4px 0 0; color: #64748b; font-size: 14px; }
.create-card { background: #fff; border-radius: 12px; padding: 20px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.create-card h3 { margin: 0 0 12px; font-size: 16px; }
.form-row { display: flex; gap: 12px; flex-wrap: wrap; }
.input { padding: 10px 14px; border: 1.5px solid #e2e8f0; border-radius: 8px; font-size: 14px; flex: 1; min-width: 200px; outline: none; }
.input:focus { border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,0.1); }
.btn { padding: 10px 20px; border-radius: 8px; font-size: 14px; font-weight: 500; cursor: pointer; border: none; transition: all 0.2s; }
.btn-primary { background: #6366f1; color: #fff; }
.btn-primary:hover { background: #4f46e5; }
.btn-ghost { background: transparent; color: #64748b; border: 1px solid #e2e8f0; }
.btn-ghost:hover { background: #f8fafc; }
.loading, .empty { text-align: center; padding: 64px; color: #94a3b8; }
.class-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 20px; }
.class-card { background: #fff; border-radius: 12px; padding: 24px; cursor: pointer; box-shadow: 0 1px 3px rgba(0,0,0,0.06); transition: all 0.2s; border: 1px solid transparent; }
.class-card:hover { border-color: #6366f1; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
.card-icon { width: 48px; height: 48px; border-radius: 12px; background: #eef2ff; display: flex; align-items: center; justify-content: center; color: #6366f1; margin-bottom: 16px; }
.class-card h3 { margin: 0 0 4px; font-size: 18px; color: #1e293b; }
.card-grade { margin: 0 0 4px; font-size: 13px; color: #64748b; }
.card-code { margin: 0; font-size: 12px; color: #94a3b8; font-family: monospace; }
</style>
