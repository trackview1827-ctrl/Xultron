import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AppProvider } from '../../stores/AppContext'
import { AuthGateway } from './AuthGateway'

const auth = vi.hoisted(() => ({ session: vi.fn(), guest: vi.fn(), register: vi.fn(), login: vi.fn(), logout: vi.fn(), sessions: vi.fn(), revokeSession: vi.fn() }))
vi.mock('../../services/authApi', () => ({ authApi: auth }))
const guest = { id: 'g1', username: 'guest-7', email: '', isGuest: true, createdAt: new Date().toISOString() }

describe('authentication critical flows', () => {
  beforeEach(() => {
    auth.session.mockResolvedValue({ user: null, csrfToken: 'csrf', expiresAt: null })
    auth.guest.mockResolvedValue({ user: guest, csrfToken: 'csrf', expiresAt: null })
    auth.login.mockResolvedValue({ user: { ...guest, isGuest: false, username: 'operator' } })
  })

  it('enters an isolated guest session from the Turkish gateway', async () => {
    const user = userEvent.setup()
    render(<AppProvider><AuthGateway /></AppProvider>)
    await screen.findByRole('heading', { name: /Hoş geldin/ })
    await user.click(screen.getByRole('button', { name: 'MİSAFİR OLARAK DEVAM ET' }))
    await waitFor(() => expect(auth.guest).toHaveBeenCalledTimes(1))
  })

  it('submits the username and password created by the CLI', async () => {
    const user = userEvent.setup()
    render(<AppProvider><AuthGateway /></AppProvider>)
    await user.type(await screen.findByLabelText('KULLANICI ADI'), 'operator')
    await user.type(screen.getByLabelText('PAROLA'), 'correct horse battery staple')
    await user.click(screen.getByRole('button', { name: 'SİSTEME GİR' }))
    await waitFor(() => expect(auth.login).toHaveBeenCalledWith({ identifier: 'operator', password: 'correct horse battery staple' }))
  })

  it('keeps submission disabled until both credentials are present', async () => {
    const user = userEvent.setup()
    render(<AppProvider><AuthGateway /></AppProvider>)
    const submit = await screen.findByRole('button', { name: 'SİSTEME GİR' })
    expect(submit).toBeDisabled()
    await user.type(screen.getByLabelText('KULLANICI ADI'), 'operator')
    expect(submit).toBeDisabled()
    expect(auth.login).not.toHaveBeenCalled()
  })
})
