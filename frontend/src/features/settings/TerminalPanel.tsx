import { Icon } from '../../components/Icon'
import { useLocale } from '../../hooks/useLocale'

export type TerminalAvailability = 'sandbox-ready' | 'disabled' | 'adapter-unavailable'

export function TerminalPanel({ availability = 'sandbox-ready' }: { availability?: TerminalAvailability }) {
  const { t } = useLocale()
  const enabled = availability === 'sandbox-ready'
  const status = enabled
    ? t('APP SANDBOX POLICY ACTIVE', 'UYGULAMA SANDBOX POLİTİKASI ETKİN')
    : availability === 'disabled'
      ? t('TERMINAL DISABLED', 'TERMİNAL DEVRE DIŞI')
      : t('ADVANCED ADAPTER UNAVAILABLE', 'GELİŞMİŞ BAĞDAŞTIRICI KULLANILAMIYOR')

  return <section className="settings-panel terminal-panel" aria-labelledby="terminal-heading">
    <div className="settings-section-head"><div><h2 id="terminal-heading">{t('Terminal safety', 'Terminal güvenliği')}</h2><p>{t('This release has no command box. Only signed, versioned local actions can be considered by the Android policy.', 'Bu sürümde komut kutusu yoktur. Android politikası yalnızca imzalı, sürümlenmiş yerel eylemleri değerlendirebilir.')}</p></div><Icon name="shield" /></div>
    <div className="settings-callout" role="status"><Icon name={enabled ? 'shield' : 'core'} /><div><strong>{status}</strong><p>{enabled ? t('Actions remain in the app sandbox. Network, raw shell commands, root, Termux and Shizuku are not enabled.', 'Eylemler uygulama sandbox alanında kalır. Ağ, ham kabuk komutları, root, Termux ve Shizuku etkin değildir.') : t('Execution is fail-closed. No action reaches an executor.', 'Çalıştırma güvenli biçimde reddedilir. Hiçbir eylem çalıştırıcıya ulaşmaz.')}</p></div></div>
    <div className="terminal-panel__details">
      <p><strong>{t('Confirmation', 'Onay')}</strong> {t('A sensitive allowlisted action requires an explicit Android confirmation and is recorded in the audit log.', 'Hassas izinli bir eylem açık Android onayı ister ve denetim günlüğüne kaydedilir.')}</p>
      <p><strong>{t('Boundary', 'Sınır')}</strong> {t('SAF document locations are not command paths. Unknown actions, schemas and fields are rejected.', 'SAF belge konumları komut yolu değildir. Bilinmeyen eylemler, şemalar ve alanlar reddedilir.')}</p>
    </div>
  </section>
}
