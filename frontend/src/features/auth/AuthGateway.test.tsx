import { fireEvent, render, screen, waitFor } from '@testing-library/react'
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
    auth.login.mockResolvedValue({ user: { ...guest, isGuest: false, username: 'local-user' } })
  })

  it('enters an isolated guest session from the Turkish gateway', async () => {
    const user = userEvent.setup()
    render(<AppProvider><AuthGateway /></AppProvider>)
    await screen.findByRole('heading', { name: /Hoş geldin/ })
    await user.click(screen.getByRole('button', { name: 'MİSAFİR OLARAK DEVAM ET' }))
    await waitFor(() => expect(auth.guest).toHaveBeenCalledTimes(1))
  })

  it('submits the fixed identity with exactly four PIN digits', async () => {
    const user = userEvent.setup()
    render(<AppProvider><AuthGateway /></AppProvider>)
    expect(await screen.findByDisplayValue('local-user')).toHaveAttribute('readonly')
    for (const [index, digit] of ['1', '3', '2', '4'].entries()) await user.type(screen.getByLabelText(`PIN hanesi ${index + 1}`), digit)
    await user.click(screen.getByRole('button', { name: 'SİSTEME GİR' }))
    await waitFor(() => expect(auth.login).toHaveBeenCalledWith({ identifier: 'local-user', password: '2468' }))
  })

  it('ignores non-numeric PIN input and keeps submission disabled', async () => {
    render(<AppProvider><AuthGateway /></AppProvider>)
    const first = await screen.findByLabelText('PIN hanesi 1')
    fireEvent.change(first, { target: { value: 'x' } })
    expect(first).toHaveValue('')
    expect(screen.getByRole('button', { name: 'SİSTEME GİR' })).toBeDisabled()
    expect(auth.login).not.toHaveBeenCalled()
  })
})
