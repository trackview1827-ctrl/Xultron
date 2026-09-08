import { afterEach, describe, expect, it, vi } from 'vitest'
import { nativeVoiceServiceBridge } from './nativeVoiceBridge'

class FakePort extends EventTarget {
  posted: string[] = []
  postMessage(message: string) { this.posted.push(message) }
  reply(payload: unknown) { this.dispatchEvent(new MessageEvent('message', { data: JSON.stringify(payload) })) }
}

afterEach(() => { delete window.XultronVoicePort })

describe('nativeVoiceServiceBridge', () => {
  it('is absent outside an Android origin-bound WebMessage port', () => {
    expect(nativeVoiceServiceBridge()).toBeUndefined()
  })

  it('sends only a fixed versioned status request and accepts its matching reply', async () => {
    const port = new FakePort()
    window.XultronVoicePort = port
    const bridge = nativeVoiceServiceBridge()!
    const pending = bridge.getStatus()
    const request = JSON.parse(port.posted[0]!) as { v: number; id: string; action: string }
    expect(request.v).toBe(1)
    expect(request.action).toBe('voice.status')
    port.reply({ id: request.id, status: { state: 'STOPPED', detail: 'Stopped.', diagnostic: { cloudSttEnabled: false, rawAudioUploadEnabled: false, pollingEnabled: false, persistentWebSocketEnabled: false, rawAudioPersisted: false } } })
    await expect(pending).resolves.toMatchObject({ state: 'STOPPED' })
  })

  it('does not resolve an unrelated native message', async () => {
    const port = new FakePort()
    window.XultronVoicePort = port
    const bridge = nativeVoiceServiceBridge()!
    const pending = bridge.start()
    const request = JSON.parse(port.posted[0]!) as { id: string }
    port.reply({ id: 'voice-unrelated999', status: {} })
    await Promise.resolve()
    const settle = vi.fn()
    void pending.then(settle, settle)
    expect(settle).not.toHaveBeenCalled()
    port.reply({ id: request.id, error: 'blocked' })
    await expect(pending).rejects.toThrow('blocked')
  })
})
