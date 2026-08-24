import { apiBlob, apiRequest } from './apiClient'

export const voiceApi = {
  transcribe: async (audio: Blob, language?: string, providerId?: string, signal?: AbortSignal): Promise<{ text: string; language: string }> => {
    const form = new FormData(); form.append('audio', audio, `xultron-${Date.now()}.webm`)
    if (language && language !== 'auto') form.append('language', language); if (providerId) form.append('providerId', providerId)
    return apiRequest('/voice/transcribe', { method: 'POST', body: form, signal })
  },
  synthesize: (text: string, providerId?: string, voice?: string, signal?: AbortSignal) => apiBlob('/voice/synthesize', { text, providerId, voice }, signal),
}
