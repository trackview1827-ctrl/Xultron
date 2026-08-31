import { beforeEach, describe, expect, it, vi } from 'vitest'
import { voiceApi } from './voiceApi'

describe('voice upload format', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ text: 'ok', language: 'tr' }), { status: 200, headers: { 'Content-Type': 'application/json' } })))
  })

  it('uses an m4a filename when Android WebView records MP4 audio', async () => {
    await voiceApi.transcribe(new Blob(['audio'], { type: 'audio/mp4' }), 'tr')
    const init = vi.mocked(fetch).mock.calls[0]![1]!
    const audio = (init.body as FormData).get('audio') as File
    expect(audio.name).toMatch(/\.m4a$/)
    expect(audio.type).toBe('audio/mp4')
  })

  it('keeps WebM recordings as webm', async () => {
    await voiceApi.transcribe(new Blob(['audio'], { type: 'audio/webm;codecs=opus' }))
    const init = vi.mocked(fetch).mock.calls[0]![1]!
    const audio = (init.body as FormData).get('audio') as File
    expect(audio.name).toMatch(/\.webm$/)
  })
})
