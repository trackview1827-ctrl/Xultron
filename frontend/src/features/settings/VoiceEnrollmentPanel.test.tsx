import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { VoiceEnrollmentPanel } from './VoiceEnrollmentPanel'
import type { NativeVoiceEnrollmentBridge, NativeVoiceEnrollmentStatus } from '../../services/nativeVoiceBridge'

const collecting: NativeVoiceEnrollmentStatus = {
  state: 'COLLECTING', attempts: 0, acceptedAttempts: 0, requiredAttempts: 5,
  detail: 'Record one explicit local sample.',
}

describe('VoiceEnrollmentPanel', () => {
  it('has an honest browser fallback that exposes no recording control', () => {
    render(<VoiceEnrollmentPanel />)
    expect(screen.getByText(/unavailable in this browser/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /record local sample/i })).not.toBeInTheDocument()
  })

  it('keeps the practice phrase in the page and sends only an explicit native sample request', async () => {
    const bridge: NativeVoiceEnrollmentBridge = {
      getEnrollmentStatus: vi.fn().mockResolvedValue(collecting),
      captureEnrollmentSample: vi.fn().mockResolvedValue({ ...collecting, attempts: 1, acceptedAttempts: 1 }),
      clearEnrollment: vi.fn(),
    }
    const user = userEvent.setup()
    render(<VoiceEnrollmentPanel bridge={bridge} />)
    await screen.findByText(/accepted samples: 0/i)
    await user.type(screen.getByLabelText(/local practice phrase/i), 'Hey Xultron')
    await user.click(screen.getByRole('button', { name: /record local sample/i }))
    await waitFor(() => expect(bridge.captureEnrollmentSample).toHaveBeenCalledOnce())
    expect(screen.getByText(/accepted samples: 1/i)).toBeInTheDocument()
  })

  it('does not make a native microphone request until a local practice phrase is chosen', async () => {
    const bridge: NativeVoiceEnrollmentBridge = {
      getEnrollmentStatus: vi.fn().mockResolvedValue(collecting), captureEnrollmentSample: vi.fn(), clearEnrollment: vi.fn(),
    }
    const user = userEvent.setup()
    render(<VoiceEnrollmentPanel bridge={bridge} />)
    await screen.findByRole('button', { name: /record local sample/i })
    await user.click(screen.getByRole('button', { name: /record local sample/i }))
    expect(bridge.captureEnrollmentSample).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent(/not sent to Android or the backend/i)
  })
})
