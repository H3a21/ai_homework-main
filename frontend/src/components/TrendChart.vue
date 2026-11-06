<script setup lang="ts">
import { computed } from 'vue'
import type { EChartsCoreOption } from 'echarts/core'
import EChartSurface from './EChartSurface.vue'

const props = defineProps<{ points: Array<{ label: string; value: number }> }>()

const option = computed<EChartsCoreOption>(() => ({
  color: ['#d97706'],
  grid: { left: 12, right: 18, top: 16, bottom: 34, containLabel: true },
  tooltip: {
    trigger: 'axis',
  },
  xAxis: {
    type: 'category',
    data: props.points.map(point => point.label),
    axisLabel: { color: '#64748b' },
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
    type: 'line',
    smooth: true,
    symbol: 'circle',
    symbolSize: 7,
    data: props.points.map(point => point.value),
    areaStyle: { color: 'rgba(245, 158, 11, 0.12)' },
    lineStyle: { width: 2 },
  }],
}))
</script>

<template>
  <div v-if="points.length < 2" class="chart-empty">积累两次以上报告后显示趋势</div>
  <EChartSurface v-else :option="option" height="240px" />
</template>

<style scoped>
.chart-empty { min-height: 180px; display: grid; place-items: center; color: #94a3b8; font-size: 14px; }
</style>
