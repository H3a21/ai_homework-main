<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { classesApi, type ClassInfo } from '../../api/classes'
import { assignmentsApi } from '../../api/assignments'
import QuestionEditor from '../../components/QuestionEditor.vue'

const router = useRouter()
const classes = ref<ClassInfo[]>([])
const subjects = [
  { id: 1, name: '数学', hint: '支持 $$\\LaTeX$$ 公式，如 $\\int_{0}^{1} x^2 dx$' },
  { id: 2, name: '语文', hint: '输入作文题目或阅读理解文本' },
  { id: 3, name: '英语', hint: '输入英语题目或写作要求' },
]

const title = ref('')
const classId = ref<number | null>(null)
const subjectId = ref<number | null>(null)
const dueDate = ref('')
const questions = ref<Array<{ content: string; max_score: number }>>([
  { content: '', max_score: 10 },
])
const loading = ref(false)
const subjectHint = ref('')

function onSubjectChange() {
  const s = subjects.find(s => s.id === subjectId.value)
  subjectHint.value = s?.hint || ''
}

function addQuestion() {
  questions.value.push({ content: '', max_score: 10 })
}

function removeQuestion(index: number) {
  questions.value.splice(index, 1)
}

function updateQuestion(index: number, val: { content: string; max_score: number }) {
  questions.value[index] = val
}

async function fetchClasses() {
  const res = await classesApi.list()
  classes.value = res.data
}

async function handleSubmit() {
  if (!title.value.trim() || !classId.value || !subjectId.value) return
  loading.value = true
  try {
    await assignmentsApi.create({
      title: title.value.trim(),
      class_id: classId.value,
      subject_id: subjectId.value,
      due_date: dueDate.value || undefined,
      questions: questions.value
        .map((q, i) => ({ question_number: i + 1, content: q.content, max_score: q.max_score }))
        .filter(q => q.content.trim()),
    })
    router.push('/teacher/assignments')
  } finally {
    loading.value = false
  }
}

onMounted(fetchClasses)
</script>

<template>
  <div class="page">
    <header class="page-header">
      <h1>布置作业</h1>
    </header>

    <div class="form-card">
      <div class="form-group">
        <label>作业标题</label>
        <input v-model="title" placeholder="如：第三章综合练习" class="input" />
      </div>

      <div class="form-row">
        <div class="form-group">
          <label>目标班级</label>
          <select v-model="classId" class="input">
            <option :value="null" disabled>选择班级</option>
            <option v-for="c in classes" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>学科</label>
          <select v-model="subjectId" class="input" @change="onSubjectChange">
            <option :value="null" disabled>选择学科</option>
            <option v-for="s in subjects" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
          <p v-if="subjectHint" class="field-hint">{{ subjectHint }}</p>
        </div>
        <div class="form-group">
          <label>截止日期</label>
          <input v-model="dueDate" type="date" class="input" />
        </div>
      </div>

      <div class="questions-section">
        <div class="section-header">
          <label>题目列表</label>
          <span class="q-count">{{ questions.length }} 题</span>
        </div>

        <QuestionEditor
          v-for="(q, i) in questions"
          :key="i"
          :model-value="q"
          :question-number="i + 1"
          @update:model-value="updateQuestion(i, $event)"
          @remove="removeQuestion(i)"
        />

        <div class="add-actions">
          <button class="btn btn-ghost" @click="addQuestion">+ 添加题目</button>
        </div>
      </div>

      <div class="form-actions">
        <button class="btn btn-primary" :disabled="loading || !title.trim() || !classId || !subjectId" @click="handleSubmit">
          {{ loading ? '提交中...' : '发布作业' }}
        </button>
        <button class="btn btn-ghost" @click="router.back()">取消</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 32px; max-width: 960px; margin: 0 auto; }
.page-header { margin-bottom: 24px; }
.page-header h1 { margin: 0; font-size: 24px; font-weight: 700; color: #1e293b; }
.form-card { background: #fff; border-radius: 12px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.form-group { display: flex; flex-direction: column; gap: 6px; margin-bottom: 20px; }
.form-group label { font-size: 13px; font-weight: 600; color: #1e293b; }
.field-hint { margin: 4px 0 0; font-size: 12px; color: #94a3b8; }
.form-row { display: flex; gap: 16px; }
.form-row .form-group { flex: 1; }
.input { padding: 10px 14px; border: 1.5px solid #e2e8f0; border-radius: 8px; font-size: 14px; outline: none; width: 100%; }
.input:focus { border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,0.1); }
.questions-section { margin-bottom: 24px; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.section-header label { font-size: 13px; font-weight: 600; color: #1e293b; }
.q-count { font-size: 12px; color: #94a3b8; background: #f1f5f9; padding: 2px 10px; border-radius: 12px; }
.add-actions { text-align: center; padding: 8px 0; }
.btn { padding: 10px 20px; border-radius: 8px; font-size: 14px; font-weight: 500; cursor: pointer; border: none; transition: all 0.2s; }
.btn-primary { background: #6366f1; color: #fff; }
.btn-primary:hover { background: #4f46e5; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-ghost { background: transparent; color: #64748b; border: 1px solid #e2e8f0; }
.btn-ghost:hover { background: #f8fafc; }
.form-actions { display: flex; gap: 12px; justify-content: flex-end; padding-top: 20px; border-top: 1px solid #f1f5f9; }
</style>
