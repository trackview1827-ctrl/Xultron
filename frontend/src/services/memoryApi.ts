import { apiRequest } from './apiClient'
import type { MemoryCategory, MemoryItem } from '../types'

export const memoryApi = {
  list: (query = '', category?: MemoryCategory, signal?: AbortSignal) => apiRequest<{ memories: MemoryItem[] }>(`/memory?query=${encodeURIComponent(query)}${category ? `&category=${category}` : ''}`, { signal }),
  create: (input: Pick<MemoryItem, 'title' | 'content' | 'category'>) => apiRequest<{ memory: MemoryItem }>('/memory', { method: 'POST', body: JSON.stringify(input) }),
  get: (id: string) => apiRequest<{ memory: MemoryItem }>(`/memory/${encodeURIComponent(id)}`),
  update: (id: string, input: Pick<MemoryItem, 'title' | 'content' | 'category'>) => apiRequest<{ memory: MemoryItem }>(`/memory/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(input) }),
  remove: (id: string) => apiRequest<void>(`/memory/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  clear: () => apiRequest<void>('/memory', { method: 'DELETE', body: JSON.stringify({ confirm: 'CLEAR' }) }),
}
