<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { BarChart3, UserPlus } from '@lucide/vue'
import { classesApi, type ClassInfo } from '../../api/classes'
import { studentsApi, type StudentInfo } from '../../api/students'
import { assignmentsApi, type AssignmentInfo } from '../../api/assignments'
import { submissionsApi, type SubmissionInfo } from '../../api/submissions'

const route = useRoute()
const router = useRouter()
const classId = Number(route.params.id)
const cls = ref<ClassInfo | null>(null)
const assignments = ref<AssignmentInfo[]>([])
const submissions = ref<SubmissionInfo[]>([])
const loading = ref(false)
const showAddStudent = ref(false)
const students = ref<StudentInfo[]>([])
const selectedStudentId = ref<number | null>(null)

async function fetchData() {
  loading.value = true
  try {
    const [clsRes, asgRes, subRes] = await Promise.all([
      classesApi.get(classId),
      assignmentsApi.list(classId),
      submissionsApi.list({ assignment_id: undefined }),
    ])
    cls.value = clsRes.data
    assignments.value = asgRes.data
    submissions.value = subRes.data.filter(s => {
      return asgRes.data.some(a => a.id === s.assignment_id)
    })
  } finally {
    loading.value = false
  }
}

async function loadStudents() {
  const res = await studentsApi.list()
  students.value = res.data
}

function openAddStudent() {
  loadStudents()
  showAddStudent.value = true
  selectedStudentId.value = null
}

async function addStudent() {
  if (!selectedStudentId.value) return
  await classesApi.addStudent(classId, selectedStudentId.value)
  showAddStudent.value = false
  await fetchData()
}

onMounted(fetchData)
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1>{{ cls?.name || '班级详情' }}</h1>
        <p class="subtitle">邀请码: {{ cls?.invite_code }} · {{ cls?.grade || '未设置年级' }}</p>
      </div>
      <div class="header-actions">
        <button class="btn btn-report" @click="router.push(`/teacher/classes/${classId}/report`)"><BarChart3 :size="16" />班级学情</button>
        <button class="btn btn-primary" @click="openAddStudent"><UserPlus :size="16" />添加学生</button>
      </div>
    </header>

    <div v-if="showAddStudent" class="modal-overlay" @click.self="showAddStudent = false">
      <div class="modal">
        <h3>添加学生</h3>
        <select v-model="selectedStudentId" class="input">
          <option :value="null" disabled>选择学生</option>
          <option v-for="s in students" :key="s.id" :value="s.id">{{ s.display_name }} ({{ s.username }})</option>
        </select>
        <div class="modal-actions">
          <button class="btn btn-primary" :disabled="!selectedStudentId" @click="addStudent">添加</button>
          <button class="btn btn-ghost" @click="showAddStudent = false">取消</button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <template v-else>
      <section class="section">
        <h2>班级成员 ({{ cls?.members?.length || 0 }})</h2>
        <div class="member-list">
          <div v-for="m in cls?.members" :key="m.id" class="member-item">
            <div class="member-avatar">{{ m.display_name[0] }}</div>
            <div class="member-info">
              <span class="member-name">{{ m.display_name }}</span>
              <span class="member-role">{{ m.class_role === 'head_teacher' ? '班主任' : m.class_role === 'teacher' ? '老师' : '学生' }}</span>
            </div>
          </div>
        </div>
      </section>

      <section class="section">
        <h2>作业 ({{ assignments.length }})</h2>
        <div v-if="assignments.length === 0" class="empty">暂未布置作业</div>
        <div v-else class="asg-list">
          <div v-for="a in assignments" :key="a.id" class="asg-item">
            <div class="asg-main">
              <strong>{{ a.title }}</strong>
              <span class="tag">{{ a.subject_name }}</span>
              <span class="meta">{{ a.question_count }} 题 · {{ a.due_date ? '截止 ' + a.due_date : '无截止日期' }}</span>
            </div>
          </div>
        </div>
      </section>

      <section class="section">
        <h2>提交记录 ({{ submissions.length }})</h2>
        <div v-if="submissions.length === 0" class="empty">暂无提交</div>
        <div v-else class="sub-list">
          <div v-for="s in submissions" :key="s.id" class="sub-item">
            <span>{{ s.student_name }}</span>
            <span class="tag" :class="s.status">{{ s.status === 'completed' ? '已批改' : s.status === 'grading' ? '批改中' : '待批改' }}</span>
            <span>{{ s.total_score != null ? s.total_score + ' 分' : '' }}</span>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.page { padding: 32px; max-width: 1200px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 32px; }
.page-header h1 { margin: 0; font-size: 24px; font-weight: 700; color: #1e293b; }
.subtitle { margin: 4px 0 0; color: #64748b; font-size: 14px; }
.section { background: #fff; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.section h2 { margin: 0 0 16px; font-size: 16px; color: #1e293b; }
.loading, .empty { text-align: center; padding: 48px; color: #94a3b8; }
.header-actions { display: flex; gap: 8px; }
.btn { min-height: 38px; display: inline-flex; align-items: center; gap: 7px; padding: 8px 14px; border-radius: 7px; font-size: 13px; font-weight: 500; cursor: pointer; border: none; transition: all 0.2s; }
.btn-primary { background: #6366f1; color: #fff; }
.btn-primary:hover { background: #4f46e5; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-ghost { background: transparent; color: #64748b; border: 1px solid #e2e8f0; }
.btn-ghost:hover { background: #f8fafc; }
.btn-report { background: #fff; color: #0f766e; border: 1px solid #99f6e4; }
.btn-report:hover { background: #f0fdfa; }
.input { padding: 10px 14px; border: 1.5px solid #e2e8f0; border-radius: 8px; font-size: 14px; width: 100%; outline: none; }
.member-list { display: flex; flex-direction: column; gap: 8px; }
.member-item { display: flex; align-items: center; gap: 12px; padding: 8px 0; }
.member-avatar { width: 36px; height: 36px; border-radius: 50%; background: #eef2ff; color: #6366f1; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 600; }
.member-info { display: flex; flex-direction: column; }
.member-name { font-size: 14px; font-weight: 500; color: #1e293b; }
.member-role { font-size: 12px; color: #94a3b8; }
.asg-list, .sub-list { display: flex; flex-direction: column; gap: 8px; }
.asg-item, .sub-item { display: flex; justify-content: space-between; align-items: center; padding: 12px; border-radius: 8px; background: #f8fafc; }
.asg-main { display: flex; gap: 12px; align-items: center; }
.tag { padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 500; background: #eef2ff; color: #6366f1; }
.tag.completed { background: #ecfdf5; color: #10b981; }
.tag.grading { background: #fffbeb; color: #f59e0b; }
.meta { font-size: 12px; color: #94a3b8; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: #fff; border-radius: 16px; padding: 32px; width: 400px; max-width: 90vw; }
.modal h3 { margin: 0 0 16px; }
.modal-actions { display: flex; gap: 12px; margin-top: 20px; justify-content: flex-end; }
@media (max-width: 620px) { .page { padding: 18px 14px; } .page-header { gap: 16px; } .header-actions { flex-direction: column; align-items: stretch; } .asg-main { flex-wrap: wrap; } }
</style>
