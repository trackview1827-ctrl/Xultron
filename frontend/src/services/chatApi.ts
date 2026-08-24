import { apiRequest, apiStream } from './apiClient'
import type { Conversation, Message } from '../types'

export interface StreamHandlers { onState?: (state: string) => void; onConversation?: (conversation: Conversation) => void; onDelta: (text: string) => void; onDone?: (message?: Message) => void; onError?: (message: string) => void }

export const chatApi = {
  conversations: (limit = 20, cursor?: string) => apiRequest<{ conversations: Conversation[]; nextCursor?: string }>(`/chat/conversations?limit=${limit}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`),
  createConversation: (title?: string) => apiRequest<{ conversation: Conversation }>('/chat/conversations', { method: 'POST', body: JSON.stringify({ title }) }),
  conversation: (id: string) => apiRequest<{ conversation: Conversation }>(`/chat/conversations/${encodeURIComponent(id)}`),
  removeConversation: (id: string) => apiRequest<void>(`/chat/conversations/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  messages: (id: string, limit = 50, before?: string) => apiRequest<{ messages: Message[] }>(`/chat/conversations/${encodeURIComponent(id)}/messages?limit=${limit}${before ? `&before=${encodeURIComponent(before)}` : ''}`),
  async stream(input: { conversationId?: string; message: string; requestId: string }, handlers: StreamHandlers, signal?: AbortSignal): Promise<void> {
    await apiStream('/chat/stream', input, (event, raw) => {
      const data = raw as Record<string, unknown>
      if (event === 'state') handlers.onState?.(String(data.state ?? ''))
      else if (event === 'conversation') handlers.onConversation?.((data.conversation ?? data) as unknown as Conversation)
      else if (event === 'delta') handlers.onDelta(String(data.delta ?? data.text ?? ''))
      else if (event === 'done') handlers.onDone?.((data.message ?? data) as unknown as Message)
      else if (event === 'error') handlers.onError?.(String(data.message ?? 'The response stream was interrupted.'))
    }, signal)
  },
}
