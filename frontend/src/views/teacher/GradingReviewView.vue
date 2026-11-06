<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Play } from '@lucide/vue'
import { submissionsApi, type SubmissionInfo } from '../../api/submissions'
import { assignmentsApi, type AssignmentInfo } from '../../api/assignments'
import { gradingBatchesApi, type GradingBatch } from '../../api/gradingBatches'
import BatchProgress from '../../components/BatchProgress.vue'

const router = useRouter()
const submissions = ref<SubmissionInfo[]>([])
const assignments = ref<AssignmentInfo[]>([])
const loading = ref(false)
const selectedAsg = ref<number | undefined>(undefined)
const grading = ref<Set<number>>(new Set())
const activeBatch = ref<GradingBatch | null>(null)
const batchStarting = ref(false)
const batchError = ref('')

const selectedPendingCount = computed(() => {
  if (!selectedAsg.value) return 0
  return submissions.value.filter(
    submission => submission.assignment_id === selectedAsg.value && submission.status === 'pending',
  ).length
})

const batchIsRunning = computed(() =>
  activeBatch.value?.status === 'pending' || activeBatch.value?.status === 'grading',
)

async function fetchData() {
  loading.value = true
  try {
    const [asgRes, subRes] = await Promise.all([
      assignmentsApi.list(),
      submissionsApi.list(),
    ])
    assignments.value = asgRes.data
    submissions.value = subRes.data
  } finally {
    loading.value = false
  }
}

function filteredSubmissions() {
  if (!selectedAsg.value) return submissions.value
  return submissions.value.filter(s => s.assignment_id === selectedAsg.value)
}

async function gradeSubmission(submissionId: number) {
  grading.value.add(submissionId)
  try {
    await submissionsApi.grade(submissionId)
    await fetchData()
  } finally {
    grading.value.delete(submissionId)
  }
}

async function loadLatestBatch() {
  stopBatchLiveUpdates()
  batchError.value = ''
  if (!selectedAsg.value) {
    activeBatch.value = null
    return
  }
  try {
    const response = await gradingBatchesApi.list({ assignment_id: selectedAsg.value, limit: 1 })
    activeBatch.value = response.data[0] || null
    if (batchIsRunning.value) connectBatchRealtime()
  } catch {
    activeBatch.value = null
    batchError.value = '批次记录暂时无法加载'
  }
}

async function startBatch() {
  if (!selectedAsg.value || selectedPendingCount.value === 0 || batchIsRunning.value) return
  batchStarting.value = true
  batchError.value = ''
  try {
    const response = await gradingBatchesApi.create(selectedAsg.value)
    activeBatch.value = response.data
    await fetchData()
    connectBatchRealtime()
  } catch {
    await loadLatestBatch()
    batchError.value = '批量任务未能启动，请刷新后重试'
  } finally {
    batchStarting.value = false
  }
}

function viewResult(submissionId: number) {
  const s = submissions.value.find(x => x.id === submissionId)
  if (s?.student_id) {
    router.push(`/teacher/submissions/${submissionId}`)
  }
}

function getAssignmentName(assignmentId: number) {
  return assignments.value.find(a => a.id === assignmentId)?.title || `作业#${assignmentId}`
}

let pollTimer: ReturnType<typeof window.setInterval> | undefined
let batchSocket: WebSocket | null = null
let batchFallbackTimer: ReturnType<typeof window.setInterval> | undefined

function stopBatchFallback() {
  if (batchFallbackTimer) window.clearInterval(batchFallbackTimer)
  batchFallbackTimer = undefined
}

function stopBatchLiveUpdates() {
  stopBatchFallback()
  const socket = batchSocket
  batchSocket = null
  if (socket && socket.readyState < WebSocket.CLOSING) {
    socket.onclose = null
    socket.onerror = null
    socket.close(1000)
  }
}

async function refreshActiveBatch() {
  if (!activeBatch.value) return
  try {
    const response = await gradingBatchesApi.get(activeBatch.value.id)
    activeBatch.value = response.data
    await fetchData()
    if (!batchIsRunning.value) stopBatchLiveUpdates()
  } catch {
    batchError.value = '批次进度暂时无法刷新'
  }
}

function startBatchFallback() {
  if (batchFallbackTimer || !batchIsRunning.value) return
  batchFallbackTimer = window.setInterval(refreshActiveBatch, 5000)
}

