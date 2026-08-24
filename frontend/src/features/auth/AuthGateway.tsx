import { useRef, useState, type ClipboardEvent, type FormEvent, type KeyboardEvent } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useApp } from '../../stores/AppContext'
import { authApi } from '../../services/authApi'
import { ApiError } from '../../services/apiClient'
import { Button, Input, Spinner } from '../../components/ui'
import { XultronCore } from '../core/XultronCore'
import { conservesMotion } from '../../theme/motionPolicy'

const PIN_LENGTH = 4
const LOCAL_USERNAME = 'local-user'

export function AuthGateway() {
  const { setUser, sessionReachable, settings, retryConnection } = useApp()
  const [digits, setDigits] = useState<string[]>(Array(PIN_LENGTH).fill(''))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const inputs = useRef<Array<HTMLInputElement | null>>([])
  const conserveMotion = conservesMotion(settings)
  const pin = digits.join('')

  const applyDigits = (start: number, raw: string) => {
    const numeric = raw.replace(/\D/g, '').slice(0, PIN_LENGTH - start)
    if (!numeric) return
    setDigits(current => {
      const next = [...current]
      for (let offset = 0; offset < numeric.length; offset += 1) next[start + offset] = numeric[offset]!
      return next
    })
    setError('')
    const nextIndex = Math.min(start + numeric.length, PIN_LENGTH - 1)
    window.requestAnimationFrame(() => inputs.current[nextIndex]?.focus())
  }

  const handleKeyDown = (index: number, event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Backspace' && !digits[index] && index > 0) {
      event.preventDefault()
      setDigits(current => current.map((digit, position) => position === index - 1 ? '' : digit))
      inputs.current[index - 1]?.focus()
    } else if (event.key === 'ArrowLeft' && index > 0) inputs.current[index - 1]?.focus()
    else if (event.key === 'ArrowRight' && index < PIN_LENGTH - 1) inputs.current[index + 1]?.focus()
  }

  const handlePaste = (event: ClipboardEvent<HTMLInputElement>) => {
    event.preventDefault()
    const numeric = event.clipboardData.getData('text').replace(/\D/g, '').slice(0, PIN_LENGTH)
    if (!numeric) return
    setDigits(Array.from({ length: PIN_LENGTH }, (_, index) => numeric[index] ?? ''))
    setError('')
    window.requestAnimationFrame(() => inputs.current[Math.min(numeric.length, PIN_LENGTH) - 1]?.focus())
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!/^\d{4}$/.test(pin)) { setError('PIN tam olarak 4 rakam olmalıdır.'); inputs.current[0]?.focus(); return }
    setBusy(true); setError('')
    try {
      const result = await authApi.login({ identifier: LOCAL_USERNAME, password: pin })
      setUser(result.user)
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === 'invalid_credentials') setError('Kullanıcı adı veya PIN hatalı.')
      else if (caught instanceof ApiError && caught.code === 'validation_failed') setError('PIN tam olarak 4 rakam olmalıdır.')
      else setError(caught instanceof Error ? caught.message : 'Giriş yapılamadı. Lütfen tekrar dene.')
      setDigits(Array(PIN_LENGTH).fill(''))
      window.requestAnimationFrame(() => inputs.current[0]?.focus())
    } finally { setBusy(false) }
  }

  const enterGuest = async () => {
    setBusy(true); setError('')
    try { const result = await authApi.guest(); setUser(result.user) }
    catch { setError('Misafir erişimi şu anda kullanılamıyor.') }
    finally { setBusy(false) }
  }

  return <main className="auth-screen">
    <motion.section className="auth-core" initial={conserveMotion ? false : { opacity: 0, scale: .96 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: conserveMotion ? 0 : .5, ease: 'easeOut' }}>
      <div className="brand-lockup"><span className="eyebrow">KİŞİSEL YAPAY ZEKA SİSTEMİ</span><h1>XULTRON</h1></div>
      <XultronCore state={sessionReachable ? 'ONLINE' : 'OFFLINE'} reducedMotion={conserveMotion} />
    </motion.section>
    <motion.section className="auth-panel" initial={conserveMotion ? false : { opacity: 0, x: 18 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: conserveMotion ? 0 : .12, duration: conserveMotion ? 0 : .38 }}>
      <span className="section-index">SİSTEM ERİŞİMİ / 01</span>
      <h2>Hoş geldin,<br />Local User.</h2>
      <p>Kimliğini doğrulamak için dört haneli Xultron PIN kodunu gir.</p>
      <form onSubmit={submit} noValidate className="pin-login-form">
        <label className="field-wrap"><span className="field-label">KULLANICI</span><Input value={LOCAL_USERNAME} readOnly aria-readonly="true" autoComplete="username" /></label>
        <fieldset className="pin-fieldset" disabled={busy}>
          <legend className="field-label">4 HANELİ PIN</legend>
          <motion.div className="pin-grid" animate={error && !conserveMotion ? { x: [0, -6, 6, -4, 4, 0] } : { x: 0 }} transition={{ duration: .32 }}>
            {digits.map((digit, index) => <motion.input
              key={index}
              ref={element => { inputs.current[index] = element }}
              className={`pin-cell ${digit ? 'filled' : ''}`}
              type="password"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={1}
              value={digit}
              autoComplete={index === 0 ? 'one-time-code' : 'off'}
              aria-label={`PIN hanesi ${index + 1}`}
              onChange={event => { const value = event.target.value; if (!value) setDigits(current => current.map((entry, position) => position === index ? '' : entry)); else applyDigits(index, value) }}
              onKeyDown={event => handleKeyDown(index, event)}
              onPaste={handlePaste}
              initial={conserveMotion ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: conserveMotion ? 0 : .18 + index * .06, duration: conserveMotion ? 0 : .22 }}
              autoFocus={index === 0}
            />)}
          </motion.div>
          <span className="field-hint">Yalnızca rakam kullan.</span>
        </fieldset>
        <AnimatePresence mode="wait">{error && <motion.div key={error} className="inline-error" role="alert" initial={conserveMotion ? false : { opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>{error}</motion.div>}</AnimatePresence>
        <Button type="submit" disabled={busy || pin.length !== PIN_LENGTH || !sessionReachable}>{busy ? <Spinner /> : 'SİSTEME GİR'}</Button>
        <button className="text-button" type="button" onClick={enterGuest} disabled={busy || !sessionReachable}>MİSAFİR OLARAK DEVAM ET</button>
      </form>
      {!sessionReachable && <div className="offline-note">Backend bağlantısı yok. Hesap erişimi için bağlantıyı yeniden kur.<button className="text-button" onClick={retryConnection}>BAĞLANTIYI YENİLE</button></div>}
    </motion.section>
  </main>
}
