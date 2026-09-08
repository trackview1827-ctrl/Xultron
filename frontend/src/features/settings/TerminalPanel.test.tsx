import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { TerminalPanel } from './TerminalPanel'

const app = vi.hoisted(() => ({ value: { settings: { locale: 'tr' } } }))
vi.mock('../../stores/AppContext', () => ({ useApp: () => app.value }))

describe('TerminalPanel', () => {
  it('shows Turkish fail-closed status without a command or execute control', () => {
    render(<TerminalPanel availability="disabled" />)
    expect(screen.getByRole('heading', { name: 'Terminal güvenliği' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('TERMİNAL DEVRE DIŞI')
    expect(screen.getByText(/Çalıştırma güvenli biçimde reddedilir/)).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('explains sandbox limits and confirmation when ready', () => {
    render(<TerminalPanel />)
    expect(screen.getByRole('status')).toHaveTextContent('UYGULAMA SANDBOX POLİTİKASI ETKİN')
    expect(screen.getByText(/açık Android onayı ister/i)).toBeInTheDocument()
    expect(screen.getByText(/SAF belge konumları komut yolu değildir/i)).toBeInTheDocument()
  })
})