function connectBatchRealtime() {
  stopBatchLiveUpdates()
  const batch = activeBatch.value
  const token = localStorage.getItem('access_token')
  if (!batch || !token || !batchIsRunning.value) {
    startBatchFallback()
    return
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  let socket: WebSocket
  try {
    socket = new WebSocket(`${protocol}//${window.location.host}/api/ws/batches/${batch.id}`)
  } catch {
    startBatchFallback()
    return
  }
  batchSocket = socket
  socket.onopen = () => {
    stopBatchFallback()
    socket.send(JSON.stringify({ type: 'auth', token }))
  }
  socket.onmessage = async (event) => {
    let payload: Partial<GradingBatch> & { type?: string }
    try {
      payload = JSON.parse(String(event.data))
    } catch {
      return
    }
    if (payload.type === 'grading_batch.snapshot' || payload.type === 'grading_batch.status') {
      activeBatch.value = { ...activeBatch.value!, ...payload }
      if (!batchIsRunning.value) {
        await fetchData()
        stopBatchLiveUpdates()
      }
    }
  }
  socket.onerror = () => socket.close()
  socket.onclose = () => {
    if (batchSocket === socket) batchSocket = null
    startBatchFallback()
  }
}

onMounted(async () => {
  await fetchData()
  pollTimer = window.setInterval(() => {
    if (submissions.value.some(s => s.status === 'grading')) fetchData()
  }, 2000)
})

watch(selectedAsg, loadLatestBatch)

onUnmounted(() => {
  if (pollTimer) window.clearInterval(pollTimer)
  stopBatchLiveUpdates()
})
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1>批改审核</h1>
        <p class="subtitle">查看学生提交并管理批改</p>
      </div>
      <div class="header-actions">
        <select v-model="selectedAsg" class="filter-select">
          <option :value="undefined">全部作业</option>
          <option v-for="a in assignments" :key="a.id" :value="a.id">{{ a.title }}</option>
        </select>
        <button
          class="btn btn-primary batch-button"
          :disabled="!selectedAsg || selectedPendingCount === 0 || batchIsRunning || batchStarting"
          :title="!selectedAsg ? '请先选择作业' : selectedPendingCount === 0 ? '没有待批改提交' : '批量提交待批改作业'"
          @click="startBatch"
        >
          <Play :size="15" aria-hidden="true" />
          {{ batchStarting ? '启动中...' : batchIsRunning ? '批改进行中' : `批量批改 ${selectedPendingCount}` }}
        </button>
      </div>
    </header>

    <p v-if="batchError" class="batch-error" role="alert">{{ batchError }}</p>
    <BatchProgress v-if="activeBatch && selectedAsg" :batch="activeBatch" />

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="filteredSubmissions().length === 0" class="empty">
      <p>暂无提交记录</p>
    </div>
    <div v-else class="sub-list">
      <div v-for="s in filteredSubmissions()" :key="s.id" class="sub-card">
        <div class="sub-main">
          <div class="sub-student">
            <div class="avatar">{{ s.student_name?.[0] || '?' }}</div>
            <div>
              <strong>{{ s.student_name }}</strong>
              <span class="sub-asg">{{ getAssignmentName(s.assignment_id) }}</span>
            </div>
          </div>
          <div class="sub-status" :class="s.status">
            {{ s.status === 'completed' ? '已批改' : s.status === 'grading' ? '批改中' : '待批改' }}
          </div>
        </div>
        <div class="sub-detail">
          <span>提交时间: {{ s.submitted_at?.slice(0, 16) || '--' }}</span>
          <span v-if="s.total_score != null">得分: {{ s.total_score }}</span>
        </div>
        <div class="sub-actions">
          <button
            v-if="s.status === 'pending'"
            class="btn btn-primary btn-sm"
            :disabled="grading.has(s.id)"
            @click="gradeSubmission(s.id)"
          >
            {{ grading.has(s.id) ? '提交中...' : '提交批改' }}
          </button>
          <button
            v-if="s.status === 'completed'"
            class="btn btn-ghost btn-sm"
            @click="viewResult(s.id)"
          >
            查看批改
          </button>
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
.filter-select { padding: 8px 14px; border: 1.5px solid #e2e8f0; border-radius: 8px; font-size: 14px; outline: none; min-width: 200px; }
.header-actions { display: flex; align-items: center; gap: 10px; }
.batch-button { display: inline-flex; min-width: 144px; align-items: center; justify-content: center; gap: 7px; white-space: nowrap; }
.batch-error { margin: -18px 0 20px; color: #b91c1c; font-size: 13px; }
.loading, .empty { text-align: center; padding: 64px; color: #94a3b8; }
.sub-list { display: flex; flex-direction: column; gap: 16px; }
.sub-card { background: #fff; border-radius: 12px; padding: 20px 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.sub-main { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.sub-student { display: flex; align-items: center; gap: 12px; }
.avatar { width: 36px; height: 36px; border-radius: 50%; background: #eef2ff; color: #6366f1; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 600; }
.sub-asg { display: block; font-size: 12px; color: #94a3b8; }
.sub-status { padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 500; }
.sub-status.completed { background: #ecfdf5; color: #10b981; }
.sub-status.grading { background: #fffbeb; color: #f59e0b; }
.sub-status.pending { background: #f1f5f9; color: #64748b; }
.sub-detail { display: flex; gap: 20px; font-size: 13px; color: #94a3b8; margin-bottom: 12px; }
.sub-actions { display: flex; gap: 8px; }
.btn { padding: 8px 16px; border-radius: 8px; font-size: 13px; font-weight: 500; cursor: pointer; border: none; transition: all 0.2s; }
.btn-primary { background: #6366f1; color: #fff; }
.btn-primary:hover { background: #4f46e5; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-ghost { background: transparent; color: #6366f1; border: 1px solid #6366f1; }
.btn-ghost:hover { background: #eef2ff; }
.btn-sm { padding: 6px 14px; font-size: 12px; }
@media (max-width: 720px) {
  .page { padding: 20px 16px; }
  .page-header { flex-direction: column; gap: 16px; margin-bottom: 24px; }
  .header-actions { width: 100%; flex-wrap: wrap; }
  .filter-select { flex: 1 1 180px; min-width: 0; }
  .batch-button { flex: 1 1 160px; }
  .sub-main { align-items: flex-start; gap: 12px; }
  .sub-detail { flex-direction: column; gap: 4px; }
}
</style>
