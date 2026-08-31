import { useCallback, useEffect, useRef, useState } from 'react'
import type { Dispatch } from 'react'
import { voiceApi } from '../services/voiceApi'
import { useApp } from '../stores/AppContext'
import type { CoreEvent } from '../features/core/coreMachine'

interface CaptureSession {
  id: number
  cancelled: boolean
}

interface PlaybackSession {
  id: number
  audio: HTMLAudioElement
  url: string
  abort: () => void
}

interface StartOptions {
  autoStopSilenceMs?: number
}

function abortError(message: string): DOMException {
  return new DOMException(message, 'AbortError')
}

async function openMicrophone(): Promise<MediaStream> {
  try {
    return await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 } })
  } catch (caught) {
    // Recent Android WebView builds can report NotReadableError when Chromium
    // cannot initialize its communication-audio processing path. Retrying with
    // an unconstrained source lets WebView use the device's normal recorder.
    if (caught instanceof DOMException && (
      caught.name === 'OverconstrainedError' ||
      caught.name === 'NotSupportedError' ||
      caught.name === 'NotReadableError' ||
      caught.name === 'AbortError'
    )) {
      return navigator.mediaDevices.getUserMedia({ audio: true })
    }
    throw caught
  }
}

function createAudioRecorder(stream: MediaStream): MediaRecorder {
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']
  for (const mimeType of candidates) {
    try {
      if (MediaRecorder.isTypeSupported(mimeType)) return new MediaRecorder(stream, { mimeType })
    } catch { /* Some Android WebView versions throw while probing codecs. */ }
  }
  return new MediaRecorder(stream)
}

function microphoneError(caught: unknown): string {
  if (!(caught instanceof DOMException)) return 'Xultron could not activate the microphone. Close other recording apps, then retry.'
  if (caught.name === 'NotAllowedError' || caught.name === 'SecurityError') return 'Microphone access was denied. Allow microphone access for Xultron in Android Settings, then retry.'
  if (caught.name === 'NotFoundError') return 'No microphone was found on this device.'
  if (caught.name === 'NotReadableError') return 'Android WebView could not initialize the microphone. Allow microphone access for Xultron, update Android System WebView, then reopen Xultron.'
  if (caught.name === 'AbortError') return 'Android interrupted the microphone request. Reopen Xultron and retry.'
  if (caught.name === 'OverconstrainedError') return 'This WebView rejected the requested microphone mode. Update Android System WebView, then retry.'
  if (caught.name === 'NotSupportedError') return 'This Android System WebView does not support microphone recording. Update it from Play Store.'
  return `Xultron could not activate the microphone (${caught.name}).`
}

