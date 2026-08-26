import { apiRequest } from './apiClient'
import type { AgentTask, Attachment, ToolDescription } from '../types'

export const tasksApi = {
  list: () => apiRequest<{ tasks: AgentTask[] }>('/tasks'),
  get: (id: string) => apiRequest<{ task: AgentTask }>(`/tasks/${encodeURIComponent(id)}`),
  create: (title: string, instruction: string) => apiRequest<{ task: AgentTask }>('/tasks', { method: 'POST', body: JSON.stringify({ title, instruction }) }),
  plan: (id: string) => apiRequest<{ task: AgentTask }>(`/tasks/${encodeURIComponent(id)}/plan`, { method: 'POST', body: '{}' }),
  approvePlan: (id: string) => apiRequest<{ task: AgentTask }>(`/tasks/${encodeURIComponent(id)}/plan/approve`, { method: 'POST', body: '{}' }),
  claim: (id: string, workerId: string) => apiRequest<{ task: AgentTask }>(`/tasks/${encodeURIComponent(id)}/claim`, { method: 'POST', body: JSON.stringify({ workerId }) }),
  cancel: (id: string) => apiRequest<{ task: AgentTask }>(`/tasks/${encodeURIComponent(id)}/cancel`, { method: 'POST', body: '{}' }),
  tools: () => apiRequest<{ tools: ToolDescription[] }>('/tools'),
  upload: (file: File) => { const form = new FormData(); form.append('file', file); return apiRequest<{ attachment: Attachment }>('/attachments', { method: 'POST', body: form }) },
}
