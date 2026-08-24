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
  it('keeps ERROR observable until an explicit recovery action', () => {
    const failed = coreReducer('THINKING', { type: 'FAIL' })
    expect(failed).toBe('ERROR')
    expect(coreReducer(failed, { type: 'COMPLETE' })).toBe('ERROR')
    expect(coreReducer(failed, { type: 'LISTEN' })).toBe('ERROR')
    expect(coreReducer(failed, { type: 'RECOVER' })).toBe('ONLINE')
  })
  it('cancels active work without entering ERROR', () => {
    expect(coreReducer('THINKING', { type: 'CANCEL' })).toBe('ONLINE')
    expect(coreReducer('LISTENING', { type: 'CANCEL' })).toBe('ONLINE')
    expect(coreReducer('SPEAKING', { type: 'CANCEL' })).toBe('ONLINE')
  })
})
