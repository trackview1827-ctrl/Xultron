import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { VoiceServiceControls, type NativeVoiceServiceBridge, type NativeVoiceServiceStatus } from './VoiceServiceControls'

const stopped: NativeVoiceServiceStatus = { state: 'STOPPED', detail: 'Stopped. No microphone is open.', diagnostic: { cloudSttEnabled: false, rawAudioUploadEnabled: false, pollingEnabled: false, persistentWebSocketEnabled: false, rawAudioPersisted: false } }
const active: NativeVoiceServiceStatus = { ...stopped, state: 'MONITORING_EXPERIMENTAL', detail: 'Experimental local monitoring active.' }

describe('VoiceServiceControls', () => {
  it('uses an honest browser fallback without requesting microphone access', () => {
    render(<VoiceServiceControls />)
    expect(screen.getByText(/unavailable in this browser/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /start local monitor/i })).not.toBeInTheDocument()
  })

  it('reads native state and sends only explicit start and stop commands', async () => {
    const bridge: NativeVoiceServiceBridge = { getStatus: vi.fn().mockResolvedValue(stopped), start: vi.fn().mockResolvedValue(active), stop: vi.fn().mockResolvedValue(stopped) }
    const user = userEvent.setup()
    render(<VoiceServiceControls bridge={bridge} />)
    const start = await screen.findByRole('button', { name: 'START LOCAL MONITOR' })
    await user.click(start)
    await waitFor(() => expect(bridge.start).toHaveBeenCalledTimes(1))
    expect(screen.getByRole('button', { name: 'STOP LOCAL MONITOR' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'STOP LOCAL MONITOR' }))
    await waitFor(() => expect(bridge.stop).toHaveBeenCalledTimes(1))
  })

  it('renders the native fail-closed block reason', async () => {
    const bridge: NativeVoiceServiceBridge = { getStatus: vi.fn().mockResolvedValue({ ...stopped, state: 'BLOCKED', blockReason: 'MICROPHONE_PERMISSION_MISSING' }), start: vi.fn(), stop: vi.fn() }
    render(<VoiceServiceControls bridge={bridge} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('MICROPHONE_PERMISSION_MISSING')
  })
})
