<script setup lang="ts">
import { computed } from 'vue'
import LatexRender from './LatexRender.vue'

const props = defineProps<{
  modelValue: { content: string; max_score: number }
  questionNumber: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: { content: string; max_score: number }]
  remove: []
}>()

const preview = computed(() => props.modelValue.content)

function update(field: 'content' | 'max_score', value: string | number) {
  emit('update:modelValue', { ...props.modelValue, [field]: value })
}

const latexHints = [
  { label: 'x²', insert: 'x^2' },
  { label: '√', insert: '\\sqrt{x}' },
  { label: '分数', insert: '\\frac{a}{b}' },
  { label: '求和', insert: '\\sum_{i=1}^{n}' },
  { label: '积分', insert: '\\int_{a}^{b}' },
  { label: '方程组', insert: '\\begin{cases} x + y = 1 \\\\ x - y = 2 \\end{cases}' },
]

function insertLatex(hint: { insert: string }) {
  const textarea = document.getElementById(`q-content-${props.questionNumber}`) as HTMLTextAreaElement
  if (!textarea) return
  const start = textarea.selectionStart
  const end = textarea.selectionEnd
  const before = props.modelValue.content.substring(0, start)
  const after = props.modelValue.content.substring(end)
  const newContent = before + '$$' + hint.insert + '$$' + after
  update('content', newContent)
  requestAnimationFrame(() => {
    textarea.focus()
    textarea.setSelectionRange(start + hint.insert.length + 4, start + hint.insert.length + 4)
  })
}

function handleImageUpload(event: Event) {
  const input = event.target as HTMLInputElement
  if (!input.files?.length) return
  const file = input.files[0]
  const reader = new FileReader()
  reader.onload = (e) => {
    const dataUrl = e.target?.result as string
    const markdown = `![image](${dataUrl})`
    update('content', props.modelValue.content + '\n' + markdown)
  }
  reader.readAsDataURL(file)
}
</script>

<template>
  <div class="question-editor">
    <div class="qe-header">
      <span class="qe-num">第 {{ questionNumber }} 题</span>
      <span class="qe-score">
        分值:
        <input
          type="number"
          :value="modelValue.max_score"
          @input="update('max_score', Number(($event.target as HTMLInputElement).value))"
          class="score-input"
          min="0"
          step="0.5"
        />
      </span>
      <button class="btn-icon" @click="$emit('remove')" title="删除题目">✕</button>
    </div>

    <div class="qe-body">
      <div class="qe-editor">
        <div class="toolbar">
          <span class="toolbar-label">公式模板:</span>
          <button
            v-for="hint in latexHints"
            :key="hint.label"
            class="latex-btn"
            @click="insertLatex(hint)"
            :title="hint.insert"
          >{{ hint.label }}</button>
          <label class="upload-btn" title="上传图片">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
            图片
            <input type="file" accept="image/*" hidden @change="handleImageUpload" />
          </label>
        </div>
        <textarea
          :id="`q-content-${questionNumber}`"
          :value="modelValue.content"
          @input="update('content', ($event.target as HTMLTextAreaElement).value)"
          class="qe-textarea"
          :placeholder="'输入题目内容，支持 $$LaTeX$$ 公式\n例如: 计算 $$\\int_{0}^{1} x^2 dx$$'"
          rows="4"
        />
      </div>
      <div class="qe-preview">
        <div class="preview-label">预览</div>
        <div class="preview-content">
          <LatexRender :text="preview || '（题目内容将在这里预览）'" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.question-editor { border: 1.5px solid #e2e8f0; border-radius: 12px; overflow: hidden; margin-bottom: 16px; }
.qe-header { display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: #f8fafc; border-bottom: 1px solid #e2e8f0; }
.qe-num { font-weight: 600; color: #6366f1; font-size: 14px; }
.qe-score { margin-left: auto; font-size: 13px; color: #64748b; display: flex; align-items: center; gap: 6px; }
.score-input { width: 60px; padding: 4px 8px; border: 1.5px solid #e2e8f0; border-radius: 6px; font-size: 13px; text-align: center; outline: none; }
.score-input:focus { border-color: #6366f1; }
.btn-icon { background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 16px; padding: 4px 8px; border-radius: 4px; }
.btn-icon:hover { color: #ef4444; background: #fef2f2; }
.qe-body { display: grid; grid-template-columns: 1fr 1fr; }
.toolbar { display: flex; align-items: center; gap: 6px; padding: 8px 12px; border-bottom: 1px solid #e2e8f0; flex-wrap: wrap; background: #fafafa; }
.toolbar-label { font-size: 12px; color: #94a3b8; margin-right: 4px; }
.latex-btn { padding: 3px 10px; border: 1px solid #e2e8f0; border-radius: 4px; background: #fff; font-size: 12px; cursor: pointer; color: #475569; transition: all 0.15s; }
.latex-btn:hover { border-color: #6366f1; color: #6366f1; background: #eef2ff; }
.upload-btn { display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px; border: 1px solid #e2e8f0; border-radius: 4px; background: #fff; font-size: 12px; cursor: pointer; color: #475569; }
.upload-btn:hover { border-color: #10b981; color: #10b981; background: #ecfdf5; }
.qe-textarea { width: 100%; border: none; padding: 12px; font-size: 14px; font-family: inherit; resize: vertical; outline: none; min-height: 120px; line-height: 1.6; }
.qe-preview { border-left: 1px solid #e2e8f0; display: flex; flex-direction: column; }
.preview-label { padding: 8px 12px; font-size: 12px; color: #94a3b8; background: #fafafa; border-bottom: 1px solid #e2e8f0; }
.preview-content { padding: 12px; overflow-x: auto; font-size: 15px; min-height: 120px; }
</style>
