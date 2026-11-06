<script setup lang="ts">
import { computed } from 'vue'
import type { EChartsCoreOption } from 'echarts/core'
import type { KnowledgeRadarPoint } from '../api/reports'
import EChartSurface from './EChartSurface.vue'

const props = defineProps<{ points: KnowledgeRadarPoint[] }>()

const option = computed<EChartsCoreOption>(() => {
  const points = props.points.slice(0, 8)
  return {
    color: ['#0f766e'],
    tooltip: {
      trigger: 'item',
    },
    radar: {
      indicator: points.map(point => ({
        name: point.knowledge_point_name.length > 10
          ? `${point.knowledge_point_name.slice(0, 10)}...`
          : point.knowledge_point_name,
        max: 1,
      })),
      center: ['50%', '52%'],
      radius: '64%',
      splitNumber: 4,
      axisName: { color: '#475569', fontSize: 12 },
      splitLine: { lineStyle: { color: ['#dbeafe', '#cbd5e1'] } },
      splitArea: { areaStyle: { color: ['#f8fafc', '#ffffff'] } },
      axisLine: { lineStyle: { color: '#cbd5e1' } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: points.map(point => point.mastery_level),
        name: '掌握度',
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2, color: '#0f766e' },
        itemStyle: { color: '#0f766e' },
        areaStyle: { color: 'rgba(20, 184, 166, 0.2)' },
      }],
    }],
  }
})
</script>

<template>
  <div v-if="points.length === 0" class="chart-empty">暂无知识点掌握数据</div>
  <EChartSurface v-else :option="option" height="320px" />
</template>

<style scoped>
.chart-empty { min-height: 220px; display: grid; place-items: center; color: #94a3b8; font-size: 14px; }
</style>
