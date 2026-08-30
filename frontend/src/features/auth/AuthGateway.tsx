import { useState, type FormEvent } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useApp } from '../../stores/AppContext'
import { authApi } from '../../services/authApi'
import { ApiError } from '../../services/apiClient'
import { Button, Input, Spinner } from '../../components/ui'
import { XultronCore } from '../core/XultronCore'
import { conservesMotion } from '../../theme/motionPolicy'

export function AuthGateway() {
  const { setUser, sessionReachable, settings, retryConnection } = useApp()
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const conserveMotion = conservesMotion(settings)

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const normalizedIdentifier = identifier.trim()
    if (!normalizedIdentifier || !password) {
      setError('Kullanıcı adı ve parola gereklidir.')
      return
    }
    setBusy(true); setError('')
    try {
      const result = await authApi.login({ identifier: normalizedIdentifier, password })
      setUser(result.user)
    } catch (caught) {
      if (caught instanceof ApiError && ['invalid_credentials', 'validation_failed'].includes(caught.code)) {
        setError('Kullanıcı adı veya parola hatalı.')
      } else setError(caught instanceof Error ? caught.message : 'Giriş yapılamadı. Lütfen tekrar dene.')
      setPassword('')
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
      <h2>Hoş geldin,<br />operatör.</h2>
      <p>Xultron kurulurken oluşturduğun kullanıcı adı ve parolayla kimliğini doğrula.</p>
      <form onSubmit={submit} noValidate className="pin-login-form">
        <label className="field-wrap"><span className="field-label">KULLANICI ADI</span><Input value={identifier} onChange={event => { setIdentifier(event.target.value); setError('') }} autoComplete="username" autoFocus disabled={busy} /></label>
        <label className="field-wrap"><span className="field-label">PAROLA</span><Input type="password" value={password} onChange={event => { setPassword(event.target.value); setError('') }} autoComplete="current-password" disabled={busy} /></label>
        <span className="field-hint">Terminalde ilk çalıştırmada oluşturduğun bilgileri kullan.</span>
        <AnimatePresence mode="wait">{error && <motion.div key={error} className="inline-error" role="alert" initial={conserveMotion ? false : { opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>{error}</motion.div>}</AnimatePresence>
        <Button type="submit" disabled={busy || !identifier.trim() || !password || !sessionReachable}>{busy ? <Spinner /> : 'SİSTEME GİR'}</Button>
        <button className="text-button" type="button" onClick={enterGuest} disabled={busy || !sessionReachable}>MİSAFİR OLARAK DEVAM ET</button>
      </form>
      {!sessionReachable && <div className="offline-note">Backend bağlantısı yok. Hesap erişimi için bağlantıyı yeniden kur.<button className="text-button" onClick={retryConnection}>BAĞLANTIYI YENİLE</button></div>}
    </motion.section>
  </main>
}
