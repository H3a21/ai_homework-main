<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ArrowLeft, RefreshCw } from '@lucide/vue'
import { useRoute, useRouter } from 'vue-router'
import { reportsApi, type ClassLearningReport, type KnowledgeRadarPoint } from '../../api/reports'
import KnowledgeRadar from '../../components/KnowledgeRadar.vue'
import ScoreDistribution from '../../components/ScoreDistribution.vue'

const route = useRoute()
const router = useRouter()
const classId = Number(route.params.id)
const report = ref<ClassLearningReport | null>(null)
const subjectId = ref<number | undefined>(undefined)
const loading = ref(false)
const error = ref('')

const radarPoints = computed<KnowledgeRadarPoint[]>(() => report.value?.knowledge_points.slice(0, 8).map(point => ({
  knowledge_point_id: point.knowledge_point_id,
  knowledge_point_name: point.knowledge_point_name,
  subject_id: point.subject_id,
  subject_name: point.subject_name,
  mastery_level: point.average_mastery,
  ability_theta: 0,
  attempt_count: point.total_attempts,
  average_score_ratio: point.average_mastery,
  is_weak: point.average_mastery < 0.6,
})) || [])

const studentBars = computed(() => report.value?.student_summaries.slice(0, 12).map(student => ({
  label: student.student_name,
  value: student.average_mastery,
})) || [])

