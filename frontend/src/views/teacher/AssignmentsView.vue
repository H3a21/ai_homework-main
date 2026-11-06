<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { assignmentsApi, type AssignmentInfo } from '../../api/assignments'
import { submissionsApi, type SubmissionInfo } from '../../api/submissions'

const router = useRouter()
const assignments = ref<AssignmentInfo[]>([])
const submissionsMap = ref<Record<number, SubmissionInfo[]>>({})
const loading = ref(false)

async function fetchData() {
  loading.value = true
  try {
    const res = await assignmentsApi.list()
    assignments.value = res.data
    const subRes = await submissionsApi.list()
    for (const s of subRes.data) {
      if (!submissionsMap.value[s.assignment_id]) {
        submissionsMap.value[s.assignment_id] = []
      }
      submissionsMap.value[s.assignment_id].push(s)
    }
  } finally {
    loading.value = false
  }
}

function viewCreate() {
  router.push('/teacher/assignments/create')
}

onMounted(fetchData)
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1>作业管理</h1>
        <p class="subtitle">查看和管理已布置的作业</p>
      </div>
      <button class="btn btn-primary" @click="viewCreate">布置作业</button>
    </header>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="assignments.length === 0" class="empty">
      <p>暂无作业</p>
    </div>
    <div v-else class="asg-list">
      <div v-for="a in assignments" :key="a.id" class="asg-card">
        <div class="asg-header">
          <h3>{{ a.title }}</h3>
          <span class="tag">{{ a.subject_name }}</span>
        </div>
        <div class="asg-meta">
          <span>{{ a.class_name }}</span>
          <span>{{ a.question_count }} 题</span>
          <span v-if="a.due_date">截止 {{ a.due_date }}</span>
        </div>
        <div class="asg-stats">
          <span>提交 {{ submissionsMap[a.id]?.length || 0 }} / {{ a.question_count }} 人</span>
          <span class="stat-detail">
            已批改: {{ submissionsMap[a.id]?.filter(s => s.status === 'completed').length || 0 }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 32px; max-width: 1200px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 32px; }
.page-header h1 { margin: 0; font-size: 24px; font-weight: 700; color: #1e293b; }
.subtitle { margin: 4px 0 0; color: #64748b; font-size: 14px; }
.btn { padding: 10px 20px; border-radius: 8px; font-size: 14px; font-weight: 500; cursor: pointer; border: none; transition: all 0.2s; }
.btn-primary { background: #6366f1; color: #fff; }
.btn-primary:hover { background: #4f46e5; }
.loading, .empty { text-align: center; padding: 64px; color: #94a3b8; }
.asg-list { display: flex; flex-direction: column; gap: 16px; }
.asg-card { background: #fff; border-radius: 12px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.asg-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.asg-header h3 { margin: 0; font-size: 18px; color: #1e293b; }
.tag { padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 500; background: #eef2ff; color: #6366f1; }
.asg-meta { display: flex; gap: 16px; font-size: 13px; color: #64748b; margin-bottom: 8px; }
.asg-stats { font-size: 13px; color: #94a3b8; display: flex; gap: 16px; }
.stat-detail { color: #10b981; }
</style>
