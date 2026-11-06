<script setup lang="ts">
interface QuestionResult {
  id: number
  question_number: number
  content: string
  max_score: number
  score: number | null
  feedback: string | null
}

defineProps<{ questions: QuestionResult[] }>()
</script>

<template>
  <section class="step-panel">
    <div class="step-header">
      <div>
        <h3>逐题对比</h3>
        <p>得分、完成度与批改反馈</p>
      </div>
      <span class="step-count">{{ questions.length }} 题</span>
    </div>
    <div v-if="questions.length === 0" class="step-empty">暂无逐题结果</div>
    <div v-else class="step-list">
      <article v-for="question in questions" :key="question.id" class="step-row">
        <div class="step-index">{{ String(question.question_number).padStart(2, '0') }}</div>
        <div class="step-content">
          <div class="step-title">{{ question.content || `题目 ${question.question_number}` }}</div>
          <div class="score-track"><span :style="{ width: `${question.score != null && question.max_score > 0 ? Math.min(100, question.score / question.max_score * 100) : 0}%` }" /></div>
          <p v-if="question.feedback" class="step-feedback">{{ question.feedback }}</p>
        </div>
        <div class="step-score" :class="{ complete: question.score != null && question.score >= question.max_score }">
          {{ question.score != null ? `${question.score}/${question.max_score}` : '--' }}
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.step-panel { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; }
.step-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 16px; }
.step-header h3 { margin: 0; color: #1e293b; font-size: 16px; }
.step-header p { margin: 4px 0 0; color: #94a3b8; font-size: 12px; }
.step-count { color: #64748b; font-size: 12px; }
.step-list { display: grid; gap: 2px; }
.step-row { display: grid; grid-template-columns: 36px minmax(0, 1fr) auto; gap: 12px; align-items: start; padding: 14px 0; border-bottom: 1px solid #f1f5f9; }
.step-row:last-child { border-bottom: 0; }
.step-index { color: #0f766e; font: 600 12px/1 var(--mono); padding-top: 3px; }
.step-title { color: #334155; font-size: 13px; line-height: 1.5; word-break: break-word; }
.score-track { height: 5px; margin-top: 9px; overflow: hidden; background: #f1f5f9; border-radius: 3px; }
.score-track span { display: block; height: 100%; background: #14b8a6; border-radius: inherit; transition: width 0.25s ease; }
.step-feedback { margin: 8px 0 0; color: #64748b; font-size: 12px; line-height: 1.5; }
.step-score { min-width: 54px; color: #64748b; font-size: 13px; font-weight: 600; text-align: right; }
.step-score.complete { color: #059669; }
.step-empty { min-height: 120px; display: grid; place-items: center; color: #94a3b8; font-size: 13px; }
</style>
