import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DEFAULT_SETTINGS } from '../../services/settingsApi'
import { HomePage } from './HomePage'

const app = vi.hoisted(() => ({ dispatchCore: vi.fn(), value: {} as Record<string, unknown> }))
const chat = vi.hoisted(() => ({ conversations: vi.fn(), messages: vi.fn(), stream: vi.fn() }))
const providers = vi.hoisted(() => ({ list: vi.fn() }))
const voice = vi.hoisted(() => ({ start: vi.fn(), stop: vi.fn(), speak: vi.fn(), stopSpeaking: vi.fn(), clearError: vi.fn(), recording: false, speaking: false, level: 0, error: '' }))
vi.mock('../../stores/AppContext', () => ({ useApp: () => app.value }))
vi.mock('../../services/chatApi', () => ({ chatApi: chat }))
vi.mock('../../services/providersApi', () => ({ providersApi: providers }))
vi.mock('../../hooks/useVoice', () => ({ useVoice: () => voice }))

const conversationA = { id: 'a', title: 'Sequence A', createdAt: '2026-08-24T00:00:00Z', updatedAt: '2026-08-24T01:00:00Z' }
const conversationB = { id: 'b', title: 'Sequence B', createdAt: '2026-08-24T00:00:00Z', updatedAt: '2026-08-24T02:00:00Z' }
function message(id: string, conversationId: string, content: string) { return { id, conversationId, role: 'assistant' as const, content, createdAt: '2026-08-24T00:00:00Z' } }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(next => { resolve = next }); return { promise, resolve } }

describe('HomePage response and history lifecycle', () => {
  beforeEach(() => {
    app.dispatchCore.mockReset()
    app.value = { coreState: 'ONLINE', dispatchCore: app.dispatchCore, settings: { ...DEFAULT_SETTINGS }, online: true, networkOnline: true, setPage: vi.fn() }
    providers.list.mockResolvedValue({ providers: [{ id: 'p1', name: 'AI', kind: 'ai', adapter: 'local_http', baseUrl: null, model: null, temperature: null, maxTokens: null, streaming: true, enabled: true, isDefault: true, credential: { configured: false, masked: null }, config: {} }] })
    chat.conversations.mockResolvedValue({ conversations: [] })
    chat.messages.mockResolvedValue({ messages: [] })
    chat.stream.mockReset()
  })

  it('finalizes partial assistant output on explicit Stop without a Core error flash', async () => {
    chat.stream.mockImplementation(async (_input, handlers, signal: AbortSignal) => {
      handlers.onDelta('Partial output')
      await new Promise<void>((_resolve, reject) => signal.addEventListener('abort', () => reject(new DOMException('Stopped', 'AbortError')), { once: true }))
    })
    const user = userEvent.setup(); const { container } = render(<HomePage />)
    const input = await screen.findByLabelText('Message Xultron')
    await user.type(input, 'Hello')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Send message' })).toBeEnabled())
    await user.click(screen.getByRole('button', { name: 'Send message' }))
    expect(await screen.findByText(/Partial output/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Stop response' }))
    expect(await screen.findByText(/STOPPED/)).toBeInTheDocument()
    expect(container.querySelector('.cursor')).toBeNull()
    expect(app.dispatchCore).toHaveBeenCalledWith({ type: 'CANCEL' })
    expect(app.dispatchCore).not.toHaveBeenCalledWith({ type: 'FAIL' })
  })

  it('caps message input at the backend 8000-character limit and exposes the counter', async () => {
    render(<HomePage />)
    const input = await screen.findByLabelText<HTMLTextAreaElement>('Message Xultron')
    fireEvent.change(input, { target: { value: 'x'.repeat(8001) } })
    expect(input.value).toHaveLength(8000)
    expect(input).toHaveAttribute('maxlength', '8000')
    expect(screen.getByText('8000/8000')).toBeInTheDocument()
  })

  it('prevents a slower prior conversation selection from overwriting the latest one', async () => {
    const first = deferred<{ messages: ReturnType<typeof message>[] }>(); const second = deferred<{ messages: ReturnType<typeof message>[] }>()
    chat.conversations.mockResolvedValue({ conversations: [conversationA, conversationB] })
    chat.messages.mockImplementation((id: string) => id === 'a' ? first.promise : second.promise)
    const user = userEvent.setup(); render(<HomePage />)
    await user.click(await screen.findByRole('button', { name: 'Open conversation history' }))
    await user.click(await screen.findByRole('button', { name: /Sequence A/ }))
    await user.click(screen.getByRole('button', { name: /Open conversation history/ }))
    await user.click(screen.getByRole('button', { name: /Sequence B/ }))
    second.resolve({ messages: [message('mb', 'b', 'Latest B output')] })
    expect(await screen.findByText('Latest B output')).toBeInTheDocument()
    first.resolve({ messages: [message('ma', 'a', 'Stale A output')] })
    await Promise.resolve()
    expect(screen.queryByText('Stale A output')).not.toBeInTheDocument()
  })
})
