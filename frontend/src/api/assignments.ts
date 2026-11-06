import apiClient from './client'

export interface QuestionInfo {
  id: number
  question_number: number
  content: string
  max_score: number
  knowledge_point_id: number | null
}

export interface AssignmentInfo {
  id: number
  title: string
  class_id: number
  class_name: string
  subject_id: number
  subject_name: string
  teacher_id: number
  due_date: string | null
  question_count: number
  created_at: string | null
  questions?: QuestionInfo[]
}

export const assignmentsApi = {
  list(classId?: number) {
    const params = classId ? { class_id: classId } : {}
    return apiClient.get<AssignmentInfo[]>('/assignments', { params })
  },
  get(id: number) {
    return apiClient.get<AssignmentInfo>(`/assignments/${id}`)
  },
  create(data: {
    title: string
    class_id: number
    subject_id: number
    due_date?: string
    questions: Array<{ question_number: number; content: string; max_score: number }>
  }) {
    return apiClient.post<{ id: number; title: string; message: string }>('/assignments', data)
  },
}
