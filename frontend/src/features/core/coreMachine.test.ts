import { describe, expect, it } from 'vitest'
import { coreReducer } from './coreMachine'

describe('Xultron Core state machine', () => {
  it('follows the guarded boot and operation path', () => {
    let state = coreReducer('BOOTING', { type: 'BOOT_COMPLETE' }); expect(state).toBe('CONNECTING')
    state = coreReducer(state, { type: 'CONNECTED' }); expect(state).toBe('ONLINE')
    state = coreReducer(state, { type: 'LISTEN' }); expect(state).toBe('LISTENING')
    state = coreReducer(state, { type: 'THINK' }); expect(state).toBe('THINKING')
    state = coreReducer(state, { type: 'SPEAK' }); expect(state).toBe('SPEAKING')
    state = coreReducer(state, { type: 'COMPLETE' }); expect(state).toBe('ONLINE')
  })
  it('rejects impossible transitions', () => {
    expect(coreReducer('OFFLINE', { type: 'SPEAK' })).toBe('OFFLINE')
    expect(coreReducer('BOOTING', { type: 'LISTEN' })).toBe('BOOTING')
    expect(coreReducer('THINKING', { type: 'LISTEN' })).toBe('THINKING')
  })
  it('gives network loss precedence and recovers through connecting', () => {
    expect(coreReducer('SPEAKING', { type: 'NETWORK_LOST' })).toBe('OFFLINE')
    expect(coreReducer('OFFLINE', { type: 'NETWORK_FOUND' })).toBe('CONNECTING')
    expect(coreReducer('ERROR', { type: 'RETRY' })).toBe('CONNECTING')
  })
})
