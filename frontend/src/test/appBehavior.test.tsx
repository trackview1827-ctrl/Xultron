import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AppProvider, useApp } from '../stores/AppContext'

const auth = vi.hoisted(() => ({ session: vi.fn() }))
const settingsApiMock = vi.hoisted(() => ({ get: vi.fn(), update: vi.fn(), devices: vi.fn() }))
vi.mock('../services/authApi', () => ({ authApi: auth }))
vi.mock('../services/settingsApi', async original => { const actual = await original<typeof import('../services/settingsApi')>(); return { ...actual, settingsApi: settingsApiMock } })
function Probe() { const { coreState, settings, updateSettings } = useApp(); return <div><span data-testid="core">{coreState}</span><span data-testid="low">{String(settings.lowDataMode)}</span><button onClick={() => void updateSettings({ lowDataMode: true, reducedMotion: true })}>conserve</button></div> }
describe('offline recovery and conservation behavior', () => {
  beforeEach(() => { Object.defineProperty(navigator, 'onLine', { configurable: true, value: true }); auth.session.mockResolvedValue({ user: { id: 'u1', username: 'nova', email: 'n@x.test', isGuest: false, createdAt: '' }, csrfToken: 'c', expiresAt: null }); settingsApiMock.get.mockResolvedValue({ settings: {} }); settingsApiMock.update.mockResolvedValue({ settings: { lowDataMode: true, reducedMotion: true } }) })
  it('completes the initial boot handshake', async () => { render(<AppProvider><Probe /></AppProvider>); await waitFor(() => expect(screen.getByTestId('core')).toHaveTextContent('ONLINE'), { timeout: 1800 }) })
  it('moves offline immediately and reconnects to online', async () => { render(<AppProvider><Probe /></AppProvider>); await waitFor(() => expect(screen.getByTestId('core')).toHaveTextContent(/CONNECTING|ONLINE/)); fireEvent(window, new Event('offline')); expect(screen.getByTestId('core')).toHaveTextContent('OFFLINE'); fireEvent(window, new Event('online')); await waitFor(() => expect(screen.getByTestId('core')).toHaveTextContent('ONLINE'), { timeout: 1200 }) })
  it('applies low-data and reduced-motion modes at the document boundary', async () => { render(<AppProvider><Probe /></AppProvider>); fireEvent.click(screen.getByText('conserve')); await waitFor(() => expect(document.documentElement.dataset.lowData).toBe('true')); expect(document.documentElement.dataset.reduceMotion).toBe('true'); expect(screen.getByTestId('low')).toHaveTextContent('true') })
})