async function fetchReport() {
  loading.value = true
  error.value = ''
  try {
    report.value = (await reportsApi.getClass(classId, subjectId.value)).data
  } catch {
    error.value = '班级学情报告加载失败'
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
      <div class="header-main">
        <button class="icon-button" title="返回班级" aria-label="返回班级" @click="router.push(`/teacher/classes/${classId}`)"><ArrowLeft :size="18" /></button>
        <div><h1>{{ report?.class_name || '班级学情' }}</h1><p>知识点覆盖、薄弱率和学生掌握度</p></div>
      </div>
      <div class="header-actions">
        <select v-model="subjectId" class="subject-select" @change="fetchReport">
          <option :value="undefined">全部学科</option>
          <option :value="1">数学</option><option :value="2">语文</option><option :value="3">英语</option>
        </select>
        <button class="icon-button" title="刷新报告" aria-label="刷新报告" :disabled="loading" @click="fetchReport"><RefreshCw :size="18" :class="{ spinning: loading }" /></button>
      </div>
    </header>

    <div v-if="loading && !report" class="state-panel">正在聚合班级数据...</div>
    <div v-else-if="error" class="state-panel error-state">{{ error }}</div>
    <template v-else-if="report">
      <section class="metric-grid">
        <article class="metric"><span>班级学生</span><strong>{{ report.overview.student_count }}</strong></article>
        <article class="metric"><span>已有数据</span><strong>{{ report.overview.students_with_data }}</strong></article>
        <article class="metric"><span>平均掌握度</span><strong>{{ percent(report.overview.average_mastery) }}</strong></article>
        <article class="metric warning"><span>薄弱知识点</span><strong>{{ report.overview.weak_point_count }}</strong></article>
      </section>

      <div class="report-grid">
        <section class="panel"><div class="panel-heading"><h2>班级知识雷达</h2><span>{{ report.cache.hit ? '缓存' : '最新' }}</span></div><KnowledgeRadar :points="radarPoints" /></section>
        <section class="panel"><div class="panel-heading"><h2>学生掌握度分布</h2></div><ScoreDistribution :items="studentBars" /></section>
      </div>

      <div class="report-grid lower-grid">
        <section class="panel">
          <div class="panel-heading"><h2>重点薄弱知识点</h2><span>{{ report.weak_knowledge_points.length }} 项</span></div>
          <div v-if="report.weak_knowledge_points.length === 0" class="inline-empty">暂无班级共性薄弱点</div>
          <div v-else class="point-list">
            <article v-for="point in report.weak_knowledge_points" :key="point.knowledge_point_id" class="point-row">
              <div><strong>{{ point.knowledge_point_name }}</strong><small>{{ point.subject_name }} · 覆盖 {{ point.covered_student_count }} 人</small></div>
              <div class="point-values"><span>{{ percent(point.average_mastery) }}</span><small>{{ percent(point.weak_rate) }} 薄弱</small></div>
            </article>
          </div>
        </section>
        <section class="panel table-panel">
          <div class="panel-heading"><h2>学生摘要</h2><span>{{ report.student_summaries.length }} 人</span></div>
          <div class="summary-table">
            <div class="table-row table-head"><span>学生</span><span>掌握度</span><span>薄弱点</span><span>作答</span></div>
            <div v-for="student in report.student_summaries" :key="student.student_id" class="table-row">
              <strong>{{ student.student_name }}</strong><span>{{ percent(student.average_mastery) }}</span><span>{{ student.weak_point_count }}</span><span>{{ student.total_attempts }}</span>
            </div>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.report-page { max-width: 1240px; margin: 0 auto; padding: 28px; }
.page-header, .header-main, .header-actions { display: flex; align-items: center; }
.page-header { justify-content: space-between; gap: 20px; margin-bottom: 22px; }
.header-main, .header-actions { gap: 12px; }
.page-header h1 { margin: 0; color: #172033; font-size: 24px; }
.page-header p { margin: 3px 0 0; color: #64748b; font-size: 13px; }
.icon-button { width: 38px; height: 38px; display: grid; place-items: center; border: 1px solid #cbd5e1; border-radius: 7px; background: #fff; color: #475569; cursor: pointer; }
.icon-button:hover { color: #0f766e; border-color: #5eead4; }
.subject-select { height: 38px; min-width: 126px; padding: 0 10px; border: 1px solid #cbd5e1; border-radius: 7px; background: #fff; color: #475569; }
.spinning { animation: spin .8s linear infinite; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
.metric { min-height: 92px; padding: 16px 18px; background: #fff; border: 1px solid #e2e8f0; border-top: 3px solid #2563eb; border-radius: 8px; }
.metric.warning { border-top-color: #d97706; }
.metric span { display: block; color: #64748b; font-size: 12px; }
.metric strong { display: block; margin-top: 7px; color: #172033; font-size: 25px; line-height: 1; }
.report-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-bottom: 16px; }
.lower-grid { grid-template-columns: minmax(0, .9fr) minmax(0, 1.1fr); }
.panel { min-width: 0; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; }
.panel-heading { min-height: 28px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.panel-heading h2 { margin: 0; color: #253247; font-size: 15px; }
.panel-heading span { color: #94a3b8; font-size: 11px; }
.point-row { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 12px 0; border-bottom: 1px solid #f1f5f9; }
.point-row strong { display: block; color: #334155; font-size: 13px; }
.point-row small { display: block; margin-top: 2px; color: #94a3b8; font-size: 11px; }
.point-values { text-align: right; color: #b45309; font: 600 12px/1.4 var(--mono); }
.summary-table { overflow-x: auto; }
.table-row { min-width: 460px; display: grid; grid-template-columns: minmax(140px, 1fr) 80px 72px 60px; align-items: center; min-height: 40px; border-bottom: 1px solid #f1f5f9; color: #64748b; font-size: 12px; }
.table-row strong { color: #334155; }
.table-head { color: #94a3b8; font-size: 11px; }
.inline-empty, .state-panel { min-height: 180px; display: grid; place-items: center; color: #94a3b8; font-size: 13px; }
.state-panel { min-height: 360px; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; }
.error-state { color: #b91c1c; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 860px) { .metric-grid { grid-template-columns: repeat(2, 1fr); } .report-grid, .lower-grid { grid-template-columns: 1fr; } }
@media (max-width: 560px) { .report-page { padding: 18px 14px; } .page-header { align-items: flex-start; } .header-actions { flex-direction: column-reverse; align-items: flex-end; } }
</style>
