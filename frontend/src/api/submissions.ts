import type { AxiosProgressEvent } from 'axios'
import apiClient from './client'

export interface UploadedSubmissionImage {
  image_path: string
  filename: string
  content_type: string
  size: number
}

export interface SubmissionInfo {
  id: number
  assignment_id: number
  assignment_title: string
  student_id: number
  student_name: string
  status: string
  total_score: number | null
  comment: string | null
  submitted_at: string | null
  graded_at: string | null
  image_count: number
  graded_count: number
  images?: Array<{ id: number; image_path: string; page_number: number }>
  questions?: Array<{
    id: number
    question_number: number
    content: string
    max_score: number
    score: number | null
    feedback: string | null
  }>
}

export const submissionsApi = {
  list(params?: { assignment_id?: number; student_id?: number }) {
    return apiClient.get<SubmissionInfo[]>('/submissions', { params })
  },
  get(id: number) {
    return apiClient.get<SubmissionInfo>(`/submissions/${id}`)
  },
  uploadImage(image: File, onProgress?: (progress: number) => void) {
    const form = new FormData()
    form.append('image', image)
    return apiClient.post<UploadedSubmissionImage>('/submissions/images', form, {
      onUploadProgress(event: AxiosProgressEvent) {
        if (event.total && onProgress) {
          onProgress(Math.round((event.loaded / event.total) * 100))
        }
      },
    })
  },
  create(data: { assignment_id: number; image_paths: string[]; auto_grade?: boolean }) {
    return apiClient.post<{
      id: number
      assignment_id: number
      status: string
      task_id: string | null
      message: string
    }>('/submissions', data)
  },
  grade(id: number) {
    return apiClient.post<{
      message: string
      submission_id: number
      task_id: string
    }>(`/submissions/${id}/grade`)
  },
}
