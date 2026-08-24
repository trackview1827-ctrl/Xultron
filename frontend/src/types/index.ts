export type CoreState = 'BOOTING' | 'OFFLINE' | 'CONNECTING' | 'ONLINE' | 'LISTENING' | 'THINKING' | 'SPEAKING' | 'ERROR'
export type ProviderKind = 'ai' | 'stt' | 'tts'
export type MemoryCategory = 'personal' | 'preferences' | 'important' | 'temporary'

export interface ApiErrorBody { error: { code: string; message: string; retryable: boolean; requestId?: string } }
export interface User { id: string; username: string; email: string | null; isGuest: boolean; createdAt: string }
export interface SessionResponse { user: User | null; csrfToken: string; expiresAt: string | null }
export interface IdentityResponse { user: User; csrfToken: string; expiresAt?: string | null }
export interface LogoutResponse { ok: boolean; csrfToken: string }
export interface SessionDevice { id: string; current: boolean; createdAt: string; lastSeenAt: string; expiresAt: string }
export interface Conversation { id: string; title: string; createdAt: string; updatedAt: string }
export interface Message { id: string; conversationId: string; role: 'user' | 'assistant' | 'system'; content: string; createdAt: string; pending?: boolean; failed?: boolean; cancelled?: boolean }
export interface ProviderCredential { configured: boolean; masked: string | null }
export interface Provider {
  id: string; name: string; kind: ProviderKind; adapter: string; baseUrl: string | null; model: string | null;
  temperature: number | null; maxTokens: number | null; streaming: boolean; enabled: boolean; isDefault: boolean;
  credential: ProviderCredential; config: Record<string, unknown>; createdAt?: string; updatedAt?: string;
}
export interface ProviderInput {
  name: string; kind: ProviderKind; adapter: string; baseUrl: string; apiKey?: string; model: string;
  temperature?: number; maxTokens?: number; streaming?: boolean; enabled: boolean; isDefault: boolean; config: Record<string, unknown>;
}
export interface ModelOption { id: string; label: string }
export interface ProviderTest { ok: boolean; latencyMs: number; message: string }
export interface MemoryItem { id: string; title: string; content: string; category: MemoryCategory; createdAt: string; updatedAt: string }
export interface Device { id: string; name: string; deviceType: string; status: string; metadata: Record<string, unknown>; createdAt: string; updatedAt: string }
export interface AppSettings {
  locale: string; lowDataMode: boolean; memoryEnabled: boolean; conversationHistory: boolean; voiceHistory: boolean;
  saveAudio: boolean; analytics: boolean; reducedMotion: boolean; preferredVoice: string; sttLanguage: string;
  theme: 'dark' | 'darker'; accent: 'cyan' | 'violet'; textScale: 'compact' | 'standard' | 'large';
}
export interface DataUsage { downloaded: number; uploaded: number }
export type PageId = 'home' | 'memory' | 'settings'
