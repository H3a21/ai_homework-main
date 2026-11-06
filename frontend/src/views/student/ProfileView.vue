<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RefreshCw } from '@lucide/vue'
import { reportsApi, type StudentLearningReport } from '../../api/reports'
import KnowledgeRadar from '../../components/KnowledgeRadar.vue'
import ScoreDistribution from '../../components/ScoreDistribution.vue'
import TrendChart from '../../components/TrendChart.vue'
import { useAuthStore } from '../../stores/auth'

const authStore = useAuthStore()
const report = ref<StudentLearningReport | null>(null)
const loading = ref(false)
const error = ref('')

const subjectBars = computed(() => report.value?.subject_summaries.map(item => ({
  label: item.subject_name,
  value: item.average_mastery,
})) || [])

async function fetchReport() {
  if (!authStore.user) await authStore.fetchUser()
  if (!authStore.user) return
  loading.value = true
  error.value = ''
  try {
    report.value = (await reportsApi.getStudent(authStore.user.id)).data
  } catch {
    error.value = '学情报告加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function percent(value: number) { return `${Math.round(value * 100)}%` }

onMounted(fetchReport)
</script>

<template>
  <div class="report-page">
    <header class="page-header">
      <div>
        <h1>我的学情</h1>
        <p>{{ report?.student_name || authStore.user?.display_name }}</p>
      </div>
      <button class="icon-button" title="刷新报告" aria-label="刷新报告" :disabled="loading" @click="fetchReport">
        <RefreshCw :size="18" :class="{ spinning: loading }" />
      </button>
    </header>

    <div v-if="loading && !report" class="state-panel">正在生成学情报告...</div>
    <div v-else-if="error" class="state-panel error-state">
      <span>{{ error }}</span>
      <button class="retry-button" @click="fetchReport"><RefreshCw :size="16" />重试</button>
    </div>
    <template v-else-if="report">
      <section class="metric-grid">
        <article class="metric"><span>平均掌握度</span><strong>{{ percent(report.overview.average_mastery) }}</strong></article>
        <article class="metric"><span>知识点</span><strong>{{ report.overview.knowledge_point_count }}</strong></article>
        <article class="metric warning"><span>薄弱知识点</span><strong>{{ report.overview.weak_point_count }}</strong></article>
        <article class="metric"><span>累计作答</span><strong>{{ report.overview.total_attempts }}</strong></article>
      </section>

      <div class="report-grid">
        <section class="panel radar-panel">
          <div class="panel-heading"><h2>知识掌握雷达</h2><span>{{ report.cache.hit ? '缓存' : '最新' }}</span></div>
          <KnowledgeRadar :points="report.radar" />
        </section>
        <section class="panel">
          <div class="panel-heading"><h2>学科掌握度</h2></div>
          <ScoreDistribution :items="subjectBars" />
        </section>
      </div>

      <div class="report-grid lower-grid">
        <section class="panel">
          <div class="panel-heading"><h2>薄弱知识点</h2><span>{{ report.weak_points.length }} 项</span></div>
          <div v-if="report.weak_points.length === 0" class="inline-empty">暂未发现明显薄弱点</div>
          <div v-else class="point-list">
            <article v-for="point in report.weak_points" :key="point.knowledge_point_id" class="point-row">
              <div><strong>{{ point.knowledge_point_name }}</strong><small>{{ point.subject_name }} · {{ point.attempt_count }} 次</small></div>
              <span class="value weak">{{ percent(point.mastery_level) }}</span>
            </article>
          </div>
        </section>
        <section class="panel">
          <div class="panel-heading"><h2>优势知识点</h2><span>{{ report.strengths.length }} 项</span></div>
          <div v-if="report.strengths.length === 0" class="inline-empty">继续积累作答数据</div>
          <div v-else class="point-list">
            <article v-for="point in report.strengths" :key="point.knowledge_point_id" class="point-row">
              <div><strong>{{ point.knowledge_point_name }}</strong><small>{{ point.subject_name }} · {{ point.attempt_count }} 次</small></div>
              <span class="value strong">{{ percent(point.mastery_level) }}</span>
            </article>
          </div>
        </section>
      </div>

      <section class="panel trend-panel">
        <div class="panel-heading"><h2>掌握度趋势</h2></div>
        <TrendChart :points="[]" />
      </section>
    </template>
  </div>
</template>

<style scoped>
.report-page { max-width: 1180px; margin: 0 auto; padding: 28px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 22px; }
.page-header h1 { margin: 0; color: #172033; font-size: 24px; }
.page-header p { margin: 3px 0 0; color: #64748b; font-size: 13px; }
.icon-button { width: 38px; height: 38px; display: grid; place-items: center; border: 1px solid #cbd5e1; border-radius: 7px; background: #fff; color: #475569; cursor: pointer; }
.icon-button:hover { color: #0f766e; border-color: #5eead4; }
.icon-button:disabled { opacity: .55; }
.spinning { animation: spin .8s linear infinite; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
.metric { min-height: 92px; padding: 16px 18px; background: #fff; border: 1px solid #e2e8f0; border-top: 3px solid #0f766e; border-radius: 8px; }
.metric.warning { border-top-color: #d97706; }
.metric span { display: block; color: #64748b; font-size: 12px; }
.metric strong { display: block; margin-top: 7px; color: #172033; font-size: 25px; line-height: 1; }
.report-grid { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, .9fr); gap: 16px; margin-bottom: 16px; }
.lower-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.panel { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; min-width: 0; }
.panel-heading { min-height: 28px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.panel-heading h2 { margin: 0; color: #253247; font-size: 15px; }
.panel-heading span { color: #94a3b8; font-size: 11px; }
.point-list { display: grid; }
.point-row { display: flex; justify-content: space-between; gap: 16px; align-items: center; padding: 12px 0; border-bottom: 1px solid #f1f5f9; }
.point-row:last-child { border-bottom: 0; }
.point-row strong { display: block; color: #334155; font-size: 13px; }
.point-row small { display: block; margin-top: 2px; color: #94a3b8; font-size: 11px; }
.value { font: 600 13px/1 var(--mono); }
.value.weak { color: #dc2626; }
.value.strong { color: #059669; }
.inline-empty, .state-panel { min-height: 140px; display: grid; place-items: center; color: #94a3b8; font-size: 13px; }
.state-panel { min-height: 360px; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; }
.error-state { gap: 12px; align-content: center; color: #b91c1c; }
.retry-button { display: inline-flex; align-items: center; gap: 7px; padding: 8px 12px; border: 1px solid #fecaca; border-radius: 6px; background: #fff; color: #b91c1c; cursor: pointer; }
.trend-panel { margin-bottom: 16px; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 820px) { .metric-grid { grid-template-columns: repeat(2, 1fr); } .report-grid, .lower-grid { grid-template-columns: 1fr; } }
@media (max-width: 520px) { .report-page { padding: 18px 14px; } .metric-grid { grid-template-columns: 1fr 1fr; gap: 8px; } .metric { min-height: 82px; padding: 14px; } }
</style>
