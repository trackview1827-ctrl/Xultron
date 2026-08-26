import { apiRequest } from './apiClient'
import type { AppSettings, Device } from '../types'

export const DEFAULT_SETTINGS: AppSettings = {
  locale: 'en', lowDataMode: false, memoryEnabled: true, conversationHistory: true, voiceHistory: false,
  saveAudio: false, analytics: false, reducedMotion: false, preferredVoice: '', sttLanguage: 'auto', timeZone: 'UTC',
  theme: 'dark', accent: 'cyan', textScale: 'standard',
}

export const settingsApi = {
  get: (signal?: AbortSignal) => apiRequest<{ settings: AppSettings }>('/settings', { signal }),
  update: (settings: Partial<AppSettings>) => apiRequest<{ settings: AppSettings }>('/settings', { method: 'PATCH', body: JSON.stringify(settings) }),
  devices: () => apiRequest<{ devices: Device[] }>('/devices'),
}
