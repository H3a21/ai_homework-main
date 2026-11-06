<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { AlertCircle, ImagePlus, LoaderCircle, Trash2, Upload } from '@lucide/vue'
import axios from 'axios'
import { useRoute, useRouter } from 'vue-router'
import { assignmentsApi, type AssignmentInfo } from '../../api/assignments'
import { submissionsApi } from '../../api/submissions'
import LatexRender from '../../components/LatexRender.vue'

type UploadStatus = 'ready' | 'uploading' | 'uploaded' | 'error'

interface PendingImage {
  id: string
  file: File
  previewUrl: string
  imagePath: string | null
  progress: number
  status: UploadStatus
  error: string
}

const MAX_IMAGES = 10
const MAX_IMAGE_BYTES = 10 * 1024 * 1024
const ALLOWED_TYPES = new Set(['image/png', 'image/jpeg'])

const route = useRoute()
const router = useRouter()
const assignmentId = Number(route.params.id)
const assignment = ref<AssignmentInfo | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const loading = ref(false)
const submitting = ref(false)
const images = ref<PendingImage[]>([])
const errorMessage = ref('')

const hasUploadingImage = computed(() =>
  images.value.some((image) => image.status === 'uploading'),
)
const canSubmit = computed(
  () => images.value.length > 0 && !submitting.value && !hasUploadingImage.value,
)

async function fetchAssignment() {
  loading.value = true
  try {
    const res = await assignmentsApi.get(assignmentId)
    assignment.value = res.data
  } finally {
    loading.value = false
  }
}

function openFilePicker() {
  fileInput.value?.click()
}

function addImages(event: Event) {
  const input = event.target as HTMLInputElement
  const selected = Array.from(input.files || [])
  input.value = ''
  errorMessage.value = ''

  const remaining = MAX_IMAGES - images.value.length
  if (selected.length > remaining) {
    errorMessage.value = `每次最多上传 ${MAX_IMAGES} 张图片，已保留前 ${remaining} 张。`
  }

  for (const file of selected.slice(0, Math.max(remaining, 0))) {
    if (!ALLOWED_TYPES.has(file.type)) {
      errorMessage.value = `${file.name} 不是支持的 PNG 或 JPEG 图片。`
      continue
    }
    if (file.size > MAX_IMAGE_BYTES) {
      errorMessage.value = `${file.name} 超过 10 MB。`
      continue
    }
    images.value.push({
      id: `${Date.now()}-${crypto.randomUUID()}`,
      file,
      previewUrl: URL.createObjectURL(file),
      imagePath: null,
      progress: 0,
      status: 'ready',
      error: '',
    })
  }
}

function removeImage(index: number) {
  const [removed] = images.value.splice(index, 1)
  if (removed) URL.revokeObjectURL(removed.previewUrl)
}

function uploadErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
  }
  return '图片上传失败，请检查网络后重试。'
}

async function uploadImage(image: PendingImage) {
  if (image.status === 'uploaded' && image.imagePath) return
  image.status = 'uploading'
  image.progress = 0
  image.error = ''
  try {
    const response = await submissionsApi.uploadImage(image.file, (progress) => {
      image.progress = progress
    })
    image.imagePath = response.data.image_path
    image.progress = 100
    image.status = 'uploaded'
  } catch (error) {
    image.status = 'error'
    image.error = uploadErrorMessage(error)
  }
}

async function handleSubmit() {
  if (!canSubmit.value) return
  submitting.value = true
  errorMessage.value = ''
  try {
    await Promise.all(images.value.map(uploadImage))
    const failed = images.value.filter((image) => image.status === 'error')
    if (failed.length > 0) {
      errorMessage.value = `${failed.length} 张图片上传失败，请重试提交。`
      return
    }

    const response = await submissionsApi.create({
      assignment_id: assignmentId,
      image_paths: images.value.map((image) => image.imagePath as string),
      auto_grade: true,
    })
    router.push(`/student/result/${response.data.id}`)
  } catch (error) {
    errorMessage.value = uploadErrorMessage(error)
  } finally {
    submitting.value = false
  }
}

onMounted(fetchAssignment)
onUnmounted(() => {
  for (const image of images.value) URL.revokeObjectURL(image.previewUrl)
})
</script>

