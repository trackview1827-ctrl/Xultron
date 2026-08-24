import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ProviderManager } from './ProviderManager'

const api = vi.hoisted(() => ({ list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn(), test: vi.fn(), models: vi.fn() }))
vi.mock('../../services/providersApi', () => ({ providersApi: api }))
const provider = { id: 'p1', name: 'Primary Mind', kind: 'ai', adapter: 'openai_compatible', baseUrl: 'https://example.test/v1', model: 'mind-1', temperature: .3, maxTokens: 800, streaming: true, enabled: true, isDefault: true, credential: { configured: true, masked: 'sk-••••91a2' }, config: {} }
describe('ProviderManager', () => {
  beforeEach(() => { api.list.mockResolvedValue({ providers: [] }); api.create.mockResolvedValue({ provider }); api.test.mockResolvedValue({ ok: true, latencyMs: 42, message: 'Connected' }); api.models.mockResolvedValue({ models: [{ id: 'mind-1', label: 'Mind One' }] }) })
  it('creates a provider and never persists its key in browser storage', async () => {
    const user = userEvent.setup(); render(<ProviderManager kind="ai" online />); await screen.findByText('No AI provider configured'); await user.click(screen.getByRole('button', { name: 'CONFIGURE PROVIDER' }))
    fireEvent.change(screen.getByLabelText('Provider name'), { target: { value: 'Primary Mind' } }); fireEvent.change(screen.getByPlaceholderText('https://api.example.com/v1'), { target: { value: 'https://example.test/v1' } }); fireEvent.change(screen.getByPlaceholderText('Enter secret once'), { target: { value: 'one-time-secret' } }); fireEvent.change(screen.getByRole('combobox', { name: /Model ID/ }), { target: { value: 'mind-1' } }); await user.click(screen.getByRole('button', { name: 'SAVE PROVIDER' }))
    await waitFor(() => expect(api.create).toHaveBeenCalled()); expect(api.create).toHaveBeenCalledWith(expect.objectContaining({ apiKey: 'one-time-secret' })); expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0)
  })
  it('supports connection testing and model discovery on saved providers', async () => {
    api.list.mockResolvedValue({ providers: [provider] }); const user = userEvent.setup(); render(<ProviderManager kind="ai" online />); await user.click(await screen.findByText('Primary Mind')); await user.click(screen.getByRole('button', { name: 'Refresh models' })); expect(await screen.findByText('1 models discovered.')).toBeInTheDocument(); await user.click(screen.getByRole('button', { name: 'TEST CONNECTION' })); expect(await screen.findByText(/Connected · 42 ms/)).toBeInTheDocument()
  })
  it('disables configuration while offline', async () => { render(<ProviderManager kind="stt" online={false} />); expect(await screen.findByRole('button', { name: /ADD PROVIDER/ })).toBeDisabled() })
})
