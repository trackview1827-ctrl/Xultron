import type { DataUsage } from '../types'

const API_ROOT = '/api/v1'
let csrfToken = ''
let usage: DataUsage = { downloaded: 0, uploaded: 0 }
const subscribers = new Set<(next: DataUsage) => void>()

export class ApiError extends Error {
  readonly code: string
  readonly retryable: boolean
  readonly status: number
  readonly requestId?: string
  constructor(message: string, status = 0, code = 'network_error', retryable = true, requestId?: string) {
    super(message); this.name = 'ApiError'; this.status = status; this.code = code; this.retryable = retryable; this.requestId = requestId
  }
}

export function setCsrfToken(token: string): void { csrfToken = token }
export function getDataUsage(): DataUsage { return { ...usage } }
export function subscribeDataUsage(listener: (next: DataUsage) => void): () => void { subscribers.add(listener); return () => subscribers.delete(listener) }
export function resetDataUsage(): void { usage = { downloaded: 0, uploaded: 0 }; subscribers.forEach(fn => fn(getDataUsage())) }
function count(direction: keyof DataUsage, value: string | Blob): void {
  const bytes = typeof value === 'string' ? new Blob([value]).size : value.size
  usage = { ...usage, [direction]: usage[direction] + bytes }; subscribers.forEach(fn => fn(getDataUsage()))
}
function countFormData(form: FormData): void {
  for (const value of form.values()) count('uploaded', value)
}

async function safeError(response: Response): Promise<ApiError> {
  try {
    const body = await response.json() as { error?: { code?: string; message?: string; retryable?: boolean; requestId?: string } }
    return new ApiError(body.error?.message ?? 'Xultron could not complete the request.', response.status, body.error?.code ?? 'request_failed', body.error?.retryable ?? response.status >= 500, body.error?.requestId)
  } catch { return new ApiError('Xultron received an invalid server response.', response.status, 'invalid_response', response.status >= 500) }
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const hasForm = init.body instanceof FormData
  if (init.body && !hasForm) headers.set('Content-Type', 'application/json')
  if (csrfToken && init.method && init.method !== 'GET') headers.set('X-CSRF-Token', csrfToken)
  if (typeof init.body === 'string') count('uploaded', init.body)
  else if (init.body instanceof Blob) count('uploaded', init.body)
  else if (init.body instanceof FormData) countFormData(init.body)
  let response: Response
  try { response = await fetch(`${API_ROOT}${path}`, { ...init, headers, credentials: 'same-origin' }) }
  catch (error) { if (error instanceof DOMException && error.name === 'AbortError') throw error; throw new ApiError('The Xultron link is unavailable. Check your connection.', 0, 'network_error', true) }
  const text = await response.text(); count('downloaded', text)
  if (!response.ok) {
    const reconstructed = new Response(text, { status: response.status, headers: response.headers })
    throw await safeError(reconstructed)
  }
  if (!text) return undefined as T
  try { return JSON.parse(text) as T } catch { throw new ApiError('Xultron received unreadable data.', response.status, 'invalid_response', false) }
}

export async function apiBlob(path: string, body: unknown, signal?: AbortSignal): Promise<Blob> {
  const payload = JSON.stringify(body); count('uploaded', payload)
  const headers = new Headers({ 'Content-Type': 'application/json' }); if (csrfToken) headers.set('X-CSRF-Token', csrfToken)
  let response: Response
  try { response = await fetch(`${API_ROOT}${path}`, { method: 'POST', body: payload, headers, credentials: 'same-origin', signal }) }
  catch (error) { if (error instanceof DOMException && error.name === 'AbortError') throw error; throw new ApiError('Speech service is unreachable.', 0, 'network_error', true) }
  if (!response.ok) throw await safeError(response)
  const blob = await response.blob(); count('downloaded', blob); return blob
}

export async function apiStream(path: string, body: unknown, onEvent: (event: string, data: unknown) => void, signal?: AbortSignal): Promise<void> {
  const payload = JSON.stringify(body); count('uploaded', payload)
  const headers = new Headers({ Accept: 'text/event-stream', 'Content-Type': 'application/json' }); if (csrfToken) headers.set('X-CSRF-Token', csrfToken)
  let response: Response
  try { response = await fetch(`${API_ROOT}${path}`, { method: 'POST', body: payload, headers, credentials: 'same-origin', signal }) }
  catch (error) { if (error instanceof DOMException && error.name === 'AbortError') throw error; throw new ApiError('Streaming link interrupted. Your message is safe to retry.', 0, 'network_error', true) }
  if (!response.ok) throw await safeError(response)
  if (!response.body) throw new ApiError('Streaming is not supported by this browser.', 0, 'stream_unavailable', false)
  const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''; let terminal = false
  const processBlock = (block: string) => {
    let event = 'message'; const data: string[] = []
    for (const line of block.split(/\r?\n/)) { if (line.startsWith('event:')) event = line.slice(6).trim(); if (line.startsWith('data:')) data.push(line.slice(5).trim()) }
    const serialized = data.join('\n'); if (!serialized) return
    let parsed: unknown
    try { parsed = JSON.parse(serialized) as unknown } catch { parsed = serialized }
    if (event === 'done' || event === 'error') terminal = true
    onEvent(event, parsed)
  }
  while (true) {
    const { value, done } = await reader.read(); if (done) break
    const chunk = decoder.decode(value, { stream: true }); count('downloaded', chunk); buffer += chunk
    const blocks = buffer.split(/\r?\n\r?\n/); buffer = blocks.pop() ?? ''
    for (const block of blocks) processBlock(block)
  }
  buffer += decoder.decode()
  if (buffer.trim()) processBlock(buffer)
  if (!terminal) throw new ApiError('Streaming ended before Xultron completed the response. Your message is safe to retry.', 0, 'stream_interrupted', true)
}
