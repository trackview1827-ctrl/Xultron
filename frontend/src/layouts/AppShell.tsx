import { AnimatePresence, motion } from 'framer-motion'
import type { PageId } from '../types'
import { useApp } from '../stores/AppContext'
import { Icon, type IconName } from '../components/Icon'
import { HomePage } from '../features/chat/HomePage'
import { MemoryPage } from '../features/memory/MemoryPage'
import { SettingsPage } from '../features/settings/SettingsPage'
import { formatBytes, useDataUsage } from '../hooks/useNetwork'
import { conservesMotion } from '../theme/motionPolicy'

const nav: { id: PageId; label: string; icon: IconName }[] = [{ id: 'home', label: 'Core', icon: 'core' }, { id: 'memory', label: 'Memory', icon: 'memory' }, { id: 'settings', label: 'Systems', icon: 'settings' }]
export function AppShell() {
  const { page, setPage, online, user, settings, retryConnection } = useApp(); const usage = useDataUsage()
  const conserveMotion = conservesMotion(settings)
  return <div className="app-shell"><header className="topbar"><button className="wordmark" onClick={() => setPage('home')} aria-label="Go to Xultron Core"><span>X</span><strong>XULTRON</strong></button><div className="system-meta"><span className={online ? 'online' : 'offline'}><i />{online ? 'LINKED' : 'OFFLINE'}</span>{settings.lowDataMode && <span>LOW DATA</span>}<span className="desktop-only">↓ {formatBytes(usage.downloaded)} · ↑ {formatBytes(usage.uploaded)}</span><span className="identity">{user?.isGuest ? 'GUEST' : user?.username}</span></div></header>
    <nav className="system-nav" aria-label="Primary navigation">{nav.map(item => <button key={item.id} className={page === item.id ? 'active' : ''} onClick={() => setPage(item.id)} aria-current={page === item.id ? 'page' : undefined}><Icon name={item.icon} /><span className="nav-label">{item.label}</span></button>)}</nav>
    <main className="app-content"><AnimatePresence mode={conserveMotion ? 'sync' : 'wait'} initial={false}><motion.div key={page} className="page-motion" initial={conserveMotion ? false : { opacity: 0, x: 6 }} animate={{ opacity: 1, x: 0 }} exit={conserveMotion ? undefined : { opacity: 0, x: -6 }} transition={{ duration: conserveMotion ? 0 : .18 }}>{page === 'home' ? <HomePage /> : page === 'memory' ? <MemoryPage /> : <SettingsPage />}</motion.div></AnimatePresence></main>
    {!online && <div className="reconnect-strip" role="status"><Icon name="signal" /><span>NETWORK OR BACKEND LINK UNAVAILABLE</span><button onClick={retryConnection}>RETRY LINK</button></div>}
  </div>
}
