import { createRef, useRef, useState } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ConfirmDialog } from './ConfirmDialog'

function Harness({ onConfirm = vi.fn() }: { onConfirm?: () => void }) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  return <>
    <button ref={triggerRef} onClick={() => setOpen(true)}>CLEAR MEMORY</button>
    <button onClick={() => setBusy(value => !value)}>TOGGLE BUSY</button>
    <ConfirmDialog open={open} title="Clear memory?" description="This cannot be undone." confirmLabel="CLEAR ALL" busy={busy} onCancel={() => setOpen(false)} onConfirm={onConfirm} fallbackFocusRef={triggerRef} />
  </>
}

describe('ConfirmDialog', () => {
  it('traps focus, survives busy rerenders, closes with Escape, and restores trigger focus', async () => {
    const user = userEvent.setup()
    const triggerRef = createRef<HTMLButtonElement>(); const firstCancel = vi.fn(); const latestCancel = vi.fn()
    const view = render(<><button ref={triggerRef}>CLEAR MEMORY</button><ConfirmDialog open={false} title="Clear memory?" description="This cannot be undone." confirmLabel="CLEAR ALL" busy={false} onCancel={firstCancel} onConfirm={vi.fn()} fallbackFocusRef={triggerRef} /></>)
    const trigger = screen.getByRole('button', { name: 'CLEAR MEMORY' }); trigger.focus()
    view.rerender(<><button ref={triggerRef}>CLEAR MEMORY</button><ConfirmDialog open title="Clear memory?" description="This cannot be undone." confirmLabel="CLEAR ALL" busy={false} onCancel={firstCancel} onConfirm={vi.fn()} fallbackFocusRef={triggerRef} /></>)
    const keep = await screen.findByRole('button', { name: 'KEEP DATA' })
    await waitFor(() => expect(keep).toHaveFocus())

    view.rerender(<><button ref={triggerRef}>CLEAR MEMORY</button><ConfirmDialog open title="Clear memory?" description="This cannot be undone." confirmLabel="CLEAR ALL" busy onCancel={latestCancel} onConfirm={vi.fn()} fallbackFocusRef={triggerRef} /></>)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(trigger).not.toHaveFocus()
    await user.keyboard('{Escape}')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(latestCancel).not.toHaveBeenCalled()

    view.rerender(<><button ref={triggerRef}>CLEAR MEMORY</button><ConfirmDialog open title="Clear memory?" description="This cannot be undone." confirmLabel="CLEAR ALL" busy={false} onCancel={latestCancel} onConfirm={vi.fn()} fallbackFocusRef={triggerRef} /></>)
    await user.keyboard('{Escape}')
    expect(latestCancel).toHaveBeenCalledTimes(1)
    view.rerender(<><button ref={triggerRef}>CLEAR MEMORY</button><ConfirmDialog open={false} title="Clear memory?" description="This cannot be undone." confirmLabel="CLEAR ALL" busy={false} onCancel={latestCancel} onConfirm={vi.fn()} fallbackFocusRef={triggerRef} /></>)
    await waitFor(() => expect(trigger).toHaveFocus())
  })

  it('requires the explicit destructive action', async () => {
    const onConfirm = vi.fn()
    const user = userEvent.setup()
    render(<Harness onConfirm={onConfirm} />)
    await user.click(screen.getByRole('button', { name: 'CLEAR MEMORY' }))
    await user.click(await screen.findByRole('button', { name: 'CLEAR ALL' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })
})
