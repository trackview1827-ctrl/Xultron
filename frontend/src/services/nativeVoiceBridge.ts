import type { NativeVoiceServiceBridge, NativeVoiceServiceStatus } from '../features/settings/VoiceServiceControls'

type NativeVoicePort = EventTarget & { postMessage: (message: string) => void }
type VoiceReply = { id?: string; status?: NativeVoiceServiceStatus; error?: string }

declare global {
  interface Window { XultronVoicePort?: NativeVoicePort }
}

const requestId = () => {
  const random = globalThis.crypto?.randomUUID?.().replaceAll('-', '') ?? Math.random().toString(36).slice(2)
  return `voice-${random}`.slice(0, 64)
}

/**
 * Available only when Android's WebMessageListener created an origin-bound port.
 * This is not an addJavascriptInterface bridge and cannot accept arbitrary methods.
 */
export function nativeVoiceServiceBridge(): NativeVoiceServiceBridge | undefined {
  const port = window.XultronVoicePort
  if (!port) return undefined

  const request = (action: 'voice.status' | 'voice.start' | 'voice.stop'): Promise<NativeVoiceServiceStatus> => new Promise((resolve, reject) => {
    const id = requestId()
    const onMessage = (event: Event) => {
      const data = (event as MessageEvent<string>).data
      let reply: VoiceReply
      try { reply = JSON.parse(data) as VoiceReply } catch { return }
      if (reply.id !== id) return
      port.removeEventListener('message', onMessage)
      if (reply.status) resolve(reply.status)
      else reject(new Error(reply.error ?? 'native_voice_bridge_failed'))
    }
    port.addEventListener('message', onMessage)
    try { port.postMessage(JSON.stringify({ v: 1, id, action })) }
    catch (error) { port.removeEventListener('message', onMessage); reject(error) }
  })

  return { getStatus: () => request('voice.status'), start: () => request('voice.start'), stop: () => request('voice.stop') }
}
