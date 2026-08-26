import { apiRequest } from './apiClient'
import type { ModelOption, Provider, ProviderInput, ProviderKind, ProviderTest } from '../types'

export function sanitizeProviderInput(input: ProviderInput): ProviderInput {
  const clean = { ...input, config: { ...input.config } }
  if (!clean.apiKey?.trim()) delete clean.apiKey
  return clean
}

export const providersApi = {
  list: (kind?: ProviderKind) => apiRequest<{ providers: Provider[] }>(`/providers${kind ? `?kind=${kind}` : ''}`),
  get: (id: string) => apiRequest<{ provider: Provider }>(`/providers/${encodeURIComponent(id)}`),
  create: (input: ProviderInput) => apiRequest<{ provider: Provider }>('/providers', { method: 'POST', body: JSON.stringify(sanitizeProviderInput(input)) }),
  update: (id: string, input: ProviderInput) => apiRequest<{ provider: Provider }>(`/providers/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(sanitizeProviderInput(input)) }),
  remove: (id: string) => apiRequest<void>(`/providers/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  test: (id: string) => apiRequest<ProviderTest>(`/providers/${encodeURIComponent(id)}/test`, { method: 'POST', body: '{}' }),
  models: (id: string) => apiRequest<{ models: ModelOption[] }>(`/providers/${encodeURIComponent(id)}/models`, { method: 'POST', body: '{}' }),
  startOpenAIOAuth: (id: string) => apiRequest<{ authorizationUrl: string; redirectUri: string }>(`/providers/${encodeURIComponent(id)}/oauth/openai/start`, { method: 'POST', body: '{}' }),
  oauthStatus: (id: string) => apiRequest<{ supported: boolean; connected: boolean; authMethod: string | null; accountId: string | null; expiresAt: number | null }>(`/providers/${encodeURIComponent(id)}/oauth/status`),
  disconnectOAuth: (id: string) => apiRequest<{ ok: boolean }>(`/providers/${encodeURIComponent(id)}/oauth`, { method: 'DELETE' }),
}
