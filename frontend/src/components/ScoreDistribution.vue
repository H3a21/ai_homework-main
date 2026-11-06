<script setup lang="ts">
import { computed } from 'vue'
import type { EChartsCoreOption } from 'echarts/core'
import EChartSurface from './EChartSurface.vue'

const props = defineProps<{ items: Array<{ label: string; value: number }> }>()

const option = computed<EChartsCoreOption>(() => ({
  color: ['#2563eb'],
  grid: { left: 12, right: 18, top: 16, bottom: 34, containLabel: true },
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
  },
  xAxis: {
    type: 'category',
    data: props.items.map(item => item.label),
    axisLabel: { color: '#64748b', interval: 0, rotate: props.items.length > 6 ? 30 : 0 },
    axisLine: { lineStyle: { color: '#cbd5e1' } },
  },
  yAxis: {
    type: 'value',
    min: 0,
    max: 1,
    axisLabel: { color: '#64748b', formatter: (value: number) => `${value * 100}%` },
    splitLine: { lineStyle: { color: '#e2e8f0' } },
  },
  series: [{
    type: 'bar',
    barMaxWidth: 28,
    data: props.items.map(item => item.value),
    itemStyle: { borderRadius: [4, 4, 0, 0] },
  }],
}))
</script>

<template>
  <div v-if="items.length === 0" class="chart-empty">暂无班级掌握度数据</div>
  <EChartSurface v-else :option="option" height="280px" />
</template>

<style scoped>
.chart-empty { min-height: 220px; display: grid; place-items: center; color: #94a3b8; font-size: 14px; }
</style>
