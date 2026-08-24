import type { CoreState } from '../../types'

export type CoreEvent =
  | { type: 'BOOT_COMPLETE' } | { type: 'NETWORK_LOST' } | { type: 'NETWORK_FOUND' }
  | { type: 'CONNECTED' } | { type: 'LISTEN' } | { type: 'THINK' } | { type: 'SPEAK' }
  | { type: 'COMPLETE' } | { type: 'FAIL' } | { type: 'RETRY' }

const transitions: Record<CoreState, Partial<Record<CoreEvent['type'], CoreState>>> = {
  BOOTING: { BOOT_COMPLETE: 'CONNECTING', NETWORK_LOST: 'OFFLINE', FAIL: 'ERROR' },
  OFFLINE: { NETWORK_FOUND: 'CONNECTING' },
  CONNECTING: { CONNECTED: 'ONLINE', NETWORK_LOST: 'OFFLINE', FAIL: 'ERROR' },
  ONLINE: { NETWORK_LOST: 'OFFLINE', LISTEN: 'LISTENING', THINK: 'THINKING', SPEAK: 'SPEAKING', FAIL: 'ERROR' },
  LISTENING: { NETWORK_LOST: 'OFFLINE', THINK: 'THINKING', COMPLETE: 'ONLINE', FAIL: 'ERROR' },
  THINKING: { NETWORK_LOST: 'OFFLINE', SPEAK: 'SPEAKING', COMPLETE: 'ONLINE', FAIL: 'ERROR' },
  SPEAKING: { NETWORK_LOST: 'OFFLINE', COMPLETE: 'ONLINE', FAIL: 'ERROR' },
  ERROR: { NETWORK_LOST: 'OFFLINE', RETRY: 'CONNECTING', COMPLETE: 'ONLINE' },
}

export function coreReducer(state: CoreState, event: CoreEvent): CoreState {
  if (event.type === 'NETWORK_LOST') return 'OFFLINE'
  return transitions[state][event.type] ?? state
}

export function coreLabel(state: CoreState): string {
  const labels: Record<CoreState, string> = {
    BOOTING: 'INITIALIZING XULTRON', OFFLINE: 'NETWORK OFFLINE', CONNECTING: 'ESTABLISHING LINK', ONLINE: 'SYSTEM ONLINE',
    LISTENING: 'LISTENING', THINKING: 'PROCESSING', SPEAKING: 'SPEAKING', ERROR: 'SYSTEM INTERRUPT',
  }
  return labels[state]
}
