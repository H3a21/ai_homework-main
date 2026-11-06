<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { LoaderCircle, RefreshCw } from '@lucide/vue'
import { useRoute } from 'vue-router'
import { submissionsApi, type SubmissionInfo } from '../../api/submissions'
import LatexRender from '../../components/LatexRender.vue'

interface RealtimeMessage {
  type: 'submission.snapshot' | 'submission.status' | 'heartbeat' | 'error'
  submission_id?: number
  status?: string
  code?: string
}

const route = useRoute()
const submissionId = Number(route.params.id)
const submission = ref<SubmissionInfo | null>(null)
const loading = ref(false)
const refreshing = ref(false)
const loadError = ref('')

let socket: WebSocket | null = null
let reconnectTimer: ReturnType<typeof window.setTimeout> | undefined
let fallbackTimer: ReturnType<typeof window.setInterval> | undefined
let reconnectAttempts = 0
let destroyed = false

const statusLabel = computed(() => {
  if (submission.value?.status === 'completed') return '已批改'
  if (submission.value?.status === 'grading') return '批改中'
  return '等待批改'
})

async function fetchResult(showLoading = false): Promise<boolean> {
  if (refreshing.value) return false
  refreshing.value = true
  if (showLoading && !submission.value) loading.value = true
  try {
    const res = await submissionsApi.get(submissionId)
    submission.value = res.data
    loadError.value = ''
    if (res.data.status === 'completed') stopLiveUpdates()
    return true
  } catch {
    if (!submission.value) loadError.value = '结果加载失败，请重试。'
    return false
  } finally {
    refreshing.value = false
    loading.value = false
  }
}

function realtimeUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/ws/submissions/${submissionId}`
}

function stopFallbackPolling() {
  if (fallbackTimer) window.clearInterval(fallbackTimer)
  fallbackTimer = undefined
}

function startFallbackPolling() {
  if (fallbackTimer || submission.value?.status === 'completed' || destroyed) return
  fallbackTimer = window.setInterval(async () => {
    await fetchResult()
  }, 10_000)
}

function scheduleReconnect() {
  if (reconnectTimer || submission.value?.status === 'completed' || destroyed) return
  const delay = Math.min(1000 * 2 ** reconnectAttempts, 15_000)
  reconnectAttempts += 1
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = undefined
    connectRealtime()
  }, delay)
}

function stopLiveUpdates() {
  stopFallbackPolling()
  if (reconnectTimer) window.clearTimeout(reconnectTimer)
  reconnectTimer = undefined
  const activeSocket = socket
  socket = null
  if (activeSocket && activeSocket.readyState < WebSocket.CLOSING) {
    activeSocket.close(1000)
  }
}

function connectRealtime() {
  if (destroyed || submission.value?.status === 'completed') return
  if (socket && socket.readyState < WebSocket.CLOSING) return

  const token = localStorage.getItem('access_token')
  if (!token) {
    startFallbackPolling()
    return
  }

  let activeSocket: WebSocket
  try {
    activeSocket = new WebSocket(realtimeUrl())
  } catch {
    startFallbackPolling()
    scheduleReconnect()
    return
  }
  socket = activeSocket

  activeSocket.onopen = () => {
    reconnectAttempts = 0
    stopFallbackPolling()
    activeSocket.send(JSON.stringify({ type: 'auth', token }))
  }

  activeSocket.onmessage = async (event) => {
    let message: RealtimeMessage
    try {
      message = JSON.parse(String(event.data)) as RealtimeMessage
    } catch {
      return
    }

    if (
      (message.type === 'submission.snapshot' || message.type === 'submission.status')
      && message.submission_id === submissionId
      && message.status
    ) {
      if (submission.value) submission.value.status = message.status
      if (message.status === 'completed') await fetchResult()
    }
    if (message.type === 'error') {
      activeSocket.close()
    }
  }

  activeSocket.onerror = () => {
    activeSocket.close()
  }

  activeSocket.onclose = async (event) => {
    if (socket === activeSocket) socket = null
    if (destroyed || submission.value?.status === 'completed') return

    startFallbackPolling()
    if (event.code === 4401) await fetchResult()
    if (event.code !== 4403 && event.code !== 4404) scheduleReconnect()
  }
}

async function retryLoad() {
  if (await fetchResult(true)) connectRealtime()
}

onMounted(async () => {
  if (await fetchResult(true) && submission.value?.status !== 'completed') {
    connectRealtime()
  }
})

onUnmounted(() => {
  destroyed = true
  stopLiveUpdates()
})
</script>

<template>
  <div class="page">
    <header class="page-header">
      <h1>批改结果</h1>
      <p v-if="submission" class="subtitle">{{ submission.assignment_title }}</p>
    </header>

    <div v-if="loading" class="loading">
      <LoaderCircle class="spin" :size="22" aria-hidden="true" />
      <span>加载中...</span>
    </div>
    <div v-else-if="loadError" class="load-error" role="alert">
      <p>{{ loadError }}</p>
      <button class="retry-button" type="button" :disabled="refreshing" @click="retryLoad">
        <RefreshCw :class="{ spin: refreshing }" :size="16" aria-hidden="true" />
        重试
      </button>
    </div>
    <template v-else-if="submission">
      <section data-testid="grading-summary" class="summary-panel">
        <div class="score-circle" :class="submission.status">
          <LoaderCircle v-if="submission.status !== 'completed'" class="spin" :size="24" aria-hidden="true" />
          <span v-else data-testid="grading-score" class="score-value">{{ submission.total_score ?? '--' }}</span>
          <span class="score-label">{{ submission.status === 'completed' ? '总分' : statusLabel }}</span>
        </div>
        <div class="summary-info">
          <div class="status-line">
            <span class="status-dot" :class="submission.status" aria-hidden="true"></span>
            <strong>{{ statusLabel }}</strong>
          </div>
          <p><span>提交时间</span>{{ submission.submitted_at?.slice(0, 10) || '--' }}</p>
          <p><span>批改时间</span>{{ submission.graded_at?.slice(0, 10) || '待批改' }}</p>
          <p v-if="submission.comment" class="comment"><span>评语</span>{{ submission.comment }}</p>
        </div>
      </section>

      <section class="detail-panel">
        <h2>逐题评分</h2>
        <div v-for="q in submission.questions" :key="q.id" class="question-result">
          <div class="question-header">
            <span class="question-number">第 {{ q.question_number }} 题</span>
            <span class="question-content"><LatexRender :text="q.content || `题目 ${q.question_number}`" /></span>
            <span class="question-score">{{ q.score != null ? `${q.score}/${q.max_score}` : '待批改' }}</span>
          </div>
          <p v-if="q.feedback" class="question-feedback">{{ q.feedback }}</p>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.page { padding: 32px; max-width: 800px; margin: 0 auto; }
.page-header { margin-bottom: 24px; }
.page-header h1 { margin: 0; font-size: 24px; font-weight: 700; color: #172033; }
.subtitle { margin: 4px 0 0; color: #667085; font-size: 14px; }
.loading { min-height: 180px; display: flex; align-items: center; justify-content: center; gap: 9px; color: #667085; }
.load-error { min-height: 180px; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #b42318; }
.retry-button { min-height: 38px; display: inline-flex; align-items: center; gap: 7px; padding: 8px 14px; border: 1px solid #d0d5dd; border-radius: 8px; background: #fff; color: #344054; font: inherit; font-size: 14px; cursor: pointer; }
.summary-panel { display: flex; gap: 32px; align-items: center; padding: 28px; margin-bottom: 20px; background: #fff; border: 1px solid #e4e7ec; border-radius: 8px; }
.score-circle { width: 104px; height: 104px; flex: 0 0 104px; display: flex; flex-direction: column; align-items: center; justify-content: center; border-radius: 50%; background: #f2f4f7; color: #475467; }
.score-circle.grading { background: #eff8ff; color: #175cd3; }
.score-circle.completed { background: #ecfdf3; color: #067647; }
.score-value { font-size: 32px; font-weight: 700; line-height: 1; }
.score-label { margin-top: 5px; font-size: 12px; color: inherit; }
.summary-info { min-width: 0; flex: 1; }
.status-line { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; color: #344054; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: #98a2b3; }
.status-dot.grading { background: #2e90fa; }
.status-dot.completed { background: #12b76a; }
.summary-info p { display: grid; grid-template-columns: 76px minmax(0, 1fr); gap: 10px; margin: 7px 0; font-size: 14px; color: #344054; }
.summary-info p span { color: #667085; }
.summary-info .comment { line-height: 1.6; }
.detail-panel { padding: 24px; background: #fff; border: 1px solid #e4e7ec; border-radius: 8px; }
.detail-panel h2 { margin: 0 0 12px; font-size: 16px; color: #172033; }
.question-result { padding: 14px 0; border-bottom: 1px solid #eef0f3; }
.question-result:last-child { border-bottom: none; }
.question-header { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 12px; align-items: center; }
.question-number { font-weight: 600; color: #475467; font-size: 14px; white-space: nowrap; }
.question-content { min-width: 0; font-size: 14px; color: #172033; }
.question-score { font-size: 14px; font-weight: 600; color: #344054; white-space: nowrap; }
.question-feedback { margin: 9px 0 0; padding: 9px 12px; border-left: 3px solid #12b76a; background: #f6fef9; color: #475467; font-size: 13px; line-height: 1.55; }
.spin { animation: spin 0.9s linear infinite; }

@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 640px) {
  .page { padding: 20px 16px; }
  .summary-panel { align-items: flex-start; gap: 20px; padding: 20px 16px; }
  .score-circle { width: 82px; height: 82px; flex-basis: 82px; }
  .score-value { font-size: 26px; }
  .summary-info p { grid-template-columns: 64px minmax(0, 1fr); gap: 7px; }
  .detail-panel { padding: 20px 16px; }
  .question-header { grid-template-columns: 1fr auto; }
  .question-content { grid-column: 1 / -1; grid-row: 2; }
}
</style>
