import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, useState, type Dispatch, type ReactNode } from 'react'
import type { AppSettings, CoreState, PageId, User } from '../types'
import { authApi } from '../services/authApi'
import { DEFAULT_SETTINGS, settingsApi } from '../services/settingsApi'
import { coreReducer, type CoreEvent } from '../features/core/coreMachine'
import { useOnline } from '../hooks/useNetwork'

interface AppContextValue {
  user: User | null; sessionReady: boolean; sessionReachable: boolean; setUser: (user: User | null) => void; refreshSession: () => Promise<boolean>; retryConnection: () => void
  settings: AppSettings; updateSettings: (patch: Partial<AppSettings>) => Promise<void>
  coreState: CoreState; dispatchCore: Dispatch<CoreEvent>; online: boolean; networkOnline: boolean; page: PageId; setPage: (page: PageId) => void
}
const AppContext = createContext<AppContextValue | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const browserOnline = useOnline(); const [user, setUserState] = useState<User | null>(null); const [sessionReady, setSessionReady] = useState(false)
  const [sessionReachable, setSessionReachable] = useState(true); const [settings, setSettings] = useState(DEFAULT_SETTINGS)
  const settingsGenerationRef = useRef(0)
  const identityRef = useRef<string | null>(null)
  const setUser = useCallback((next: User | null) => {
    const nextId = next?.id ?? null
    if (identityRef.current !== nextId) {
      identityRef.current = nextId
      settingsGenerationRef.current += 1
      setSettings(DEFAULT_SETTINGS)
    }
    setUserState(next)
  }, [])
  const [coreState, dispatchCore] = useReducer(coreReducer, 'BOOTING'); const [page, setPage] = useState<PageId>('home')
  const refreshSession = useCallback(async () => {
    try { const session = await authApi.session(); setUser(session.user); setSessionReachable(true); return true }
    catch { setSessionReachable(false); setUser(null); return false }
    finally { setSessionReady(true) }
  }, [setUser])
  const online = browserOnline && sessionReachable
  const retryConnection = useCallback(() => dispatchCore({ type: 'RETRY' }), [])
  useEffect(() => { void refreshSession() }, [refreshSession])
  useEffect(() => { const timer = setTimeout(() => dispatchCore({ type: browserOnline ? 'BOOT_COMPLETE' : 'NETWORK_LOST' }), settings.reducedMotion || settings.lowDataMode ? 0 : 900); return () => clearTimeout(timer) }, [])
  useEffect(() => {
    if (!browserOnline) { dispatchCore({ type: 'NETWORK_LOST' }); return }
    if (coreState === 'OFFLINE') { dispatchCore({ type: 'NETWORK_FOUND' }); return }
    if (coreState === 'CONNECTING') { let active = true; void refreshSession().then(reachable => { if (active) dispatchCore({ type: reachable ? 'CONNECTED' : 'FAIL' }) }); return () => { active = false } }
  }, [browserOnline, coreState, refreshSession])
  useEffect(() => {
    const generation = ++settingsGenerationRef.current
    setSettings(DEFAULT_SETTINGS)
    if (!user || !sessionReachable) return
    const controller = new AbortController()
    void settingsApi.get(controller.signal).then(data => { if (generation === settingsGenerationRef.current) setSettings({ ...DEFAULT_SETTINGS, ...data.settings }) }).catch(error => { if (!(error instanceof DOMException && error.name === 'AbortError')) return })
    return () => { settingsGenerationRef.current += 1; controller.abort() }
  }, [user?.id, sessionReachable])
  const updateSettings = useCallback(async (patch: Partial<AppSettings>) => {
    if (!user || !sessionReachable) throw new Error('Reconnect before changing settings.')
    const ownerId = user.id; const generation = settingsGenerationRef.current; const previous = settings; const next = { ...settings, ...patch }; setSettings(next)
    try {
      const result = await settingsApi.update(patch)
      if (generation === settingsGenerationRef.current && identityRef.current === ownerId) setSettings({ ...DEFAULT_SETTINGS, ...result.settings })
    } catch (error) {
      if (generation === settingsGenerationRef.current && identityRef.current === ownerId) setSettings(previous)
      throw error
    }
  }, [sessionReachable, settings, user])
  useEffect(() => {
    document.documentElement.dataset.lowData = String(settings.lowDataMode)
    document.documentElement.dataset.reduceMotion = String(settings.reducedMotion)
    document.documentElement.dataset.accent = settings.accent
    document.documentElement.dataset.theme = settings.theme
    document.documentElement.dataset.textScale = settings.textScale
  }, [settings])
  const value = useMemo(() => ({ user, sessionReady, sessionReachable, setUser, refreshSession, retryConnection, settings, updateSettings, coreState, dispatchCore, online, networkOnline: browserOnline, page, setPage }), [user, sessionReady, sessionReachable, refreshSession, retryConnection, settings, updateSettings, coreState, online, browserOnline, page])
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}
export function useApp(): AppContextValue { const value = useContext(AppContext); if (!value) throw new Error('useApp must be used inside AppProvider'); return value }