<template>
  <div class="page">
    <header class="page-header">
      <h1>提交作业</h1>
      <p v-if="assignment" class="subtitle">
        {{ assignment.title }} · {{ assignment.subject_name }}
      </p>
    </header>

    <div v-if="loading" class="loading">加载中...</div>
    <template v-else-if="assignment">
      <section class="panel">
        <h2>作业题目</h2>
        <div v-for="q in assignment.questions" :key="q.id" class="question-item">
          <span class="q-num">{{ q.question_number }}.</span>
          <LatexRender :text="q.content || `题目 ${q.question_number}`" />
          <span class="q-score">{{ q.max_score }} 分</span>
        </div>
      </section>

      <section class="panel">
        <div class="panel-heading">
          <div>
            <h2>作业图片</h2>
            <p>PNG / JPEG · 单张不超过 10 MB · 最多 10 张</p>
          </div>
          <span class="image-count">{{ images.length }}/{{ MAX_IMAGES }}</span>
        </div>

        <input
          ref="fileInput"
          data-testid="submission-images"
          class="file-input"
          type="file"
          accept=".png,.jpg,.jpeg,image/png,image/jpeg"
          multiple
          @change="addImages"
        />

        <button
          data-testid="add-image"
          class="upload-zone"
          type="button"
          :disabled="images.length >= MAX_IMAGES || submitting"
          @click="openFilePicker"
        >
          <ImagePlus :size="22" aria-hidden="true" />
          <span>选择作业图片</span>
        </button>

        <div v-if="images.length" class="image-grid">
          <article v-for="(image, index) in images" :key="image.id" class="image-item">
            <div class="preview-wrap">
              <img :src="image.previewUrl" :alt="image.file.name" />
              <div v-if="image.status === 'uploading'" class="upload-progress">
                <LoaderCircle class="spin" :size="20" aria-hidden="true" />
                <span>{{ image.progress }}%</span>
              </div>
            </div>
            <div class="image-meta">
              <span class="image-name" :title="image.file.name">{{ image.file.name }}</span>
              <span v-if="image.status === 'error'" class="image-error">上传失败</span>
              <span v-else class="image-size">{{ (image.file.size / 1024 / 1024).toFixed(1) }} MB</span>
              <button
                class="icon-button"
                type="button"
                title="移除图片"
                :disabled="image.status === 'uploading'"
                @click="removeImage(index)"
              >
                <Trash2 :size="16" aria-hidden="true" />
              </button>
            </div>
          </article>
        </div>

        <p v-if="errorMessage" class="error-message" role="alert">
          <AlertCircle :size="16" aria-hidden="true" />
          {{ errorMessage }}
        </p>
      </section>

      <div class="form-actions">
        <button class="btn btn-ghost" type="button" :disabled="submitting" @click="router.back()">
          返回
        </button>
        <button
          data-testid="submit-assignment"
          class="btn btn-primary"
          type="button"
          :disabled="!canSubmit"
          @click="handleSubmit"
        >
          <LoaderCircle v-if="submitting" class="spin" :size="17" aria-hidden="true" />
          <Upload v-else :size="17" aria-hidden="true" />
          {{ submitting ? '正在提交' : '提交作业' }}
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page { padding: 32px; max-width: 800px; margin: 0 auto; }
.page-header { margin-bottom: 24px; }
.page-header h1 { margin: 0; font-size: 24px; font-weight: 700; color: #172033; }
.subtitle { margin: 4px 0 0; color: #667085; font-size: 14px; }
.loading { text-align: center; padding: 64px; color: #98a2b3; }
.panel { background: #fff; border: 1px solid #e4e7ec; border-radius: 8px; padding: 24px; margin-bottom: 20px; }
.panel h2 { margin: 0 0 16px; font-size: 16px; color: #172033; }
.panel-heading { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 14px; }
.panel-heading h2 { margin-bottom: 4px; }
.panel-heading p { margin: 0; font-size: 13px; color: #667085; }
.image-count { flex: 0 0 auto; font-size: 13px; color: #475467; font-variant-numeric: tabular-nums; }
.question-item { display: flex; gap: 12px; align-items: center; padding: 10px 0; border-bottom: 1px solid #eef0f3; }
.question-item:last-child { border-bottom: none; }
.q-num { font-weight: 600; color: #475467; min-width: 24px; }
.q-score { margin-left: auto; font-size: 13px; color: #667085; white-space: nowrap; }
.file-input { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0, 0, 0, 0); }
.upload-zone { width: 100%; min-height: 86px; display: flex; align-items: center; justify-content: center; gap: 9px; border: 1px dashed #98a2b3; border-radius: 8px; background: #f9fafb; color: #344054; font: inherit; font-size: 14px; font-weight: 600; cursor: pointer; }
.upload-zone:hover { border-color: #0f766e; background: #f0fdfa; color: #0f766e; }
.upload-zone:disabled { opacity: 0.5; cursor: not-allowed; }
.image-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 14px; }
.image-item { min-width: 0; border: 1px solid #e4e7ec; border-radius: 8px; overflow: hidden; background: #fff; }
.preview-wrap { position: relative; width: 100%; aspect-ratio: 4 / 3; background: #f2f4f7; }
.preview-wrap img { width: 100%; height: 100%; display: block; object-fit: cover; }
.upload-progress { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; gap: 7px; background: rgba(23, 32, 51, 0.72); color: #fff; font-size: 13px; font-variant-numeric: tabular-nums; }
.image-meta { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2px 8px; align-items: center; padding: 9px 8px; }
.image-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; color: #344054; }
.image-size, .image-error { grid-column: 1; font-size: 11px; color: #667085; }
.image-error { color: #b42318; }
.icon-button { grid-column: 2; grid-row: 1 / span 2; width: 30px; height: 30px; display: inline-flex; align-items: center; justify-content: center; border: 0; border-radius: 6px; background: transparent; color: #667085; cursor: pointer; }
.icon-button:hover { color: #b42318; background: #fef3f2; }
.icon-button:disabled { opacity: 0.45; cursor: not-allowed; }
.error-message { display: flex; align-items: center; gap: 7px; margin: 14px 0 0; color: #b42318; font-size: 13px; }
.form-actions { display: flex; gap: 12px; justify-content: flex-end; }
.btn { min-height: 40px; display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 9px 18px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; border: 1px solid transparent; }
.btn-primary { background: #0f766e; color: #fff; }
.btn-primary:hover { background: #115e59; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-ghost { background: #fff; color: #475467; border-color: #d0d5dd; }
.btn-ghost:hover { background: #f9fafb; }
.spin { animation: spin 0.9s linear infinite; }

@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 640px) {
  .page { padding: 20px 16px; }
  .panel { padding: 18px 16px; }
  .image-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .form-actions { flex-direction: column-reverse; }
  .btn { width: 100%; }
}
</style>
