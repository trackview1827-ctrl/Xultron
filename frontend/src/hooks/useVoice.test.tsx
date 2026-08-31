import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DEFAULT_SETTINGS } from '../services/settingsApi'
import { useVoice } from './useVoice'

const app = vi.hoisted(() => ({ dispatchCore: vi.fn(), value: {} as Record<string, unknown> }))
const api = vi.hoisted(() => ({ transcribe: vi.fn(), synthesize: vi.fn() }))
vi.mock('../stores/AppContext', () => ({ useApp: () => app.value }))
vi.mock('../services/voiceApi', () => ({ voiceApi: api }))

class FakeTrack extends EventTarget {
  stop = vi.fn()
  disconnect() { this.dispatchEvent(new Event('ended')) }
}
class FakeStream {
  track = new FakeTrack()
  getTracks() { return [this.track] }
}
class FakeRecorder {
  static instances: FakeRecorder[] = []
  static constructorArgumentCounts: number[] = []
  static constructorMimeTypes: (string | undefined)[] = []
  static isTypeSupported = vi.fn(() => false)
  state: RecordingState = 'inactive'
  mimeType = ''
  ondataavailable: ((event: BlobEvent) => void) | null = null
  onstop: (() => void) | null = null
  onerror: (() => void) | null = null
  constructor(_stream: MediaStream, options?: MediaRecorderOptions) { FakeRecorder.instances.push(this); FakeRecorder.constructorArgumentCounts.push(arguments.length); FakeRecorder.constructorMimeTypes.push(options?.mimeType) }
  start() { this.state = 'recording' }
  stop() { this.state = 'inactive'; const handler = this.onstop; queueMicrotask(() => handler?.()) }
  fail() { this.onerror?.() }
}
class FakeAudio {
  static instances: FakeAudio[] = []
  paused = true
  ended = false
  onended: (() => void) | null = null
  onerror: (() => void) | null = null
  onpause: (() => void) | null = null
  constructor(public src: string) { FakeAudio.instances.push(this) }
  play() { this.paused = false; return Promise.resolve() }
  pause() { this.paused = true; this.onpause?.() }
  removeAttribute(name: string) { if (name === 'src') this.src = '' }
  load() {}
  finish() { this.ended = true; this.paused = true; this.onended?.() }
}
class FakeAudioContext {
  static instances: FakeAudioContext[] = []
  state: AudioContextState = 'running'
  close = vi.fn(async () => { this.state = 'closed' })
  createMediaStreamSource() { return { connect: vi.fn() } }
  createAnalyser() { return { fftSize: 0, frequencyBinCount: 4, getByteFrequencyData: vi.fn() } }
  constructor() { FakeAudioContext.instances.push(this) }
}

function setApp(coreState = 'ONLINE', settings = { ...DEFAULT_SETTINGS, reducedMotion: true }) {
  app.value = { coreState, dispatchCore: app.dispatchCore, settings, online: true, networkOnline: true }
}

