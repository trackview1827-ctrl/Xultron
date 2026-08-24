import { apiRequest, setCsrfToken } from './apiClient'
import type { IdentityResponse, LogoutResponse, SessionDevice, SessionResponse } from '../types'

export const authApi = {
  async session(): Promise<SessionResponse> { const data = await apiRequest<SessionResponse>('/auth/session'); setCsrfToken(data.csrfToken); return data },
  async guest(): Promise<IdentityResponse> { const data = await apiRequest<IdentityResponse>('/auth/guest', { method: 'POST', body: '{}' }); setCsrfToken(data.csrfToken); return data },
  async register(input: { username: string; email: string; password: string }): Promise<IdentityResponse> { const data = await apiRequest<IdentityResponse>('/auth/register', { method: 'POST', body: JSON.stringify(input) }); setCsrfToken(data.csrfToken); return data },
  async login(input: { identifier: string; password: string }): Promise<IdentityResponse> { const data = await apiRequest<IdentityResponse>('/auth/login', { method: 'POST', body: JSON.stringify(input) }); setCsrfToken(data.csrfToken); return data },
  async logout(): Promise<LogoutResponse> { const data = await apiRequest<LogoutResponse>('/auth/logout', { method: 'POST', body: '{}' }); setCsrfToken(data.csrfToken); return data },
  sessions: () => apiRequest<{ sessions: SessionDevice[] }>('/auth/sessions'),
  revokeSession: (id: string) => apiRequest<void>(`/auth/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' }),
}
