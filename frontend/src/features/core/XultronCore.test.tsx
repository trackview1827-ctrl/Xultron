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
})
