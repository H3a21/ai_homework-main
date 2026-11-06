<script setup lang="ts">
import { computed } from 'vue'
import { AlertTriangle, CheckCircle2, LoaderCircle } from '@lucide/vue'
import type { GradingBatch } from '../api/gradingBatches'

const props = defineProps<{
  batch: GradingBatch
}>()

const statusLabel = computed(() => {
  if (props.batch.status === 'completed') return '批次已完成'
  if (props.batch.status === 'failed') return '批次部分失败'
  return '批量批改中'
})

const progress = computed(() => Math.min(100, Math.max(0, props.batch.progress_percent)))
</script>

<template>
  <section class="batch-progress" aria-live="polite">
    <div class="batch-heading">
      <component
        :is="batch.status === 'completed' ? CheckCircle2 : batch.status === 'failed' ? AlertTriangle : LoaderCircle"
        :size="18"
        :class="['status-icon', { spinning: batch.status === 'grading' || batch.status === 'pending' }]"
        aria-hidden="true"
      />
      <div>
        <strong>{{ statusLabel }}</strong>
        <span>批次 #{{ batch.id }}</span>
      </div>
    </div>

    <div class="batch-counts">
      <span>完成 {{ batch.completed_submissions }}</span>
      <span v-if="batch.failed_submissions">失败 {{ batch.failed_submissions }}</span>
      <span>共 {{ batch.total_submissions }}</span>
    </div>

    <div class="progress-track" role="progressbar" :aria-valuenow="progress" aria-valuemin="0" aria-valuemax="100">
      <div class="progress-fill" :class="batch.status" :style="{ width: `${progress}%` }" />
    </div>
    <span class="progress-value">{{ progress.toFixed(0) }}%</span>
  </section>
</template>

<style scoped>
.batch-progress {
  display: grid;
  grid-template-columns: minmax(170px, 1fr) auto minmax(220px, 2fr) 52px;
  align-items: center;
  gap: 20px;
  min-height: 76px;
  padding: 14px 0;
  margin-bottom: 24px;
  border-top: 1px solid #e2e8f0;
  border-bottom: 1px solid #e2e8f0;
}
.batch-heading { display: flex; align-items: center; gap: 10px; color: #334155; }
.batch-heading div { min-width: 0; }
.batch-heading strong, .batch-heading span { display: block; }
.batch-heading strong { font-size: 14px; }
.batch-heading span { margin-top: 2px; font-size: 12px; color: #94a3b8; }
.status-icon { flex: 0 0 auto; color: #2563eb; }
.batch-progress:has(.progress-fill.completed) .status-icon { color: #059669; }
.batch-progress:has(.progress-fill.failed) .status-icon { color: #dc2626; }
.spinning { animation: spin 1.2s linear infinite; }
.batch-counts { display: flex; gap: 12px; white-space: nowrap; font-size: 13px; color: #64748b; }
.progress-track { height: 8px; overflow: hidden; border-radius: 4px; background: #e2e8f0; }
.progress-fill { height: 100%; background: #2563eb; transition: width 0.3s ease; }
.progress-fill.completed { background: #059669; }
.progress-fill.failed { background: #dc2626; }
.progress-value { width: 52px; text-align: right; font-variant-numeric: tabular-nums; font-size: 13px; font-weight: 600; color: #334155; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 760px) {
  .batch-progress { grid-template-columns: 1fr auto; gap: 10px 16px; }
  .batch-counts { justify-content: flex-end; }
  .progress-track { grid-column: 1; min-width: 0; }
  .progress-value { grid-column: 2; }
}
</style>
