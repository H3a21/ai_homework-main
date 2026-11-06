import apiClient from './client'

export interface ReportCacheMeta {
  hit: boolean
}

export interface ReportOverview {
  knowledge_point_count: number
  average_mastery: number
  weak_point_count: number
  total_attempts: number
  average_score_ratio: number
}

export interface KnowledgeRadarPoint {
  knowledge_point_id: number
  knowledge_point_name: string
  subject_id: number
  subject_name: string
  mastery_level: number
  ability_theta: number
  attempt_count: number
  average_score_ratio: number
  is_weak: boolean
}

export interface SubjectSummary {
  subject_id: number
  subject_name: string
  knowledge_point_count: number
  average_mastery: number
  weak_point_count: number
  total_attempts: number
}

export interface StudentLearningReport {
  report_type: 'student'
  student_id: number
  student_name: string
  subject_id: number | null
  generated_at: string
  overview: ReportOverview
  subject_summaries: SubjectSummary[]
  radar: KnowledgeRadarPoint[]
  weak_points: KnowledgeRadarPoint[]
  strengths: KnowledgeRadarPoint[]
  cache: ReportCacheMeta
}

export interface ClassKnowledgePoint {
  knowledge_point_id: number
  knowledge_point_name: string
  subject_id: number
  subject_name: string
  average_mastery: number
  covered_student_count: number
  weak_student_count: number
  weak_rate: number
  total_attempts: number
}

export interface ClassStudentSummary extends ReportOverview {
  student_id: number
  student_name: string
}

export interface ClassLearningReport {
  report_type: 'class'
  class_id: number
  class_name: string
  subject_id: number | null
  generated_at: string
  overview: ReportOverview & {
    student_count: number
    students_with_data: number
  }
  knowledge_points: ClassKnowledgePoint[]
  weak_knowledge_points: ClassKnowledgePoint[]
  student_summaries: ClassStudentSummary[]
  cache: ReportCacheMeta
}

export const reportsApi = {
  getStudent(studentId: number, subjectId?: number) {
    return apiClient.get<StudentLearningReport>(`/reports/students/${studentId}`, {
      params: { subject_id: subjectId },
    })
  },
  getClass(classId: number, subjectId?: number) {
    return apiClient.get<ClassLearningReport>(`/reports/classes/${classId}`, {
      params: { subject_id: subjectId },
    })
  },
}
