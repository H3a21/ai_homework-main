import apiClient from './client'

export interface ClassInfo {
  id: number
  name: string
  grade: string
  invite_code: string
  created_at: string | null
  members?: Array<{
    id: number
    username: string
    display_name: string
    role: string
    class_role: string
  }>
}

export const classesApi = {
  list() {
    return apiClient.get<ClassInfo[]>('/classes')
  },
  get(id: number) {
    return apiClient.get<ClassInfo>(`/classes/${id}`)
  },
  create(name: string, grade: string) {
    return apiClient.post<ClassInfo>('/classes', { name, grade })
  },
  addStudent(classId: number, studentId: number) {
    return apiClient.post(`/classes/${classId}/students`, { student_id: studentId })
  },
}
