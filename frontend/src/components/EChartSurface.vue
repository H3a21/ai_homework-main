<script setup lang="ts">
import { BarChart, LineChart, RadarChart } from 'echarts/charts'
import {
  GridComponent,
  RadarComponent,
  TooltipComponent,
} from 'echarts/components'
import { use, init, type ECharts, type EChartsCoreOption } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

use([
  BarChart,
  LineChart,
  RadarChart,
  GridComponent,
  RadarComponent,
  TooltipComponent,
  CanvasRenderer,
])

const props = withDefaults(defineProps<{
  option: EChartsCoreOption
  height?: string
}>(), {
  height: '280px',
})

const chartElement = ref<HTMLElement | null>(null)
let chart: ECharts | null = null
let resizeObserver: ResizeObserver | null = null

function renderChart() {
  if (!chartElement.value) return
  if (!chart) chart = init(chartElement.value)
  chart.setOption(props.option, true)
}

onMounted(async () => {
  await nextTick()
  renderChart()
  if (chartElement.value) {
    resizeObserver = new ResizeObserver(() => chart?.resize())
    resizeObserver.observe(chartElement.value)
  }
})

watch(() => props.option, renderChart, { deep: true })

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div ref="chartElement" class="chart-surface" :style="{ height }" aria-label="数据图表" />
</template>

<style scoped>
.chart-surface { width: 100%; min-height: 180px; }
</style>
