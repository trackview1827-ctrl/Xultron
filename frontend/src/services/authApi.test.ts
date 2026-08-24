import { beforeEach, describe, expect, it, vi } from 'vitest'
import { setCsrfToken } from './apiClient'
import { authApi } from './authApi'

const user = { id: 'u1', username: 'xultron-user', email: null, isGuest: true, createdAt: '2026-08-24T00:00:00Z' }
function json(data: unknown): Response { return new Response(JSON.stringify(data), { status: 200, headers: { 'Content-Type': 'application/json' } }) }

describe('auth CSRF rotation', () => {
  beforeEach(() => setCsrfToken('session-token'))

  it('uses each rotated anonymous or elevated token for the next identity mutation', async () => {
    const fetcher = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(json({ csrfToken: 'logout-token', expiresAt: '2026-08-25T00:00:00Z' }))
      .mockResolvedValueOnce(json({ user, csrfToken: 'guest-token', expiresAt: '2026-08-25T00:00:00Z' }))
      .mockResolvedValueOnce(json({ user: { ...user, isGuest: false }, csrfToken: 'register-token' }))

    await authApi.logout()
    await authApi.guest()
    await authApi.register({ username: 'xultron-user', email: 'user@example.test', password: 'long-password' })

    expect(new Headers(fetcher.mock.calls[0]![1]?.headers).get('X-CSRF-Token')).toBe('session-token')
    expect(new Headers(fetcher.mock.calls[1]![1]?.headers).get('X-CSRF-Token')).toBe('logout-token')
    expect(new Headers(fetcher.mock.calls[2]![1]?.headers).get('X-CSRF-Token')).toBe('guest-token')
  })
})
