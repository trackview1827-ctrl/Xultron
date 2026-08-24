import { apiRequest, setCsrfToken } from './apiClient'
import type { SessionDevice, SessionResponse, User } from '../types'

export const authApi = {
  async session(): Promise<SessionResponse> { const data = await apiRequest<SessionResponse>('/auth/session'); setCsrfToken(data.csrfToken); return data },
  async guest(): Promise<SessionResponse> { const data = await apiRequest<SessionResponse>('/auth/guest', { method: 'POST', body: '{}' }); setCsrfToken(data.csrfToken); return data },
  register: (input: { username: string; email: string; password: string }) => apiRequest<{ user: User }>('/auth/register', { method: 'POST', body: JSON.stringify(input) }),
  login: (input: { identifier: string; password: string }) => apiRequest<{ user: User }>('/auth/login', { method: 'POST', body: JSON.stringify(input) }),
  logout: () => apiRequest<void>('/auth/logout', { method: 'POST', body: '{}' }),
  sessions: () => apiRequest<{ sessions: SessionDevice[] }>('/auth/sessions'),
  revokeSession: (id: string) => apiRequest<void>(`/auth/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' }),
}
