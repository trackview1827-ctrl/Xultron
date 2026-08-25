import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AmbientBackdrop } from './AmbientBackdrop'

describe('AmbientBackdrop', () => {
  it('is decorative and exposes the animated obsidian background layers', () => {
    const { container } = render(<AmbientBackdrop />)
    const backdrop = container.querySelector('.ambient-backdrop')
    expect(backdrop).toHaveAttribute('aria-hidden', 'true')
    expect(container.querySelectorAll('.ambient-orb')).toHaveLength(3)
    expect(container.querySelectorAll('.ambient-ripple')).toHaveLength(2)
    expect(container.querySelector('.ambient-glass-wave')).toBeInTheDocument()
  })
})
