<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Maximize2, RotateCcw, ZoomIn, ZoomOut } from '@lucide/vue'

interface ViewerImage {
  id: number
  image_path: string
  page_number: number
}

const props = withDefaults(defineProps<{
  images: ViewerImage[]
  compare?: boolean
}>(), { compare: true })

const zoom = ref(1)
const leftIndex = ref(0)
const rightIndex = ref(Math.min(1, Math.max(props.images.length - 1, 0)))
const failed = ref<Set<number>>(new Set())

const leftImage = computed(() => props.images[leftIndex.value])
const rightImage = computed(() => props.images[rightIndex.value])

watch(() => props.images.length, length => {
  leftIndex.value = Math.min(leftIndex.value, Math.max(length - 1, 0))
  rightIndex.value = Math.min(1, Math.max(length - 1, 0))
})

function source(path: string) {
  if (/^(https?:)?\/\//.test(path) || path.startsWith('/')) return path
  return `/${path.replace(/^\\+/, '')}`
}

function markFailed(id: number) {
  failed.value = new Set([...failed.value, id])
}

function reset() { zoom.value = 1 }
function increase() { zoom.value = Math.min(2.5, Number((zoom.value + 0.25).toFixed(2))) }
function decrease() { zoom.value = Math.max(0.5, Number((zoom.value - 0.25).toFixed(2))) }
</script>

<template>
  <section class="viewer-panel">
    <div class="viewer-toolbar">
      <div class="viewer-label">作业图片</div>
      <div class="viewer-actions">
        <button title="缩小" aria-label="缩小" @click="decrease"><ZoomOut :size="16" /></button>
        <span>{{ Math.round(zoom * 100) }}%</span>
        <button title="放大" aria-label="放大" @click="increase"><ZoomIn :size="16" /></button>
        <button title="重置缩放" aria-label="重置缩放" @click="reset"><RotateCcw :size="16" /></button>
        <button title="适应窗口" aria-label="适应窗口" @click="reset"><Maximize2 :size="16" /></button>
      </div>
    </div>

    <div v-if="images.length === 0" class="viewer-empty">暂无作业图片</div>
    <div v-else class="viewer-grid" :class="{ single: !compare || images.length < 2 }">
      <div v-for="(image, index) in (compare && images.length > 1 ? [leftImage, rightImage] : [leftImage])" :key="`${image.id}-${index}`" class="image-stage">
        <div class="stage-label">第 {{ image.page_number }} 页</div>
        <div v-if="failed.has(image.id)" class="image-error">图片暂时无法加载<br /><small>{{ image.image_path }}</small></div>
        <img
          v-else
          :src="source(image.image_path)"
          :alt="`作业第 ${image.page_number} 页`"
          :style="{ transform: `scale(${zoom})` }"
          @error="markFailed(image.id)"
        />
      </div>
    </div>
  </section>
</template>

<style scoped>
.viewer-panel { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }
.viewer-toolbar { min-height: 48px; display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid #e2e8f0; }
.viewer-label { color: #334155; font-size: 13px; font-weight: 600; }
.viewer-actions { display: flex; align-items: center; gap: 8px; color: #64748b; font-size: 12px; }
.viewer-actions button { width: 30px; height: 30px; display: grid; place-items: center; border: 1px solid #e2e8f0; background: #fff; color: #475569; border-radius: 6px; cursor: pointer; }
.viewer-actions button:hover { color: #0f766e; border-color: #99f6e4; background: #f0fdfa; }
.viewer-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1px; background: #e2e8f0; }
.viewer-grid.single { grid-template-columns: minmax(0, 1fr); }
.image-stage { min-height: 300px; overflow: auto; position: relative; display: grid; place-items: center; background: #f8fafc; padding: 36px 16px 16px; }
.stage-label { position: absolute; top: 10px; left: 12px; color: #64748b; font-size: 12px; }
.image-stage img { max-width: 100%; max-height: 520px; object-fit: contain; transform-origin: center center; transition: transform 0.15s ease; }
.viewer-empty, .image-error { min-height: 260px; display: grid; place-items: center; text-align: center; color: #94a3b8; font-size: 14px; }
.image-error small { color: #cbd5e1; word-break: break-all; }
@media (max-width: 720px) { .viewer-grid { grid-template-columns: 1fr; } .viewer-grid:not(.single) .image-stage:nth-child(2) { display: none; } }
</style>
