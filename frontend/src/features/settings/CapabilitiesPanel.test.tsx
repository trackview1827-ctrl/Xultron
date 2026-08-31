import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { CapabilitiesPanel } from './CapabilitiesPanel'

const api = vi.hoisted(() => ({ tools: vi.fn() }))
const app = vi.hoisted(() => ({ value: { settings: { locale: 'en' } } }))
vi.mock('../../services/tasksApi', () => ({ tasksApi: api }))
vi.mock('../../stores/AppContext', () => ({ useApp: () => app.value }))

describe('capability boundary', () => {
  beforeEach(() => {
    api.tools.mockResolvedValue({ tools: [{ name: 'voice_transcribe', description: 'Transcribe audio', requiredPermissions: ['MICROPHONE'], sideEffect: false, riskLevel: 'low', available: true }] })
    Object.defineProperty(navigator, 'permissions', { configurable: true, value: undefined })
  })

  it('loads backend tools and keeps browser capabilities unavailable until tested', async () => {
    render(<CapabilitiesPanel online />)
    expect(await screen.findByText('voice_transcribe')).toBeInTheDocument()
    expect(screen.getAllByText('UNAVAILABLE')).toHaveLength(4)
    expect(screen.getByText(/Nothing is activated silently/i)).toBeInTheDocument()
  })

  it('requests microphone only after the explicit test action and releases the stream', async () => {
    const stop = vi.fn()
    const getUserMedia = vi.fn().mockResolvedValue({ getTracks: () => [{ stop }] })
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia } })
    const user = userEvent.setup()
    render(<CapabilitiesPanel online />)
    await user.click((await screen.findAllByRole('button', { name: 'TEST' }))[0]!)
    await waitFor(() => expect(getUserMedia).toHaveBeenCalledWith({ audio: true }))
    expect(stop).toHaveBeenCalledTimes(1)
  })
})
