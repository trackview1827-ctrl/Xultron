import { useEffect, useMemo, useState } from 'react'
import { Button, Spinner } from '../../components/ui'
import { nativeVoiceServiceBridge } from '../../services/nativeVoiceBridge'

export type NativeVoiceServiceStatus = {
  state: 'STOPPED' | 'STARTING' | 'MONITORING_EXPERIMENTAL' | 'STOPPING' | 'BLOCKED' | 'ERROR'
  detail: string
  blockReason?: string | null
  diagnostic: {
    cloudSttEnabled: boolean
    rawAudioUploadEnabled: boolean
    pollingEnabled: boolean
    persistentWebSocketEnabled: boolean
    rawAudioPersisted: boolean
    lastError?: string | null
  }
}

/** This API must be injected only by a verified Xultron Android WebView origin. */
export type NativeVoiceServiceBridge = {
  getStatus: () => Promise<NativeVoiceServiceStatus>
  start: () => Promise<NativeVoiceServiceStatus>
  stop: () => Promise<NativeVoiceServiceStatus>
}

const unavailable = 'Native voice controls are unavailable in this browser.'

export function VoiceServiceControls({ bridge }: { bridge?: NativeVoiceServiceBridge } = {}) {
  const nativeBridge = useMemo(() => bridge ?? nativeVoiceServiceBridge(), [bridge])
  const [status, setStatus] = useState<NativeVoiceServiceStatus | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const refresh = async () => {
    if (!nativeBridge) return
    try { setStatus(await nativeBridge.getStatus()); setError('') } catch { setError('Could not read native voice status.') }
  }
  useEffect(() => { void refresh() }, [nativeBridge])

  if (!nativeBridge) return <section className="settings-callout" aria-label="Local voice monitor unavailable">
    <div><strong>Experimental local voice monitor</strong><p>{unavailable} Browser fallback never opens the microphone or imitates a persistent background service.</p></div>
  </section>

  const active = status?.state === 'MONITORING_EXPERIMENTAL' || status?.state === 'STARTING' || status?.state === 'STOPPING'
  const command = async () => {
    setBusy(true); setError('')
    try { setStatus(active ? await nativeBridge.stop() : await nativeBridge.start()) } catch { setError(active ? 'Could not stop the local monitor.' : 'Could not start the local monitor.') } finally { setBusy(false) }
  }

  return <section className="settings-callout" aria-label="Experimental local voice monitor">
    <div><strong>Experimental local voice monitor</strong><p>{status?.detail ?? 'Checking native status.'}</p>
      <p>Local-only diagnostic: cloud STT, raw-audio upload, polling, and persistent WebSocket use are disabled. The microphone remains closed until a local model is installed and independently benchmarked for FAR/FRR, replay, noise, thermal, and battery behavior.</p>
      {status?.blockReason && <p role="alert">Blocked: {status.blockReason}</p>}
      {error && <p role="alert">{error}</p>}
    </div>
    <Button onClick={() => void command()} disabled={busy || status === null}>{busy ? <Spinner /> : active ? 'STOP LOCAL MONITOR' : 'START LOCAL MONITOR'}</Button>
  </section>
}
