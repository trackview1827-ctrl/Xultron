import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { XultronCore } from './XultronCore'

describe('XultronCore', () => {
  it.each([['BOOTING', 'INITIALIZING XULTRON'], ['OFFLINE', 'NETWORK OFFLINE'], ['CONNECTING', 'ESTABLISHING LINK'], ['ONLINE', 'SYSTEM ONLINE'], ['LISTENING', 'LISTENING'], ['THINKING', 'PROCESSING'], ['SPEAKING', 'SPEAKING'], ['ERROR', 'SYSTEM INTERRUPT']] as const)('renders %s as a real visual state', (state, label) => {
    render(<XultronCore state={state} reducedMotion />)
    expect(screen.getByLabelText(`Xultron Core: ${label}`)).toHaveAttribute('data-state', state)
    expect(screen.getByText(label)).toBeInTheDocument()
  })
  it('remains understandable with animation disabled', () => { const { container } = render(<XultronCore state="THINKING" reducedMotion />); expect(container.querySelectorAll('svg').length).toBeGreaterThan(2) })
  it('renders three counter-rotating monochrome orbit layers around the liquid core', () => {
    const { container } = render(<XultronCore state="ONLINE" />)
    expect(container.querySelectorAll('.core-orbit-layer')).toHaveLength(3)
    expect(container.querySelector('.core-liquid-orb')).toBeInTheDocument()
    expect(container.querySelector('.core-field')).toHaveStyle({ '--core-status': '#f1f1f2' })
  })
  it('marks CSS-driven effects as reduced when motion is disabled', () => {
    const { container } = render(<XultronCore state="ONLINE" reducedMotion />)
    expect(container.querySelector('.x-core')).toHaveClass('motion-reduced')
  })
  it('selects the lighter motion profile on phone-sized viewports', () => {
    const originalWidth = window.innerWidth
    const originalMatchMedia = window.matchMedia
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 390 })
    Object.defineProperty(window, 'matchMedia', { configurable: true, value: () => ({ matches: true, addEventListener: () => {}, removeEventListener: () => {} }) as unknown as MediaQueryList })
    try {
      const { container } = render(<XultronCore state="ONLINE" />)
      expect(container.querySelector('.x-core')).toHaveAttribute('data-motion-profile', 'mobile')
    } finally {
      Object.defineProperty(window, 'innerWidth', { configurable: true, value: originalWidth })
      Object.defineProperty(window, 'matchMedia', { configurable: true, value: originalMatchMedia })
    }
  })
})