describe('useVoice media lifecycle', () => {
  beforeEach(() => {
    app.dispatchCore.mockReset(); api.transcribe.mockReset(); api.synthesize.mockReset(); FakeRecorder.instances = []; FakeRecorder.constructorArgumentCounts = []; FakeRecorder.constructorMimeTypes = []; FakeRecorder.isTypeSupported.mockReset(); FakeRecorder.isTypeSupported.mockReturnValue(false); FakeAudio.instances = []; FakeAudioContext.instances = []
    setApp()
    Object.defineProperty(globalThis, 'MediaRecorder', { configurable: true, value: FakeRecorder })
    Object.defineProperty(globalThis, 'Audio', { configurable: true, value: FakeAudio })
    Object.defineProperty(globalThis, 'AudioContext', { configurable: true, value: FakeAudioContext })
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn((_: Blob) => `blob:test-${FakeAudio.instances.length + 1}`) })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
    Object.defineProperty(globalThis, 'requestAnimationFrame', { configurable: true, value: vi.fn(() => 1) })
    Object.defineProperty(globalThis, 'cancelAnimationFrame', { configurable: true, value: vi.fn() })
  })

  it('recovers from denied permission, retries from ERROR, and handles device disconnect', async () => {
    const stream = new FakeStream(); const getUserMedia = vi.fn().mockRejectedValueOnce(new DOMException('Denied', 'NotAllowedError')).mockResolvedValueOnce(stream)
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia } })
    const { result, rerender } = renderHook(() => useVoice(vi.fn()))

    await act(async () => result.current.start())
    expect(result.current.error).toMatch(/denied/i)
    expect(app.dispatchCore).toHaveBeenCalledWith({ type: 'FAIL' })

    setApp('ERROR'); rerender()
    await act(async () => result.current.start())
    expect(result.current.recording).toBe(true)
    expect(FakeRecorder.constructorArgumentCounts.at(-1)).toBe(1)
    expect(app.dispatchCore).toHaveBeenCalledWith({ type: 'RECOVER' })
    expect(app.dispatchCore).toHaveBeenCalledWith({ type: 'LISTEN' })

    act(() => stream.track.disconnect())
    await waitFor(() => expect(result.current.error).toMatch(/microphone disconnected/i))
    expect(FakeRecorder.instances[0]?.state).toBe('inactive')
    expect(stream.track.stop).toHaveBeenCalled()
    expect(app.dispatchCore).toHaveBeenLastCalledWith({ type: 'FAIL' })
  })

  it('falls back to a simple audio constraint for Android WebView', async () => {
    const stream = new FakeStream()
    const getUserMedia = vi.fn()
      .mockRejectedValueOnce(new DOMException('Constraint rejected', 'OverconstrainedError'))
      .mockResolvedValueOnce(stream)
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia } })
    const { result } = renderHook(() => useVoice(vi.fn()))

    await act(async () => result.current.start())

    expect(getUserMedia).toHaveBeenNthCalledWith(1, { audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 } })
    expect(getUserMedia).toHaveBeenNthCalledWith(2, { audio: true })
    expect(result.current.recording).toBe(true)
  })

  it('retries without audio processing when Android WebView cannot start the communication source', async () => {
    const stream = new FakeStream()
    const getUserMedia = vi.fn()
      .mockRejectedValueOnce(new DOMException('Could not start audio source', 'NotReadableError'))
      .mockResolvedValueOnce(stream)
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia } })
    const { result } = renderHook(() => useVoice(vi.fn()))

    await act(async () => result.current.start())

    expect(getUserMedia).toHaveBeenNthCalledWith(1, { audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 } })
    expect(getUserMedia).toHaveBeenNthCalledWith(2, { audio: true })
    expect(result.current.error).toBe('')
    expect(result.current.recording).toBe(true)
  })

  it('coalesces repeated taps while Android is opening the microphone', async () => {
    const stream = new FakeStream()
    let resolveMicrophone!: (stream: FakeStream) => void
    const getUserMedia = vi.fn(() => new Promise<FakeStream>(resolve => { resolveMicrophone = resolve }))
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia } })
    const { result } = renderHook(() => useVoice(vi.fn()))

    let first!: Promise<boolean>
    let second!: Promise<boolean>
    act(() => {
      first = result.current.start()
      second = result.current.start()
    })

    expect(getUserMedia).toHaveBeenCalledTimes(1)
    await expect(second).resolves.toBe(true)
    await act(async () => { resolveMicrophone(stream); await first })
    expect(result.current.recording).toBe(true)
  })

  it('explains when Android WebView still cannot initialize the microphone after fallback', async () => {
    const getUserMedia = vi.fn().mockRejectedValue(new DOMException('Busy', 'NotReadableError'))
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia } })
    const { result } = renderHook(() => useVoice(vi.fn()))

    await act(async () => result.current.start())

    expect(getUserMedia).toHaveBeenCalledTimes(2)
    expect(result.current.error).toMatch(/WebView could not initialize/i)
    expect(app.dispatchCore).toHaveBeenLastCalledWith({ type: 'FAIL' })
  })

  it('skips a broken codec probe and selects the next supported Android recorder format', async () => {
    const stream = new FakeStream()
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: vi.fn().mockResolvedValue(stream) } })
    FakeRecorder.isTypeSupported.mockImplementationOnce(() => { throw new Error('probe failed') }).mockReturnValueOnce(true)
    const { result } = renderHook(() => useVoice(vi.fn()))

    await act(async () => result.current.start())

    expect(result.current.recording).toBe(true)
    expect(FakeRecorder.constructorMimeTypes.at(-1)).toBe('audio/webm')
  })

  it('handles MediaRecorder errors and closes visualizer resources on unmount', async () => {
    const stream = new FakeStream(); Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: vi.fn().mockResolvedValue(stream) } }); setApp('ONLINE', { ...DEFAULT_SETTINGS, reducedMotion: false, lowDataMode: false })
    const { result, unmount } = renderHook(() => useVoice(vi.fn()))
    await act(async () => result.current.start())
    expect(FakeAudioContext.instances).toHaveLength(1)
    act(() => FakeRecorder.instances[0]!.fail())
    await waitFor(() => expect(result.current.error).toMatch(/recording was interrupted/i))
    expect(stream.track.stop).toHaveBeenCalled()
    await waitFor(() => expect(FakeAudioContext.instances[0]!.close).toHaveBeenCalled())
    unmount()
  })

  it('keeps consecutive speech operations isolated and revokes every object URL', async () => {
    api.synthesize.mockResolvedValue(new Blob(['audio'], { type: 'audio/mpeg' }))
    const { result } = renderHook(() => useVoice(vi.fn()))
    let first!: Promise<void>; await act(async () => { first = result.current.speak('first'); await Promise.resolve(); await Promise.resolve() })
    await waitFor(() => expect(FakeAudio.instances).toHaveLength(1))
    let second!: Promise<void>; await act(async () => { second = result.current.speak('second'); await first })
    await waitFor(() => expect(FakeAudio.instances).toHaveLength(2))
    expect(result.current.speaking).toBe(true)
    expect(app.dispatchCore).toHaveBeenLastCalledWith({ type: 'SPEAK' })
    act(() => FakeAudio.instances[1]!.finish())
    await act(async () => second)
    expect(result.current.speaking).toBe(false)
    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2)
  })

  it('keeps recording and playback mutually exclusive', async () => {
    const firstStream = new FakeStream(); const secondStream = new FakeStream(); const getUserMedia = vi.fn().mockResolvedValueOnce(firstStream).mockResolvedValueOnce(secondStream)
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia } }); api.synthesize.mockResolvedValue(new Blob(['audio']))
    const { result } = renderHook(() => useVoice(vi.fn()))
    await act(async () => result.current.start())
    expect(result.current.recording).toBe(true)
    let speech!: Promise<void>; await act(async () => { speech = result.current.speak('reply'); await Promise.resolve() })
    await waitFor(() => expect(FakeAudio.instances).toHaveLength(1))
    expect(firstStream.track.stop).toHaveBeenCalled()
    expect(result.current.recording).toBe(false)

    await act(async () => result.current.start())
    expect(FakeAudio.instances[0]!.paused).toBe(true)
    expect(result.current.recording).toBe(true)
    expect(app.dispatchCore).toHaveBeenLastCalledWith({ type: 'LISTEN' })
    await act(async () => { result.current.stop(); await speech })
  })

  it('does not submit an empty non-speech transcript to chat', async () => {
    const stream = new FakeStream()
    const onTranscript = vi.fn()
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: vi.fn().mockResolvedValue(stream) } })
    api.transcribe.mockResolvedValue({ text: '', language: 'tr' })
    const { result } = renderHook(() => useVoice(onTranscript))

    await act(async () => result.current.start())
    const recorder = FakeRecorder.instances[0]!
    act(() => recorder.ondataavailable?.({ data: new Blob(['webm']) } as BlobEvent))
    await act(async () => { result.current.stop(); await Promise.resolve(); await Promise.resolve() })

    await waitFor(() => expect(api.transcribe).toHaveBeenCalled())
    expect(onTranscript).not.toHaveBeenCalled()
    expect(result.current.error).toMatch(/no speech was detected/i)
    expect(app.dispatchCore).toHaveBeenLastCalledWith({ type: 'COMPLETE' })
  })
})
