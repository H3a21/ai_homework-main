import apiClient from './client'

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  password: string
  display_name: string
  role: 'teacher' | 'student'
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface UserResponse {
  id: number
  username: string
  display_name: string
  role: string
}

export const authApi = {
  login(data: LoginRequest) {
    return apiClient.post<TokenResponse>('/auth/login', data)
  },
  register(data: RegisterRequest) {
    return apiClient.post<TokenResponse>('/auth/register', data)
  },
  refresh(refreshToken: string) {
    return apiClient.post<TokenResponse>('/auth/refresh', { refresh_token: refreshToken })
  },
  getMe() {
    return apiClient.get<UserResponse>('/auth/me')
  },
}