export function useVoice(onTranscript: (text: string) => void, onNoSpeech?: () => void) {
  const { coreState, dispatchCore, settings, online, networkOnline } = useApp()
  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const openingRef = useRef(false)
  const captureRef = useRef<CaptureSession | null>(null)
  const analyserFrame = useRef<number | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const playbackRef = useRef<PlaybackSession | null>(null)
  const transcribeAbortRef = useRef<AbortController | null>(null)
  const synthAbortRef = useRef<AbortController | null>(null)
  const captureGenerationRef = useRef(0)
  const playbackGenerationRef = useRef(0)
  const mountedRef = useRef(true)
  const networkOnlineRef = useRef(networkOnline)
  const dispatchRef = useRef<Dispatch<CoreEvent>>(dispatchCore)
  const [recording, setRecording] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [level, setLevel] = useState(0)
  const [error, setError] = useState('')

  useEffect(() => { networkOnlineRef.current = networkOnline }, [networkOnline])
  useEffect(() => { dispatchRef.current = dispatchCore }, [dispatchCore])

  const releaseCapture = useCallback(async (updateState = true) => {
    streamRef.current?.getTracks().forEach(track => track.stop())
    streamRef.current = null
    if (analyserFrame.current !== null) cancelAnimationFrame(analyserFrame.current)
    analyserFrame.current = null
    const context = audioContextRef.current
    audioContextRef.current = null
    if (context && context.state !== 'closed') {
      try { await context.close() } catch { /* Browser audio shutdown is best effort. */ }
    }
    if (updateState && mountedRef.current) setLevel(0)
  }, [])

  const cancelCapture = useCallback((dispatchState: boolean) => {
    captureGenerationRef.current += 1
    transcribeAbortRef.current?.abort()
    transcribeAbortRef.current = null
    if (captureRef.current) captureRef.current.cancelled = true
    captureRef.current = null
    const recorder = recorderRef.current
    recorderRef.current = null
    if (recorder) {
      recorder.ondataavailable = null
      recorder.onstop = null
      if (recorder.state === 'recording') recorder.stop()
    }
    void releaseCapture()
    if (mountedRef.current) setRecording(false)
    if (dispatchState) dispatchRef.current({ type: networkOnlineRef.current ? 'CANCEL' : 'NETWORK_LOST' })
  }, [releaseCapture])

  const cancelPlayback = useCallback((dispatchState: boolean) => {
    playbackGenerationRef.current += 1
    synthAbortRef.current?.abort()
    synthAbortRef.current = null
    playbackRef.current?.abort()
    if (mountedRef.current) setSpeaking(false)
    if (dispatchState) dispatchRef.current({ type: networkOnlineRef.current ? 'CANCEL' : 'NETWORK_LOST' })
  }, [])

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      cancelCapture(false)
      cancelPlayback(false)
      dispatchRef.current({ type: networkOnlineRef.current ? 'CANCEL' : 'NETWORK_LOST' })
    }
  }, [cancelCapture, cancelPlayback])

  useEffect(() => {
    if (networkOnline) return
    cancelCapture(false)
    cancelPlayback(false)
    dispatchRef.current({ type: 'NETWORK_LOST' })
  }, [cancelCapture, cancelPlayback, networkOnline])

  const start = useCallback(async (options: StartOptions = {}): Promise<boolean> => {
    setError('')
    if (!online) {
      setError('Voice input needs a network connection.')
      if (!networkOnline) dispatchCore({ type: 'NETWORK_LOST' })
      return false
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setError('Microphone recording is not supported in this browser.')
      return false
    }
    if (recorderRef.current?.state === 'recording') return true
    if (openingRef.current) return true
    openingRef.current = true

    if (playbackRef.current || synthAbortRef.current) cancelPlayback(true)
    cancelCapture(false)
    const operationId = ++captureGenerationRef.current
    if (coreState === 'ERROR') dispatchCore({ type: 'RECOVER' })

    try {
      const stream = await openMicrophone()
      if (!mountedRef.current || operationId !== captureGenerationRef.current) {
        stream.getTracks().forEach(track => track.stop())
        return false
      }
      streamRef.current = stream

      const recorder = createAudioRecorder(stream)
      const capture: CaptureSession = { id: operationId, cancelled: false }
      const chunks: Blob[] = []
      recorderRef.current = recorder
      captureRef.current = capture

      const failCapture = (message: string) => {
        if (!mountedRef.current || operationId !== captureGenerationRef.current || captureRef.current !== capture) return
        setError(message)
        cancelCapture(false)
        dispatchRef.current({ type: 'FAIL' })
      }

      recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data) }
      recorder.onerror = () => failCapture('Microphone recording was interrupted. Retry when the input device is ready.')
      stream.getTracks().forEach(track => track.addEventListener('ended', () => failCapture('The microphone disconnected. Reconnect it, then retry.'), { once: true }))
      recorder.onstop = () => {
        void (async () => {
          if (recorderRef.current === recorder) recorderRef.current = null
          if (captureRef.current === capture) captureRef.current = null
          if (mountedRef.current && operationId === captureGenerationRef.current) setRecording(false)
          await releaseCapture()
          if (capture.cancelled || !mountedRef.current || operationId !== captureGenerationRef.current) return
          if (!chunks.length) {
            setError('No audio was captured.')
            dispatchRef.current({ type: 'COMPLETE' })
            return
          }

          dispatchRef.current({ type: 'THINK' })
          const controller = new AbortController()
          transcribeAbortRef.current = controller
          try {
            const result = await voiceApi.transcribe(new Blob(chunks, { type: recorder.mimeType || 'audio/webm' }), settings.sttLanguage, undefined, controller.signal)
            if (!mountedRef.current || operationId !== captureGenerationRef.current) return
            const transcript = result.text.trim()
            if (!transcript) {
              if (!onNoSpeech) setError('No speech was detected. Try speaking closer to the microphone.')
              onNoSpeech?.()
              dispatchRef.current({ type: 'COMPLETE' })
              return
            }
            onTranscript(transcript)
            dispatchRef.current({ type: 'COMPLETE' })
          } catch (caught) {
            if (!mountedRef.current || operationId !== captureGenerationRef.current) return
            if (caught instanceof DOMException && caught.name === 'AbortError') {
              dispatchRef.current({ type: networkOnlineRef.current ? 'CANCEL' : 'NETWORK_LOST' })
              return
            }
            setError(caught instanceof Error ? caught.message : 'Transcription failed.')
            dispatchRef.current({ type: 'FAIL' })
          } finally {
            if (transcribeAbortRef.current === controller) transcribeAbortRef.current = null
          }
        })()
      }

      recorder.start(250)
      setRecording(true)
      dispatchCore({ type: 'LISTEN' })

      if ((!settings.lowDataMode && !settings.reducedMotion || options.autoStopSilenceMs) && typeof AudioContext !== 'undefined') {
        let context: AudioContext | null = null
        try {
          context = new AudioContext()
          void context.resume?.().catch(() => undefined)
          audioContextRef.current = context
          const source = context.createMediaStreamSource(stream)
          const analyser = context.createAnalyser()
          analyser.fftSize = 64
          source.connect(analyser)
          const data = new Uint8Array(analyser.frequencyBinCount)
          const startedAt = performance.now()
          let speechDetected = false
          let silenceStartedAt: number | null = null
          const sample = () => {
            analyser.getByteFrequencyData(data)
            const now = performance.now()
            const currentLevel = data.reduce((sum, value) => sum + value, 0) / data.length / 255
            if (mountedRef.current && operationId === captureGenerationRef.current) setLevel(currentLevel)
            if (options.autoStopSilenceMs && recorder.state === 'recording') {
              if (currentLevel > 0.035) {
                speechDetected = true
                silenceStartedAt = null
              } else if (speechDetected || now - startedAt >= options.autoStopSilenceMs * 2) {
                silenceStartedAt ??= now
                if (now - silenceStartedAt >= options.autoStopSilenceMs) {
                  recorder.stop()
                  return
                }
              }
            }
            analyserFrame.current = requestAnimationFrame(sample)
          }
          sample()
        } catch {
          if (audioContextRef.current === context) audioContextRef.current = null
          if (context && context.state !== 'closed') void context.close().catch(() => undefined)
        }
      }
      return true
    } catch (caught) {
      if (!mountedRef.current || operationId !== captureGenerationRef.current) return false
      setError(microphoneError(caught))
      cancelCapture(false)
      dispatchCore({ type: 'FAIL' })
      return false
    } finally {
      openingRef.current = false
    }
  }, [cancelCapture, cancelPlayback, coreState, dispatchCore, networkOnline, onNoSpeech, onTranscript, online, releaseCapture, settings.lowDataMode, settings.reducedMotion, settings.sttLanguage])

  const stop = useCallback(() => {
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
  }, [])

  const stopSpeaking = useCallback(() => cancelPlayback(true), [cancelPlayback])

  const speak = useCallback(async (text: string) => {
    setError('')
    if (!online) {
      setError('Speech output needs a network connection.')
      if (!networkOnline) dispatchCore({ type: 'NETWORK_LOST' })
      return
    }
    if (recorderRef.current || captureRef.current || transcribeAbortRef.current) cancelCapture(true)
    if (playbackRef.current || synthAbortRef.current) cancelPlayback(true)
    const operationId = ++playbackGenerationRef.current
    if (coreState === 'ERROR') dispatchCore({ type: 'RECOVER' })
    dispatchCore({ type: 'SPEAK' })
    setSpeaking(true)

    const controller = new AbortController()
    synthAbortRef.current = controller
    let url = ''
    let audio: HTMLAudioElement | null = null
    let failed = false
    let interrupted = false
    try {
      const blob = await voiceApi.synthesize(text, undefined, settings.preferredVoice || undefined, controller.signal)
      if (!mountedRef.current || operationId !== playbackGenerationRef.current) throw abortError('Playback was cancelled.')
      url = URL.createObjectURL(blob)
      audio = new Audio(url)
      await new Promise<void>((resolve, reject) => {
        let settled = false
        const settle = (result: 'resolve' | 'reject', reason?: Error) => {
          if (settled) return
          settled = true
          if (result === 'resolve') resolve()
          else reject(reason)
        }
        playbackRef.current = { id: operationId, audio: audio!, url, abort: () => settle('reject', abortError('Playback was stopped.')) }
        audio!.onended = () => settle('resolve')
        audio!.onerror = () => settle('reject', new Error('Audio playback failed.'))
        audio!.onpause = () => { if (!audio!.ended) settle('reject', new Error('Audio playback was interrupted.')) }
        void audio!.play().catch(reason => settle('reject', reason instanceof Error ? reason : new Error('Audio playback could not start.')))
      })
    } catch (caught) {
      interrupted = caught instanceof DOMException && caught.name === 'AbortError'
      if (!interrupted && mountedRef.current && operationId === playbackGenerationRef.current) {
        failed = true
        setError(caught instanceof Error ? caught.message : 'Speech synthesis failed.')
        dispatchRef.current({ type: 'FAIL' })
      }
    } finally {
      if (audio) {
        audio.onended = null
        audio.onerror = null
        audio.onpause = null
        if (!audio.paused) audio.pause()
        audio.removeAttribute('src')
        audio.load()
      }
      if (url) URL.revokeObjectURL(url)
      if (playbackRef.current?.id === operationId) playbackRef.current = null
      if (synthAbortRef.current === controller) synthAbortRef.current = null
      if (mountedRef.current && operationId === playbackGenerationRef.current) {
        setSpeaking(false)
        if (!failed) dispatchRef.current({ type: networkOnlineRef.current ? (interrupted ? 'CANCEL' : 'COMPLETE') : 'NETWORK_LOST' })
      }
    }
  }, [cancelCapture, cancelPlayback, coreState, dispatchCore, networkOnline, online, settings.preferredVoice])

  return { recording, speaking, level, error, start, stop, speak, stopSpeaking, clearError: () => setError('') }
}
