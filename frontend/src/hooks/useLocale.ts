import { useCallback } from 'react'
import { useApp } from '../stores/AppContext'

export function useLocale() {
  const { settings } = useApp()
  const locale = settings.locale === 'tr' ? 'tr' : 'en'
  const t = useCallback((english: string, turkish: string) => locale === 'tr' ? turkish : english, [locale])
  return { locale, isTurkish: locale === 'tr', t }
}
