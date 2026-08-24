import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useState, type Dispatch, type ReactNode } from 'react'
import type { AppSettings, CoreState, PageId, User } from '../types'
import { authApi } from '../services/authApi'
import { DEFAULT_SETTINGS, settingsApi } from '../services/settingsApi'
import { coreReducer, type CoreEvent } from '../features/core/coreMachine'
import { useOnline } from '../hooks/useNetwork'

interface AppContextValue {
  user: User | null; sessionReady: boolean; sessionReachable: boolean; setUser: (user: User | null) => void; refreshSession: () => Promise<void>
  settings: AppSettings; updateSettings: (patch: Partial<AppSettings>) => Promise<void>
  coreState: CoreState; dispatchCore: Dispatch<CoreEvent>; online: boolean; page: PageId; setPage: (page: PageId) => void
}
const AppContext = createContext<AppContextValue | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const online = useOnline(); const [user, setUser] = useState<User | null>(null); const [sessionReady, setSessionReady] = useState(false)
  const [sessionReachable, setSessionReachable] = useState(true); const [settings, setSettings] = useState(DEFAULT_SETTINGS)
  const [coreState, dispatchCore] = useReducer(coreReducer, 'BOOTING'); const [page, setPage] = useState<PageId>('home')
  const refreshSession = useCallback(async () => {
    try { const session = await authApi.session(); setUser(session.user); setSessionReachable(true) }
    catch { setSessionReachable(false); setUser(null) }
    finally { setSessionReady(true) }
  }, [])
  useEffect(() => { void refreshSession() }, [refreshSession])
  useEffect(() => { const timer = setTimeout(() => dispatchCore({ type: online ? 'BOOT_COMPLETE' : 'NETWORK_LOST' }), settings.reducedMotion ? 0 : 900); return () => clearTimeout(timer) }, [])
  useEffect(() => {
    if (!online) { dispatchCore({ type: 'NETWORK_LOST' }); return }
    if (coreState === 'OFFLINE') { dispatchCore({ type: 'NETWORK_FOUND' }); return }
    if (coreState === 'CONNECTING') { const timer = setTimeout(() => dispatchCore({ type: 'CONNECTED' }), 450); return () => clearTimeout(timer) }
  }, [coreState, online])
  useEffect(() => { if (!user || !sessionReachable) return; settingsApi.get().then(data => setSettings({ ...DEFAULT_SETTINGS, ...data.settings })).catch(() => undefined) }, [user, sessionReachable])
  const updateSettings = useCallback(async (patch: Partial<AppSettings>) => {
    const previous = settings; const next = { ...settings, ...patch }; setSettings(next)
    try { if (user && sessionReachable) { const result = await settingsApi.update(patch); setSettings({ ...DEFAULT_SETTINGS, ...result.settings }) } }
    catch (error) { setSettings(previous); throw error }
  }, [sessionReachable, settings, user])
  useEffect(() => {
    document.documentElement.dataset.lowData = String(settings.lowDataMode)
    document.documentElement.dataset.reduceMotion = String(settings.reducedMotion)
    document.documentElement.dataset.accent = settings.accent
    document.documentElement.dataset.theme = settings.theme
    document.documentElement.dataset.textScale = settings.textScale
  }, [settings])
  const value = useMemo(() => ({ user, sessionReady, sessionReachable, setUser, refreshSession, settings, updateSettings, coreState, dispatchCore, online, page, setPage }), [user, sessionReady, sessionReachable, refreshSession, settings, updateSettings, coreState, online, page])
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}
export function useApp(): AppContextValue { const value = useContext(AppContext); if (!value) throw new Error('useApp must be used inside AppProvider'); return value }
