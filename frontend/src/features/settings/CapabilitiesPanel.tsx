import { useEffect, useState } from 'react'
import type { ToolDescription } from '../../types'
import { tasksApi } from '../../services/tasksApi'
import { useLocale } from '../../hooks/useLocale'
import { Button, Spinner } from '../../components/ui'
import { Icon } from '../../components/Icon'

 type BrowserCapability = 'microphone' | 'camera' | 'geolocation' | 'notifications'
 type CapabilityState = PermissionState | 'unsupported' | 'checking' | 'testing'

 const capabilityCopy: Record<BrowserCapability, { title: string; titleTr: string; description: string; descriptionTr: string }> = {
   microphone: { title: 'Microphone', titleTr: 'Mikrofon', description: 'Required for voice input. The Android system permission is requested only after you press Test.', descriptionTr: 'Sesli giriş için gereklidir. Android sistem izni yalnızca Test düğmesine bastığında istenir.' },
   camera: { title: 'Camera', titleTr: 'Kamera', description: 'Reserved for camera features. No camera stream is opened during status checks.', descriptionTr: 'Kamera özellikleri için ayrılmıştır. Durum kontrolünde kamera akışı açılmaz.' },
   geolocation: { title: 'Location', titleTr: 'Konum', description: 'Checked only on explicit request and never continuously in this release.', descriptionTr: 'Yalnızca açık istekte kontrol edilir ve bu sürümde sürekli izlenmez.' },
   notifications: { title: 'Notifications', titleTr: 'Bildirimler', description: 'Controls browser or Android WebView notification permission.', descriptionTr: 'Tarayıcı veya Android WebView bildirim iznini kontrol eder.' },
 }

 async function readPermission(name: BrowserCapability): Promise<CapabilityState> {
   if (!navigator.permissions?.query) return 'unsupported'
   try {
     const status = await navigator.permissions.query({ name: name as PermissionName })
     return status.state
   } catch {
     return 'unsupported'
   }
 }

 export function CapabilitiesPanel({ online }: { online: boolean }) {
   const { t } = useLocale()
   const [states, setStates] = useState<Record<BrowserCapability, CapabilityState>>({ microphone: 'checking', camera: 'checking', geolocation: 'checking', notifications: 'checking' })
   const [tools, setTools] = useState<ToolDescription[]>([])
   const [loadingTools, setLoadingTools] = useState(false)
   const [error, setError] = useState('')
   const [testing, setTesting] = useState<BrowserCapability | null>(null)

   const refresh = async () => {
     setStates({ microphone: 'checking', camera: 'checking', geolocation: 'checking', notifications: 'checking' })
     const entries = await Promise.all((Object.keys(capabilityCopy) as BrowserCapability[]).map(async name => [name, await readPermission(name)] as const))
     setStates(Object.fromEntries(entries) as Record<BrowserCapability, CapabilityState>)
   }

   useEffect(() => { void refresh() }, [])
   useEffect(() => {
     if (!online) { setTools([]); return }
     let active = true
     setLoadingTools(true)
     void tasksApi.tools().then(result => { if (active) setTools(result.tools) }).catch(caught => { if (active) setError(caught instanceof Error ? caught.message : t('Capabilities could not be loaded.', 'Yetenekler yüklenemedi.')) }).finally(() => { if (active) setLoadingTools(false) })
     return () => { active = false }
   }, [online, t])

   const test = async (name: BrowserCapability) => {
     setTesting(name); setError('')
     try {
       if (name === 'microphone' || name === 'camera') {
         if (!navigator.mediaDevices?.getUserMedia) throw new Error(t('This WebView does not expose media capture.', 'Bu WebView medya yakalamayı desteklemiyor.'))
         const stream = await navigator.mediaDevices.getUserMedia(name === 'microphone' ? { audio: true } : { video: true })
         stream.getTracks().forEach(track => track.stop())
       } else if (name === 'geolocation') {
         if (!navigator.geolocation) throw new Error(t('Location is not available in this WebView.', 'Bu WebView konum özelliğini sunmuyor.'))
         await new Promise<void>((resolve, reject) => navigator.geolocation.getCurrentPosition(() => resolve(), error => reject(new Error(error.message)), { maximumAge: 60000, timeout: 8000 }))
     } else {
       if (typeof Notification === 'undefined') throw new Error(t('Notifications are not supported in this WebView.', 'Bu WebView bildirimleri desteklemiyor.'))
       if (Notification.permission === 'granted') { await refresh(); return }
       await Notification.requestPermission()
     }
       await refresh()
     } catch (caught) {
       setError(caught instanceof Error ? caught.message : t('Capability test failed.', 'Yetenek testi başarısız oldu.'))
     } finally { setTesting(null) }
   }

   return <div className="settings-panel capabilities-panel">
     <div className="settings-section-head"><div><h2>{t('Capabilities', 'Yetenekler')}</h2><p>{t('Inspect permission boundaries before Xultron uses a device capability. Nothing is activated silently.', 'Xultron bir cihaz yeteneğini kullanmadan önce izin sınırlarını incele. Hiçbir şey sessizce etkinleştirilmez.')}</p></div><button className="capability-refresh" onClick={() => void refresh()} aria-label={t('Refresh capability status', 'Yetenek durumunu yenile')}><Icon name="refresh" /></button></div>
     <div className="settings-controls">
       <div className="capability-list">{(Object.keys(capabilityCopy) as BrowserCapability[]).map(name => { const copy = capabilityCopy[name]; const state = states[name]; return <div className="capability-row" key={name}><div className="capability-icon"><Icon name={name === 'microphone' ? 'mic' : name === 'notifications' ? 'signal' : name === 'geolocation' ? 'signal' : 'core'} /></div><div className="capability-copy"><strong>{t(copy.title, copy.titleTr)}</strong><p>{t(copy.description, copy.descriptionTr)}</p><small className={`capability-state capability-${state}`}>{state === 'checking' ? t('CHECKING', 'KONTROL EDİLİYOR') : state === 'unsupported' ? t('UNAVAILABLE', 'KULLANILAMIYOR') : state.toUpperCase()}</small></div><Button variant="secondary" onClick={() => void test(name)} disabled={testing !== null || state === 'checking'}>{testing === name ? <Spinner /> : t('TEST', 'TEST ET')}</Button></div> })}</div>
       <div className="settings-callout"><Icon name="shield" /><div><strong>{t('Android boundary', 'Android sınırı')}</strong><p>{t('In the APK, microphone and camera prompts are forwarded to Android only for the configured backend origin. A denied permission stays denied.', 'APK içinde mikrofon ve kamera istemleri yalnızca yapılandırılmış backend originine Android’e aktarılır. Reddedilen izin reddedilmiş kalır.')}</p></div></div>
       <div className="capability-tools"><span className="section-index">{t('BACKEND TOOLS', 'BACKEND ARAÇLARI')}</span>{loadingTools ? <div className="center-loader"><Spinner /></div> : tools.length ? tools.map(tool => <div className="capability-tool" key={tool.name}><div><strong>{tool.name}</strong><p>{tool.description}</p><small>{tool.requiredPermissions.length ? `${t('Requires', 'Gerektirir')}: ${tool.requiredPermissions.join(', ')}` : t('No extra permission', 'Ek izin yok')} · {tool.riskLevel.toUpperCase()}</small></div><span className={tool.available ? 'tool-available' : 'tool-blocked'}>{tool.available ? t('AVAILABLE', 'KULLANILABİLİR') : t('BLOCKED', 'ENGELLİ')}</span></div>) : <p className="capability-empty">{online ? t('No backend tools are currently exposed.', 'Şu anda backend aracı sunulmuyor.') : t('Reconnect to inspect backend tools.', 'Backend araçlarını görmek için yeniden bağlan.')}</p>}</div>
       {error && <div className="inline-error" role="alert">{error}</div>}
     </div>
   </div>
 }
