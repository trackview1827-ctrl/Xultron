import type { NativeVoiceServiceBridge, NativeVoiceServiceStatus } from '../features/settings/VoiceServiceControls'

export type NativeVoiceEnrollmentStatus = {
  state: 'COLLECTING' | 'CAPTURING' | 'COMPLETE' | 'BLOCKED' | 'ERROR'
  attempts: number
  acceptedAttempts: number
  requiredAttempts: number
  detail: string
  lastRejection?: string | null
}

export type NativeVoiceEnrollmentBridge = {
  getEnrollmentStatus: () => Promise<NativeVoiceEnrollmentStatus>
  captureEnrollmentSample: () => Promise<NativeVoiceEnrollmentStatus>
  clearEnrollment: () => Promise<NativeVoiceEnrollmentStatus>
}

type NativeVoicePort = EventTarget & { postMessage: (message: string) => void }
type VoiceReply = { id?: string; status?: NativeVoiceServiceStatus; enrollment?: NativeVoiceEnrollmentStatus; error?: string }

declare global {
  interface Window { XultronVoicePort?: NativeVoicePort }
}

const requestId = () => {
  const random = globalThis.crypto?.randomUUID?.().replaceAll('-', '') ?? Math.random().toString(36).slice(2)
  return `voice-${random}`.slice(0, 64)
}

/** Available only when Android's WebMessageListener created an origin-bound port. */
function requestNativeVoice(action: 'voice.status' | 'voice.start' | 'voice.stop' | 'voice.enrollment.status' | 'voice.enrollment.capture' | 'voice.enrollment.clear'): Promise<VoiceReply> {
  const port = window.XultronVoicePort
  if (!port) return Promise.reject(new Error('native_voice_bridge_unavailable'))
  return new Promise((resolve, reject) => {
    const id = requestId()
    const onMessage = (event: Event) => {
      const data = (event as MessageEvent<string>).data
      let reply: VoiceReply
      try { reply = JSON.parse(data) as VoiceReply } catch { return }
      if (reply.id !== id) return
      port.removeEventListener('message', onMessage)
      if (reply.error) reject(new Error(reply.error))
      else resolve(reply)
    }
    port.addEventListener('message', onMessage)
    try { port.postMessage(JSON.stringify({ v: 1, id, action })) }
    catch (error) { port.removeEventListener('message', onMessage); reject(error) }
  })
}

/**
 * Available only when Android's WebMessageListener created an origin-bound port.
 * This is not an addJavascriptInterface bridge and cannot accept arbitrary methods.
 */
export function nativeVoiceServiceBridge(): NativeVoiceServiceBridge | undefined {
  if (!window.XultronVoicePort) return undefined
  const request = async (action: 'voice.status' | 'voice.start' | 'voice.stop') => {
    const reply = await requestNativeVoice(action)
    if (!reply.status) throw new Error('native_voice_bridge_failed')
    return reply.status
  }
  return { getStatus: () => request('voice.status'), start: () => request('voice.start'), stop: () => request('voice.stop') }
}

/** Phrase text and raw audio never enter this bridge. Native captures transient PCM after confirmation. */
export function nativeVoiceEnrollmentBridge(): NativeVoiceEnrollmentBridge | undefined {
  if (!window.XultronVoicePort) return undefined
  const request = async (action: 'voice.enrollment.status' | 'voice.enrollment.capture' | 'voice.enrollment.clear') => {
    const reply = await requestNativeVoice(action)
    if (!reply.enrollment) throw new Error('native_voice_enrollment_failed')
    return reply.enrollment
  }
  return {
    getEnrollmentStatus: () => request('voice.enrollment.status'),
    captureEnrollmentSample: () => request('voice.enrollment.capture'),
    clearEnrollment: () => request('voice.enrollment.clear'),
  }
}
