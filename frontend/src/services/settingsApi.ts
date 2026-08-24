import { apiRequest } from './apiClient'
import type { AppSettings, Device } from '../types'

export const DEFAULT_SETTINGS: AppSettings = {
  locale: 'en', lowDataMode: false, memoryEnabled: true, conversationHistory: true, voiceHistory: false,
  saveAudio: false, analytics: false, reducedMotion: false, preferredVoice: '', sttLanguage: 'auto',
  theme: 'dark', accent: 'cyan', textScale: 'standard',
}

export const settingsApi = {
  get: () => apiRequest<{ settings: AppSettings }>('/settings'),
  update: (settings: Partial<AppSettings>) => apiRequest<{ settings: AppSettings }>('/settings', { method: 'PATCH', body: JSON.stringify(settings) }),
  devices: () => apiRequest<{ devices: Device[] }>('/devices'),
}
