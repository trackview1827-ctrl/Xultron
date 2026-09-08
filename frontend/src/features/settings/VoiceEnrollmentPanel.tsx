import { useEffect, useMemo, useState } from 'react'
import { Button, Spinner } from '../../components/ui'
import { nativeVoiceEnrollmentBridge, type NativeVoiceEnrollmentBridge, type NativeVoiceEnrollmentStatus } from '../../services/nativeVoiceBridge'

const unavailable = 'Native enrollment is unavailable in this browser.'

export function VoiceEnrollmentPanel({ bridge }: { bridge?: NativeVoiceEnrollmentBridge } = {}) {
  const nativeBridge = useMemo(() => bridge ?? nativeVoiceEnrollmentBridge(), [bridge])
  const [status, setStatus] = useState<NativeVoiceEnrollmentStatus | null>(null)
  const [phrase, setPhrase] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!nativeBridge) return
    void nativeBridge.getEnrollmentStatus().then(setStatus).catch(() => setError('Could not read native enrollment status.'))
  }, [nativeBridge])

  if (!nativeBridge) return <section className="settings-callout" aria-label="Local voice profile unavailable">
    <div><strong>Experimental local voice profile</strong><p>{unavailable} Browser fallback never captures enrollment audio.</p></div>
  </section>

  const capture = async () => {
    if (phrase.trim().length < 2) { setError('Choose a wake phrase locally before recording a sample. The phrase is not sent to Android or the backend.'); return }
    setBusy(true); setError('')
    try { setStatus(await nativeBridge.captureEnrollmentSample()) }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Could not capture the local sample.') }
    finally { setBusy(false) }
  }
  const clear = async () => {
    setBusy(true); setError('')
    try { setStatus(await nativeBridge.clearEnrollment()) }
    catch { setError('Could not clear the local profile.') }
    finally { setBusy(false) }
  }
  const complete = status?.state === 'COMPLETE'
  const capturing = status?.state === 'CAPTURING'
  return <section className="settings-callout" aria-label="Experimental local voice profile">
    <div>
      <strong>Experimental local voice profile</strong>
      <p>{status?.detail ?? 'Checking native enrollment status.'}</p>
      <p>Type a phrase for your own practice only. It stays in this page and is never sent. Native capture requests one explicit two-second sample after Android confirmation, analyzes it locally, then discards the PCM. Five accepted samples create an encrypted profile, not a wake-word model.</p>
      <label className="field-label" htmlFor="wake-phrase">Local practice phrase</label>
      <input id="wake-phrase" className="field" value={phrase} maxLength={40} onChange={event => setPhrase(event.target.value)} placeholder="e.g. Hey Xultron" disabled={busy || complete} />
      <p role="status">Accepted samples: {status?.acceptedAttempts ?? 0} / {status?.requiredAttempts ?? 5}. Attempts used: {status?.attempts ?? 0} / {status?.requiredAttempts ?? 5}.</p>
      {status?.lastRejection && <p role="alert">Last sample rejected: {status.lastRejection}. A rejected explicit sample uses a slot to prevent silent retry loops.</p>}
      {error && <p role="alert">{error}</p>}
    </div>
    <div className="settings-callout__actions">
      <Button onClick={() => void capture()} disabled={busy || capturing || complete || status === null}>{busy || capturing ? <Spinner /> : 'RECORD LOCAL SAMPLE'}</Button>
      <Button onClick={() => void clear()} disabled={busy || capturing || status === null}>CLEAR LOCAL PROFILE</Button>
    </div>
  </section>
}
