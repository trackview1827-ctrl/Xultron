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
    chat.stream.mockReset().mockResolvedValue(undefined)
    tasks.upload.mockReset().mockResolvedValue({ attachment: { id: 'attachment-note', name: 'note.txt', contentType: 'text/plain', size: 4, sha256: 'hash-note' } })
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

  it('offers distinct photo, video, and file choices and renders the selected preview above the composer', async () => {
    const user = userEvent.setup(); const { container } = render(<HomePage />)
    await user.click(await screen.findByRole('button', { name: 'Add attachment' }))
    const menu = screen.getByRole('group', { name: 'Attachment options' })
    expect(menu.querySelectorAll('button')).toHaveLength(3)
    expect(menu).toHaveTextContent('Photo')
    expect(menu).toHaveTextContent('Video')
    expect(menu).toHaveTextContent('File')
    expect(menu).not.toHaveTextContent(/MB/)

    const inputs = container.querySelectorAll<HTMLInputElement>('input[type="file"]')
    expect(inputs).toHaveLength(3)
    expect(inputs[0]).toHaveAttribute('accept', 'image/png,image/jpeg,image/gif')
    expect(inputs[1]).toHaveAttribute('accept', 'video/mp4,video/webm,video/quicktime')
    fireEvent.change(inputs[2]!, { target: { files: [new File(['note'], 'note.txt', { type: 'text/plain' })] } })
    await waitFor(() => expect(tasks.upload).toHaveBeenCalledWith(expect.any(File)))
    expect(await screen.findByRole('status')).toHaveTextContent('note.txt is ready')
    const preview = screen.getByRole('region', { name: 'Selected attachment: note.txt' })
    expect(preview).toHaveTextContent('FILE')
    expect(preview.parentElement?.firstElementChild).toBe(preview)
    expect(container.querySelector('.attachment-status')).toBeNull()
  })

  it('sends a ready attachment with its API ID and renders its card above the deliberate default prompt', async () => {
    const user = userEvent.setup(); const { container } = render(<HomePage />)
    const inputs = container.querySelectorAll<HTMLInputElement>('input[type="file"]')
    fireEvent.change(inputs[2]!, { target: { files: [new File(['note'], 'note.txt', { type: 'text/plain' })] } })
    await screen.findByRole('status')
    await user.click(screen.getByRole('button', { name: 'Send message' }))
    await waitFor(() => expect(chat.stream).toHaveBeenCalledWith(expect.objectContaining({ message: 'Please review the attached file.', attachmentIds: ['attachment-note'] }), expect.anything(), expect.anything()))
    const sentCard = screen.getByRole('region', { name: 'Attached document: note.txt' })
    expect(sentCard).toBeInTheDocument()
    expect(sentCard.compareDocumentPosition(screen.getByText('Please review the attached file.')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.queryByRole('region', { name: 'Selected attachment: note.txt' })).not.toBeInTheDocument()
  })

  it('removes a checking attachment without restoring it when its upload resolves later', async () => {
    const pending = deferred<{ attachment: { id: string; name: string; contentType: string; size: number; sha256: string } }>()
    tasks.upload.mockReturnValueOnce(pending.promise)
    const user = userEvent.setup(); const { container } = render(<HomePage />)
    const inputs = container.querySelectorAll<HTMLInputElement>('input[type="file"]')
    fireEvent.change(inputs[0]!, { target: { files: [new File(['photo'], 'photo.png', { type: 'image/png' })] } })
    expect(await screen.findByRole('region', { name: 'Selected attachment: photo.png' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Remove photo.png' }))
    expect(screen.queryByRole('region', { name: 'Selected attachment: photo.png' })).not.toBeInTheDocument()
    pending.resolve({ attachment: { id: 'attachment-photo', name: 'photo.png', contentType: 'image/png', size: 5, sha256: 'hash-photo' } })
    await Promise.resolve()
    expect(screen.queryByRole('region', { name: 'Selected attachment: photo.png' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add attachment' })).toBeEnabled()
  })

  it('revokes a selected media object URL when the attachment is removed', async () => {
    const createObjectUrl = vi.fn(() => 'blob:photo-preview')
    const revokeObjectUrl = vi.fn()
    const createDescriptor = Object.getOwnPropertyDescriptor(URL, 'createObjectURL')
    const revokeDescriptor = Object.getOwnPropertyDescriptor(URL, 'revokeObjectURL')
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createObjectUrl })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeObjectUrl })
    tasks.upload.mockResolvedValueOnce({ attachment: { id: 'attachment-photo', name: 'photo.png', contentType: 'image/png', size: 5, sha256: 'hash-photo' } })
    try {
      const user = userEvent.setup(); const { container, unmount } = render(<HomePage />)
      const inputs = container.querySelectorAll<HTMLInputElement>('input[type="file"]')
      fireEvent.change(inputs[0]!, { target: { files: [new File(['photo'], 'photo.png', { type: 'image/png' })] } })
      await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('photo.png is ready'))
      await user.click(screen.getByRole('button', { name: 'Remove photo.png' }))
      expect(revokeObjectUrl).toHaveBeenCalledWith('blob:photo-preview')
      unmount()
    } finally {
      if (createDescriptor) Object.defineProperty(URL, 'createObjectURL', createDescriptor)
      else delete (URL as { createObjectURL?: unknown }).createObjectURL
      if (revokeDescriptor) Object.defineProperty(URL, 'revokeObjectURL', revokeDescriptor)
      else delete (URL as { revokeObjectURL?: unknown }).revokeObjectURL
    }
  })

  it('returns focus to the attachment trigger when the attachment menu closes with Escape', async () => {
    const user = userEvent.setup(); render(<HomePage />)
    const trigger = await screen.findByRole('button', { name: 'Add attachment' })
    await user.click(trigger)
    const media = screen.getByRole('button', { name: 'Photo' })
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
