<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { submissionsApi, type SubmissionInfo } from '../../api/submissions'
import ImageViewer from '../../components/ImageViewer.vue'
import ScoreDistribution from '../../components/ScoreDistribution.vue'
import StepComparison from '../../components/StepComparison.vue'

const route = useRoute()
const submission = ref<SubmissionInfo | null>(null)
const loading = ref(false)
const polling = ref(false)
let pollTimer: ReturnType<typeof window.setInterval> | undefined

const scoreItems = computed(() => submission.value?.questions?.map(question => ({
  label: `第${question.question_number}题`,
  value: question.score != null && question.max_score > 0
    ? Math.min(1, question.score / question.max_score)
    : 0,
})) || [])

async function fetchData() {
  if (polling.value) return
  polling.value = true
  if (!submission.value) loading.value = true
  try {
    const res = await submissionsApi.get(Number(route.params.id))
    submission.value = res.data
    if (res.data.status === 'completed' && pollTimer) {
      window.clearInterval(pollTimer)
      pollTimer = undefined
    }
  } finally {
    polling.value = false
    loading.value = false
  }
}

onMounted(async () => {
  await fetchData()
  if (submission.value?.status !== 'completed') {
    pollTimer = window.setInterval(fetchData, 2000)
  }
})

onUnmounted(() => {
  if (pollTimer) window.clearInterval(pollTimer)
})
</script>

<template>
  <div class="page">
    <header class="page-header">
      <h1>批改详情</h1>
      <p class="subtitle" v-if="submission">{{ submission.student_name }} · {{ submission.assignment_title }}</p>
    </header>

    <div v-if="loading" class="loading">加载中...</div>
    <template v-else-if="submission">
      <div class="summary-card">
        <div class="score-circle" :class="submission.status">
          <span class="score-value">{{ submission.total_score ?? '--' }}</span>
          <span class="score-label">总分</span>
        </div>
        <div class="summary-info">
          <p><strong>学生：</strong>{{ submission.student_name }}</p>
          <p><strong>作业：</strong>{{ submission.assignment_title }}</p>
          <p><strong>状态：</strong>{{ submission.status === 'completed' ? '已批改' : submission.status }}</p>
          <p><strong>提交：</strong>{{ submission.submitted_at?.slice(0, 16) || '--' }}</p>
          <p><strong>批改：</strong>{{ submission.graded_at?.slice(0, 16) || '待批改' }}</p>
          <p v-if="submission.comment"><strong>评语：</strong>{{ submission.comment }}</p>
        </div>
      </div>

      <ImageViewer :images="submission.images || []" />
      <div class="detail-grid">
        <StepComparison :questions="submission.questions || []" />
        <section class="score-panel"><h3>题目得分分布</h3><ScoreDistribution :items="scoreItems" /></section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page { padding: 32px; max-width: 1180px; margin: 0 auto; }
.page-header { margin-bottom: 24px; }
.page-header h1 { margin: 0; font-size: 24px; font-weight: 700; color: #1e293b; }
.subtitle { margin: 4px 0 0; color: #64748b; font-size: 14px; }
.loading { text-align: center; padding: 64px; color: #94a3b8; }
.summary-card { display: flex; gap: 32px; background: #fff; border-radius: 12px; padding: 32px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); align-items: center; }
.score-circle { width: 100px; height: 100px; border-radius: 50%; display: flex; flex-direction: column; align-items: center; justify-content: center; background: #eef2ff; color: #6366f1; flex-shrink: 0; }
.score-circle.completed { background: #ecfdf5; color: #10b981; }
.score-value { font-size: 32px; font-weight: 700; line-height: 1; }
.score-label { font-size: 12px; color: inherit; opacity: 0.7; }
.summary-info p { margin: 4px 0; font-size: 14px; color: #475569; }
.detail-grid { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(320px, .85fr); gap: 16px; margin-top: 16px; }
.score-panel { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; }
.score-panel h3 { margin: 0 0 8px; color: #1e293b; font-size: 16px; }
@media (max-width: 900px) { .detail-grid { grid-template-columns: 1fr; } }
@media (max-width: 600px) { .page { padding: 18px 14px; } .summary-card { align-items: flex-start; padding: 20px; } }
</style>
