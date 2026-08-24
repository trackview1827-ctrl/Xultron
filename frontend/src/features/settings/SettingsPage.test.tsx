import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DEFAULT_SETTINGS } from '../../services/settingsApi'
import { DevicesPanel, SettingsPage } from './SettingsPage'

const app = vi.hoisted(() => ({
  updateSettings: vi.fn(),
  value: {} as Record<string, unknown>,
}))
const settings = vi.hoisted(() => ({ devices: vi.fn() }))
vi.mock('../../stores/AppContext', () => ({ useApp: () => app.value }))
vi.mock('../../services/settingsApi', async importOriginal => {
  const actual = await importOriginal<typeof import('../../services/settingsApi')>()
  return { ...actual, settingsApi: { ...actual.settingsApi, devices: settings.devices } }
})

describe('settings behavior', () => {
  beforeEach(() => {
    app.updateSettings.mockResolvedValue(undefined)
    app.value = {
      online: true,
      settings: { ...DEFAULT_SETTINGS },
      updateSettings: app.updateSettings,
      user: { id: 'u1', username: 'operator', email: null, isGuest: false, createdAt: '2026-08-24T00:00:00Z' },
      setUser: vi.fn(),
    }
    settings.devices.mockResolvedValue({ devices: [] })
  })

  it('offers Turkish and saves preferred voice only on explicit apply', async () => {
    const user = userEvent.setup()
    render(<SettingsPage />)
    expect(screen.getByRole('option', { name: 'Türkçe' })).toHaveValue('tr')
    await user.click(screen.getByRole('button', { name: /Voice/ }))
    const input = screen.getByLabelText(/Preferred voice/)
    await user.type(input, 'nova')
    expect(app.updateSettings).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'APPLY VOICE' }))
    expect(app.updateSettings).toHaveBeenCalledTimes(1)
    expect(app.updateSettings).toHaveBeenCalledWith({ preferredVoice: 'nova' })
  })

  it('renders translated navigation and content for Turkish locale', () => {
    app.value = { ...app.value, settings: { ...DEFAULT_SETTINGS, locale: 'tr' } }
    render(<SettingsPage />)
    expect(screen.getByRole('heading', { name: 'Sistemler' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Genel' })).toBeInTheDocument()
    expect(screen.getByLabelText('Arayüz dili')).toHaveValue('tr')
    expect(screen.getByRole('navigation', { name: 'Ayar kategorileri' })).toBeInTheDocument()
  })

  it('renders the backend deviceType field visibly', async () => {
    settings.devices.mockResolvedValue({ devices: [{ id: 'd1', name: 'Workshop Pi', deviceType: 'raspberry_pi', status: 'offline', metadata: {}, createdAt: '2026-08-24T00:00:00Z', updatedAt: '2026-08-24T00:00:00Z' }] })
    render(<DevicesPanel online />)
    expect(await screen.findByText(/raspberry_pi · offline/)).toBeInTheDocument()
    await waitFor(() => expect(settings.devices).toHaveBeenCalledTimes(1))
  })
})
