import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AppProvider } from '../../stores/AppContext'
import { AuthGateway } from './AuthGateway'

const auth = vi.hoisted(() => ({ session: vi.fn(), guest: vi.fn(), register: vi.fn(), login: vi.fn(), logout: vi.fn(), sessions: vi.fn(), revokeSession: vi.fn() }))
vi.mock('../../services/authApi', () => ({ authApi: auth }))
const guest = { id: 'g1', username: 'guest-7', email: '', isGuest: true, createdAt: new Date().toISOString() }
describe('authentication critical flows', () => {
  beforeEach(() => { auth.session.mockResolvedValue({ user: null, csrfToken: 'csrf', expiresAt: null }); auth.guest.mockResolvedValue({ user: guest, csrfToken: 'csrf', expiresAt: null }); auth.login.mockResolvedValue({ user: { ...guest, isGuest: false, username: 'nova' } }) })
  it('enters an isolated guest session', async () => { const user = userEvent.setup(); render(<AppProvider><AuthGateway /></AppProvider>); await screen.findByRole('heading', { name: /Your intelligence/ }); await user.click(screen.getByRole('button', { name: 'CONTINUE AS GUEST' })); await waitFor(() => expect(auth.guest).toHaveBeenCalledTimes(1)) })
  it('validates and submits login credentials', async () => { const user = userEvent.setup(); render(<AppProvider><AuthGateway /></AppProvider>); await user.click(await screen.findByRole('button', { name: 'SIGN IN' })); await user.type(screen.getByLabelText('Username or email'), 'nova'); await user.type(screen.getByLabelText('Password'), 'correct-horse'); await user.click(screen.getByRole('button', { name: 'VERIFY IDENTITY' })); await waitFor(() => expect(auth.login).toHaveBeenCalledWith({ identifier: 'nova', password: 'correct-horse' })) })
  it('rejects a short registration password before network submission', async () => { const user = userEvent.setup(); render(<AppProvider><AuthGateway /></AppProvider>); await user.click(await screen.findByRole('button', { name: 'CREATE IDENTITY' })); await user.type(screen.getByLabelText('Username'), 'nova'); await user.type(screen.getByLabelText('Email'), 'nova@example.test'); await user.type(screen.getByLabelText(/Password/), 'short'); const form = screen.getByLabelText(/Password/).closest('form')!; fireEvent.submit(form); expect(await screen.findByRole('alert')).toHaveTextContent('at least 10 characters'); expect(auth.register).not.toHaveBeenCalled() })
})
