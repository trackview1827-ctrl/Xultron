import { forwardRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes } from 'react'

export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'danger' | 'ghost' }>(function Button({ variant = 'primary', className = '', children, ...props }, ref) {
  return <button ref={ref} className={`btn btn-${variant} ${className}`} {...props}>{children}</button>
})
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className = '', ...props }, ref) { return <input ref={ref} className={`field ${className}`} {...props} /> })
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className = '', ...props }, ref) { return <textarea ref={ref} className={`field resize-none ${className}`} {...props} /> })
export function Field({ label, hint, error, children }: { label: string; hint?: string; error?: string; children: ReactNode }) { return <label className="field-wrap"><span className="field-label">{label}</span>{children}{error && <span className="field-error" role="alert">{error}</span>}{hint && !error && <span className="field-hint">{hint}</span>}</label> }
export function Switch({ checked, onChange, label, description, disabled }: { checked: boolean; onChange: (value: boolean) => void; label: string; description?: string; disabled?: boolean }) { return <label className="switch-row"><span><strong>{label}</strong>{description && <small>{description}</small>}</span><input type="checkbox" checked={checked} onChange={event => onChange(event.target.checked)} disabled={disabled} /><span className="switch-track" aria-hidden="true"><span /></span></label> }
export function Spinner() { return <span className="spinner" aria-label="Loading" /> }
export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) { return <div className="empty-state"><span className="empty-glyph">⌁</span><h3>{title}</h3><p>{description}</p>{action}</div> }
