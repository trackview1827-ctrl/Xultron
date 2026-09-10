import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DEFAULT_SETTINGS } from '../../services/settingsApi'
import { attachmentPreviewKind, HomePage, isCoreCompact } from './HomePage'

const app = vi.hoisted(() => ({ dispatchCore: vi.fn(), value: {} as Record<string, unknown> }))
const chat = vi.hoisted(() => ({ conversations: vi.fn(), messages: vi.fn(), stream: vi.fn() }))
const providers = vi.hoisted(() => ({ list: vi.fn() }))
const voice = vi.hoisted(() => ({ start: vi.fn(), stop: vi.fn(), speak: vi.fn(), stopSpeaking: vi.fn(), clearError: vi.fn(), onTranscript: undefined as ((text: string) => void) | undefined, recording: false, speaking: false, level: 0, error: '' }))
const tasks = vi.hoisted(() => ({ upload: vi.fn() }))
vi.mock('../../stores/AppContext', () => ({ useApp: () => app.value }))
vi.mock('../../services/chatApi', () => ({ chatApi: chat }))
vi.mock('../../services/providersApi', () => ({ providersApi: providers }))
vi.mock('../../services/tasksApi', () => ({ tasksApi: tasks }))
vi.mock('../../hooks/useVoice', () => ({ useVoice: (onTranscript: (text: string) => void) => { voice.onTranscript = onTranscript; return voice } }))

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
    tasks.upload.mockReset().mockResolvedValue({ attachment: { id: 'attachment-note', name: 'note.txt' } })
    voice.start.mockReset().mockResolvedValue(true)
    voice.stop.mockReset(); voice.speak.mockReset().mockResolvedValue(undefined); voice.stopSpeaking.mockReset(); voice.clearError.mockReset(); voice.onTranscript = undefined
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
  }, 10_000)

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

  it('runs a live voice turn, speaks the reply, and listens for the next turn', async () => {
    providers.list.mockResolvedValue({ providers: [
      { id: 'ai', name: 'AI', kind: 'ai', adapter: 'mock', baseUrl: null, model: null, temperature: null, maxTokens: null, streaming: true, enabled: true, isDefault: true, credential: { configured: false, masked: null }, config: {} },
      { id: 'stt', name: 'STT', kind: 'stt', adapter: 'mock', baseUrl: null, model: null, temperature: null, maxTokens: null, streaming: false, enabled: true, isDefault: true, credential: { configured: false, masked: null }, config: {} },
      { id: 'tts', name: 'TTS', kind: 'tts', adapter: 'mock', baseUrl: null, model: null, temperature: null, maxTokens: null, streaming: false, enabled: true, isDefault: true, credential: { configured: false, masked: null }, config: {} },
    ] })
    chat.stream.mockImplementation(async (_request, handlers) => {
      handlers.onDelta('Canlı yanıt')
      handlers.onDone({ id: 'live-answer', conversationId: '', role: 'assistant', content: 'Canlı yanıt', createdAt: '2026-08-29T00:00:00Z' })
    })
    const user = userEvent.setup(); render(<HomePage />)
    const start = await screen.findByRole('button', { name: 'Start live conversation' })
    await waitFor(() => expect(start).toBeEnabled())
    await user.click(start)
    expect(voice.start).toHaveBeenCalledTimes(1)

    voice.onTranscript?.('Nasılsın?')
    await waitFor(() => expect(chat.stream).toHaveBeenCalledWith(expect.objectContaining({ message: 'Nasılsın?' }), expect.anything(), expect.anything()))
    await waitFor(() => expect(voice.speak).toHaveBeenCalledWith('Canlı yanıt'))
    await waitFor(() => expect(voice.start).toHaveBeenCalledTimes(2))

    await user.click(screen.getByRole('button', { name: 'Stop live conversation' }))
    expect(voice.stop).toHaveBeenCalled()
    expect(voice.stopSpeaking).toHaveBeenCalled()
  })

  it('swaps the send position between live voice and send while compacting the reactor for composer focus', async () => {
    const user = userEvent.setup(); const { container } = render(<HomePage />)
    const input = await screen.findByLabelText('Message Xultron')
    expect(screen.getByRole('button', { name: 'Start live conversation' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Send message' })).not.toBeInTheDocument()

    await user.click(input)
    expect(container.querySelector('.core-stage')).toHaveClass('compact')
    await user.type(input, 'Hello')
    expect(screen.getByRole('button', { name: 'Send message' })).toBeEnabled()
    expect(screen.queryByRole('button', { name: 'Start live conversation' })).not.toBeInTheDocument()

    await user.clear(input)
    expect(screen.getByRole('button', { name: 'Start live conversation' })).toBeInTheDocument()
  })

  it('expands the reactor when Android dismisses a virtual keyboard while a draft remains focused', () => {
    expect(isCoreCompact(0, true, true, true)).toBe(true)
    expect(isCoreCompact(0, true, true, false)).toBe(false)
    expect(isCoreCompact(0, true, false, false)).toBe(true)
    expect(isCoreCompact(1, false, true, false)).toBe(true)
  })

  it('offers media, file, and camera choices and routes files through the safe attachment flow', async () => {
    const user = userEvent.setup(); const { container } = render(<HomePage />)
    await user.click(await screen.findByRole('button', { name: 'Add attachment' }))
    const menu = screen.getByRole('group', { name: 'Attachment options' })
    expect(menu.querySelectorAll('button')).toHaveLength(3)
    expect(menu).toHaveTextContent('Photo or video')
    expect(menu).toHaveTextContent('File')
    expect(menu).toHaveTextContent('Camera')
    expect(menu).toHaveTextContent('up to 6 MB')

    const inputs = container.querySelectorAll<HTMLInputElement>('input[type="file"]')
    expect(inputs).toHaveLength(2)
    expect(inputs[0]).toHaveAttribute('accept', 'image/*,video/*')
    fireEvent.change(inputs[1]!, { target: { files: [new File(['note'], 'note.txt', { type: 'text/plain' })] } })
    await waitFor(() => expect(tasks.upload).toHaveBeenCalledWith(expect.any(File)))
    expect(await screen.findByRole('status')).toHaveTextContent('note.txt is ready')
    const preview = screen.getByRole('region', { name: 'Selected attachment: note.txt' })
    expect(preview).toHaveTextContent('FILE')
    expect(preview.parentElement?.firstElementChild).toBe(preview)

    await user.click(screen.getByRole('button', { name: 'Camera' }))
    expect(screen.getByRole('status')).toHaveTextContent('Camera capture is not available')
    expect(screen.getByRole('button', { name: 'Add attachment' })).toHaveFocus()
  })

  it('returns focus to the attachment trigger when the attachment menu closes with Escape', async () => {
    const user = userEvent.setup(); render(<HomePage />)
    const trigger = await screen.findByRole('button', { name: 'Add attachment' })
    await user.click(trigger)
    const media = screen.getByRole('button', { name: 'Photo or video' })
    media.focus()
    await user.keyboard('{Escape}')
    expect(trigger).toHaveFocus()
    expect(screen.queryByRole('group', { name: 'Attachment options' })).not.toBeInTheDocument()

    await user.click(trigger)
    await user.keyboard('{Escape}')
    expect(trigger).toHaveFocus()
    expect(screen.queryByRole('group', { name: 'Attachment options' })).not.toBeInTheDocument()
  })

  it('classifies image, video, archive, and ordinary document attachment previews', () => {
    expect(attachmentPreviewKind(new File(['image'], 'scan.png', { type: 'image/png' }))).toBe('image')
    expect(attachmentPreviewKind(new File(['video'], 'walk.mp4', { type: 'video/mp4' }))).toBe('video')
    expect(attachmentPreviewKind(new File(['zip'], 'logs.zip', { type: 'application/zip' }))).toBe('archive')
    expect(attachmentPreviewKind(new File(['text'], 'notes.txt', { type: 'text/plain' }))).toBe('file')
  })
})
