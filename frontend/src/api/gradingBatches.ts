import apiClient from './client'

export type GradingBatchStatus = 'pending' | 'grading' | 'completed' | 'failed'
export type GradingBatchItemStatus = 'queued' | 'grading' | 'completed' | 'failed'

export interface GradingBatchItem {
  id: number
  submission_id: number
  task_id: string | null
  status: GradingBatchItemStatus
  error_message: string | null
  created_at: string | null
  started_at: string | null
  completed_at: string | null
}

export interface GradingBatch {
  id: number
  assignment_id: number
  teacher_id: number
  total_submissions: number
  completed_submissions: number
  failed_submissions: number
  finished_submissions: number
  queued_submissions?: number
  grading_submissions?: number
  progress_percent: number
  status: GradingBatchStatus
  error_message: string | null
  created_at: string | null
  completed_at: string | null
  items?: GradingBatchItem[]
}

export const gradingBatchesApi = {
  create(assignmentId: number) {
    return apiClient.post<GradingBatch>('/grading-batches', {
      assignment_id: assignmentId,
    })
  },
  list(params?: { assignment_id?: number; limit?: number }) {
    return apiClient.get<GradingBatch[]>('/grading-batches', { params })
  },
  get(batchId: number) {
    return apiClient.get<GradingBatch>(`/grading-batches/${batchId}`)
  },
}
