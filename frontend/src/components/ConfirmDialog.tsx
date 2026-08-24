import { useEffect, useId, useRef, type RefObject } from 'react'
import { Button } from './ui'

interface ConfirmDialogProps {
  open: boolean
  title: string
  description: string
  confirmLabel: string
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
  fallbackFocusRef?: RefObject<HTMLElement | null>
}

export function ConfirmDialog({ open, title, description, confirmLabel, busy = false, onConfirm, onCancel, fallbackFocusRef }: ConfirmDialogProps) {
  const titleId = useId()
  const descriptionId = useId()
  const cancelRef = useRef<HTMLButtonElement>(null)
  const returnFocusRef = useRef<HTMLElement | null>(null)
  const busyRef = useRef(busy)
  const onCancelRef = useRef(onCancel)
  const fallbackFocusRefValue = useRef(fallbackFocusRef)
  busyRef.current = busy
  onCancelRef.current = onCancel
  fallbackFocusRefValue.current = fallbackFocusRef

  useEffect(() => {
    if (!open) return
    returnFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const focusTimer = window.setTimeout(() => cancelRef.current?.focus(), 0)
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busyRef.current) {
        event.preventDefault()
        onCancelRef.current()
        return
      }
      if (event.key !== 'Tab') return
      const panel = cancelRef.current?.closest<HTMLElement>('[role="dialog"]')
      const focusable = [...(panel?.querySelectorAll<HTMLElement>('button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])') ?? [])]
      if (!focusable.length) return
      const first = focusable[0]!
      const last = focusable[focusable.length - 1]!
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      window.clearTimeout(focusTimer)
      document.removeEventListener('keydown', onKeyDown)
      window.setTimeout(() => {
        const fallback = fallbackFocusRefValue.current?.current
        const target = returnFocusRef.current?.isConnected ? returnFocusRef.current : fallback?.isConnected ? fallback : null
        target?.focus()
      }, 0)
    }
  }, [open])

  if (!open) return null
  return <div className="modal-layer confirmation-layer" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget && !busy) onCancel() }}>
    <div className="modal-panel confirmation-panel" role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={descriptionId}>
      <span className="section-index">DESTRUCTIVE ACTION</span>
      <h2 id={titleId}>{title}</h2>
      <p id={descriptionId}>{description}</p>
      <div className="confirmation-actions">
        <Button ref={cancelRef} variant="secondary" onClick={onCancel} disabled={busy}>KEEP DATA</Button>
        <Button variant="danger" onClick={onConfirm} disabled={busy}>{busy ? 'REMOVING…' : confirmLabel}</Button>
      </div>
    </div>
  </div>
}
