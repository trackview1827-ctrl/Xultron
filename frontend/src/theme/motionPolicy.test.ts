import { describe, expect, it } from 'vitest'
import { conservesMotion, timelineScrollBehavior } from './motionPolicy'

describe('motion policy', () => {
  it('disables JavaScript motion and smooth scrolling in Low Data Mode', () => {
    const settings = { reducedMotion: false, lowDataMode: true }
    expect(conservesMotion(settings)).toBe(true)
    expect(timelineScrollBehavior(settings)).toBe('auto')
  })

  it('preserves smooth timeline movement only when conservation is off', () => {
    expect(timelineScrollBehavior({ reducedMotion: false, lowDataMode: false })).toBe('smooth')
    expect(timelineScrollBehavior({ reducedMotion: true, lowDataMode: false })).toBe('auto')
  })
})
