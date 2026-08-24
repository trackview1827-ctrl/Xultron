import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AppErrorBoundary } from './AppErrorBoundary'

let shouldFail = true
function UnstableSurface() {
  if (shouldFail) throw new Error('private-provider-secret')
  return <p>Interface restored.</p>
}

describe('AppErrorBoundary', () => {
  it('shows a safe recovery surface without leaking errors and can retry', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    shouldFail = true
    const user = userEvent.setup()
    render(<AppErrorBoundary><UnstableSurface /></AppErrorBoundary>)
    expect(await screen.findByRole('alert')).toHaveTextContent('Xultron paused safely.')
    expect(screen.queryByText(/private-provider-secret/)).not.toBeInTheDocument()

    shouldFail = false
    await user.click(screen.getByRole('button', { name: 'TRY INTERFACE AGAIN' }))
    expect(await screen.findByText('Interface restored.')).toBeInTheDocument()
  })
})
