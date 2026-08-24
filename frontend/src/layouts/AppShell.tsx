import { AnimatePresence, motion } from 'framer-motion'
import type { PageId } from '../types'
import { useApp } from '../stores/AppContext'
import { Icon, type IconName } from '../components/Icon'
import { HomePage } from '../features/chat/HomePage'
import { MemoryPage } from '../features/memory/MemoryPage'
import { SettingsPage } from '../features/settings/SettingsPage'
import { formatBytes, useDataUsage } from '../hooks/useNetwork'
import { conservesMotion } from '../theme/motionPolicy'
import { useLocale } from '../hooks/useLocale'

const nav: { id: PageId; label: string; labelTr: string; icon: IconName }[] = [{ id: 'home', label: 'Core', labelTr: 'Çekirdek', icon: 'core' }, { id: 'memory', label: 'Memory', labelTr: 'Hafıza', icon: 'memory' }, { id: 'settings', label: 'Systems', labelTr: 'Sistemler', icon: 'settings' }]
export function AppShell() {
  const { page, setPage, online, user, settings, retryConnection } = useApp(); const usage = useDataUsage()
  const { t } = useLocale()
  const conserveMotion = conservesMotion(settings)
  return <div className="app-shell"><header className="topbar"><button className="wordmark" onClick={() => setPage('home')} aria-label={t('Go to Xultron Core', 'Xultron Çekirdeğine git')}><span>X</span><strong>XULTRON</strong></button><div className="system-meta"><span className={online ? 'online' : 'offline'}><i />{online ? t('LINKED', 'BAĞLI') : t('OFFLINE', 'ÇEVRİMDIŞI')}</span>{settings.lowDataMode && <span>{t('LOW DATA', 'DÜŞÜK VERİ')}</span>}<span className="desktop-only">↓ {formatBytes(usage.downloaded)} · ↑ {formatBytes(usage.uploaded)}</span><span className="identity">{user?.isGuest ? t('GUEST', 'MİSAFİR') : user?.username}</span></div></header>
    <nav className="system-nav" aria-label={t('Primary navigation', 'Ana navigasyon')}>{nav.map(item => <button key={item.id} className={page === item.id ? 'active' : ''} onClick={() => setPage(item.id)} aria-current={page === item.id ? 'page' : undefined}><Icon name={item.icon} /><span className="nav-label">{t(item.label, item.labelTr)}</span></button>)}</nav>
    <main className="app-content"><AnimatePresence mode={conserveMotion ? 'sync' : 'wait'} initial={false}><motion.div key={page} className="page-motion" initial={conserveMotion ? false : { opacity: 0, x: 6 }} animate={{ opacity: 1, x: 0 }} exit={conserveMotion ? undefined : { opacity: 0, x: -6 }} transition={{ duration: conserveMotion ? 0 : .18 }}>{page === 'home' ? <HomePage /> : page === 'memory' ? <MemoryPage /> : <SettingsPage />}</motion.div></AnimatePresence></main>
    {!online && <div className="reconnect-strip" role="status"><Icon name="signal" /><span>{t('NETWORK OR BACKEND LINK UNAVAILABLE', 'AĞ VEYA BACKEND BAĞLANTISI YOK')}</span><button onClick={retryConnection}>{t('RETRY LINK', 'YENİDEN BAĞLAN')}</button></div>}
  </div>
}
