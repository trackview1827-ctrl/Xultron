import { describe, expect, it, vi } from 'vitest'
import { apiRequest, apiStream, setCsrfToken } from './apiClient'
import { sanitizeProviderInput } from './providersApi'
import type { ProviderInput } from '../types'

const base: ProviderInput = { name: 'Private link', kind: 'ai', adapter: 'openai_compatible', baseUrl: 'https://example.test/v1', apiKey: '', model: 'x-1', enabled: true, isDefault: true, streaming: true, config: {} }
describe('API and secret handling', () => {
  it('omits blank credentials when editing a provider', () => { expect(sanitizeProviderInput(base)).not.toHaveProperty('apiKey') })
  it('keeps a newly submitted secret only in the one request object', () => { const clean = sanitizeProviderInput({ ...base, apiKey: 'secret-one-time-value' }); expect(clean.apiKey).toBe('secret-one-time-value'); expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0) })
  it('uses HttpOnly session credentials and CSRF without URL leakage', async () => {
    const fetcher = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }))
    setCsrfToken('csrf-test'); await apiRequest('/settings', { method: 'PATCH', body: JSON.stringify({ lowDataMode: true }) })
    const [url, init] = fetcher.mock.calls[0]!; expect(url).toBe('/api/v1/settings'); expect(String(url)).not.toContain('csrf-test'); expect(init?.credentials).toBe('same-origin'); expect(new Headers(init?.headers).get('X-CSRF-Token')).toBe('csrf-test')
  })
  it('shows only safe API error messages', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ error: { code: 'provider_authentication_failed', message: 'Authentication rejected.', retryable: false, requestId: 'req_1' } }), { status: 401 }))
    await expect(apiRequest('/providers/1/test')).rejects.toMatchObject({ message: 'Authentication rejected.', code: 'provider_authentication_failed', status: 401 })
  })
  it('parses progressive SSE events through the fetch stream boundary', async () => {
    const encoder = new TextEncoder(); const chunks = ['event: state\ndata: {"state":"thinking"}\n\n', 'event: delta\ndata: {"delta":"Hello"}\n\n', 'event: done\ndata: {"message":{"content":"Hello"}}\n\n']
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(new ReadableStream({ start(controller) { chunks.forEach(chunk => controller.enqueue(encoder.encode(chunk))); controller.close() } }), { status: 200, headers: { 'Content-Type': 'text/event-stream' } }))
    const events: string[] = []; await apiStream('/chat/stream', { message: 'Hi' }, event => events.push(event)); expect(events).toEqual(['state', 'delta', 'done'])
  })
  it('rejects an SSE response that ends without a terminal event', async () => {
    const encoder = new TextEncoder()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(new ReadableStream({ start(controller) { controller.enqueue(encoder.encode('event: delta\ndata: {"delta":"Partial"}\n\n')); controller.close() } }), { status: 200 }))
    await expect(apiStream('/chat/stream', { message: 'Hi' }, () => undefined)).rejects.toMatchObject({ code: 'stream_interrupted', retryable: true })
  })
  it('does not redeliver an event when the consumer callback throws', async () => {
    const encoder = new TextEncoder(); const callback = vi.fn(() => { throw new Error('consumer failed') })
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(new ReadableStream({ start(controller) { controller.enqueue(encoder.encode('event: done\ndata: {"message":{"content":"Hello"}}\n\n')); controller.close() } }), { status: 200 }))
    await expect(apiStream('/chat/stream', { message: 'Hi' }, callback)).rejects.toThrow('consumer failed')
    expect(callback).toHaveBeenCalledTimes(1)
  })
})
