import { useState, type FormEvent } from 'react'
import { motion } from 'framer-motion'
import { useApp } from '../../stores/AppContext'
import { authApi } from '../../services/authApi'
import { ApiError } from '../../services/apiClient'
import { Button, Field, Input, Spinner } from '../../components/ui'
import { XultronCore } from '../core/XultronCore'

export function AuthGateway() {
  const { setUser, sessionReachable, settings } = useApp(); const [mode, setMode] = useState<'entry' | 'login' | 'register'>('entry')
  const [busy, setBusy] = useState(false); const [error, setError] = useState('')
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setBusy(true); setError(''); const data = new FormData(event.currentTarget)
    try {
      if (mode === 'login') { const result = await authApi.login({ identifier: String(data.get('identifier')), password: String(data.get('password')) }); setUser(result.user) }
      else { const password = String(data.get('password')); if (password.length < 10) throw new Error('Use at least 10 characters for your password.'); const result = await authApi.register({ username: String(data.get('username')), email: String(data.get('email')), password }); setUser(result.user) }
    } catch (caught) { setError(caught instanceof ApiError || caught instanceof Error ? caught.message : 'Authentication failed.') }
    finally { setBusy(false) }
  }
  const enterGuest = async () => { setBusy(true); setError(''); try { const result = await authApi.guest(); setUser(result.user) } catch (caught) { setError(caught instanceof Error ? caught.message : 'Guest access is unavailable.') } finally { setBusy(false) } }
  return <main className="auth-screen">
    <motion.section className="auth-core" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}><div className="brand-lockup"><span className="eyebrow">PERSONAL INTELLIGENCE SYSTEM</span><h1>XULTRON</h1></div><XultronCore state={sessionReachable ? 'ONLINE' : 'OFFLINE'} reducedMotion={settings.reducedMotion} /></motion.section>
    <motion.section className="auth-panel" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: .15 }}>
      {mode === 'entry' ? <><span className="section-index">SYSTEM ACCESS / 01</span><h2>Your intelligence.<br />Under your control.</h2><p>Enter a private AI environment built around voice, memory, and providers you choose.</p><div className="auth-actions"><Button onClick={() => setMode('login')}>SIGN IN</Button><Button variant="secondary" onClick={() => setMode('register')}>CREATE IDENTITY</Button><button className="text-button" onClick={enterGuest} disabled={busy}>{busy ? <Spinner /> : 'CONTINUE AS GUEST'}</button></div></> :
      <form onSubmit={submit} noValidate><button className="text-button back-link" type="button" onClick={() => { setMode('entry'); setError('') }}>← SYSTEM ACCESS</button><span className="section-index">{mode === 'login' ? 'IDENTITY VERIFICATION' : 'NEW IDENTITY'}</span><h2>{mode === 'login' ? 'Welcome back.' : 'Initialize your space.'}</h2>
        {mode === 'register' && <><Field label="Username"><Input name="username" autoComplete="username" required minLength={3} /></Field><Field label="Email"><Input name="email" type="email" autoComplete="email" required /></Field></>}
        {mode === 'login' && <Field label="Username or email"><Input name="identifier" autoComplete="username" required /></Field>}
        <Field label="Password" hint={mode === 'register' ? 'Minimum 10 characters' : undefined}><Input name="password" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required minLength={mode === 'register' ? 10 : undefined} /></Field>
        {error && <div className="inline-error" role="alert">{error}</div>}<Button type="submit" disabled={busy}>{busy ? <Spinner /> : mode === 'login' ? 'VERIFY IDENTITY' : 'CREATE IDENTITY'}</Button>
      </form>}
      {!sessionReachable && <div className="offline-note">Backend link unavailable. The cached interface is ready, but account access requires a connection.</div>}
    </motion.section>
  </main>
}
