import apiClient from './client'

export interface StudentInfo {
  id: number
  username: string
  display_name: string
}

export const studentsApi = {
  list() {
    return apiClient.get<StudentInfo[]>('/students')
  },
}
