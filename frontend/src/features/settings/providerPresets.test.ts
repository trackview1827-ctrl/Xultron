import { describe, expect, it } from 'vitest'
import { AI_PROVIDER_PRESETS } from './providerPresets'

describe('AI provider preset catalog', () => {
  it('contains a broad unique catalog with required providers', () => {
    const ids = AI_PROVIDER_PRESETS.map(preset => preset.id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(AI_PROVIDER_PRESETS.length).toBeGreaterThanOrEqual(30)
    expect(ids).toEqual(expect.arrayContaining(['google-gemini', 'anthropic', 'openai', 'xai', 'nvidia', 'huggingface', 'groq', 'openrouter', 'ollama']))
  })

  it('uses HTTPS for hosted providers and loopback HTTP only for local presets', () => {
    for (const preset of AI_PROVIDER_PRESETS) {
      if (preset.group === 'local') expect(preset.baseUrl).toMatch(/^http:\/\/127\.0\.0\.1:/)
      else expect(preset.baseUrl).toMatch(/^https:\/\//)
    }
  })

  it('maps native APIs to native adapters and the rest to compatible adapters', () => {
    expect(AI_PROVIDER_PRESETS.find(preset => preset.id === 'google-gemini')?.adapter).toBe('gemini')
    expect(AI_PROVIDER_PRESETS.find(preset => preset.id === 'anthropic')?.adapter).toBe('anthropic')
    expect(AI_PROVIDER_PRESETS.find(preset => preset.id === 'xai')?.adapter).toBe('openai_compatible')
  })
})
