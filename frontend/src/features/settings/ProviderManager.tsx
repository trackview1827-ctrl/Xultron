import { useEffect, useRef, useState, type FormEvent, type RefObject } from 'react'
import type { ModelOption, Provider, ProviderInput, ProviderKind } from '../../types'
import { providersApi } from '../../services/providersApi'
import { Icon } from '../../components/Icon'
import { Button, EmptyState, Field, Input, Spinner, Switch } from '../../components/ui'
import { ConfirmDialog } from '../../components/ConfirmDialog'

const labels: Record<ProviderKind, { title: string; copy: string }> = {
  ai: { title: 'AI Providers', copy: 'Intelligence engines for reasoning and conversation.' },
  stt: { title: 'STT Providers', copy: 'Speech recognition links for voice input.' },
  tts: { title: 'TTS Providers', copy: 'Voice synthesis engines for spoken output.' },
}

function blank(kind: ProviderKind): ProviderInput {
  return { name: '', kind, adapter: 'openai_compatible', baseUrl: '', apiKey: '', model: '', temperature: .3, maxTokens: 800, streaming: kind === 'ai', enabled: true, isDefault: false, config: {} }
}

function providerToInput(provider: Provider): ProviderInput {
  return {
    name: provider.name,
    kind: provider.kind,
    adapter: provider.adapter,
    baseUrl: provider.baseUrl ?? '',
    model: provider.model ?? '',
    temperature: provider.temperature ?? undefined,
    maxTokens: provider.maxTokens ?? undefined,
    streaming: provider.streaming,
    enabled: provider.enabled,
    isDefault: provider.isDefault,
    config: provider.config,
  }
}

export function ProviderManager({ kind, online }: { kind: ProviderKind; online: boolean }) {
  const [providers, setProviders] = useState<Provider[]>([])
  const [editing, setEditing] = useState<Provider | 'new' | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Provider | null>(null)
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')
  const addButtonRef = useRef<HTMLButtonElement>(null)
  const deleteButtonRef = useRef<HTMLButtonElement>(null)
  const loadGenerationRef = useRef(0)

  useEffect(() => {
    const generation = ++loadGenerationRef.current
    setProviders([]); setEditing(null); setDeleteTarget(null); setError('')
    if (!online) { setLoading(false); return }
    setLoading(true)
    void providersApi.list(kind).then(result => { if (generation === loadGenerationRef.current) setProviders(result.providers) }).catch(caught => { if (generation === loadGenerationRef.current) setError(caught instanceof Error ? caught.message : 'Provider registry is unavailable.') }).finally(() => { if (generation === loadGenerationRef.current) setLoading(false) })
    return () => { loadGenerationRef.current += 1 }
  }, [kind, online])

  const quickUpdate = async (provider: Provider, patch: Partial<ProviderInput>) => {
    if (!online) return
    try {
      const result = await providersApi.update(provider.id, { ...providerToInput(provider), ...patch })
      setProviders(current => current.map(item => item.id === provider.id ? result.provider : patch.isDefault ? { ...item, isDefault: false } : item))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Provider could not be updated.')
    }
  }

  const remove = async () => {
    if (!deleteTarget || !online) return
    setDeleting(true)
    try {
      await providersApi.remove(deleteTarget.id)
      setProviders(current => current.filter(item => item.id !== deleteTarget.id))
      setEditing(null)
      setDeleteTarget(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Provider could not be deleted.')
    } finally {
      setDeleting(false)
    }
  }

  return <div className="provider-manager">
    <div className="settings-section-head">
      <div><h2>{labels[kind].title}</h2><p>{labels[kind].copy}</p></div>
      <Button ref={addButtonRef} onClick={() => setEditing('new')} disabled={!online}><Icon name="plus" /> ADD PROVIDER</Button>
    </div>
    {error && <div className="command-error" role="alert">{error}</div>}
    {loading ? <div className="center-loader"><Spinner /></div> : !providers.length
      ? <EmptyState title={`No ${kind.toUpperCase()} provider configured`} description={`Xultron remains stable without one. Add a provider when you are ready to activate ${kind === 'ai' ? 'conversation' : kind === 'stt' ? 'voice input' : 'spoken output'}.`} action={online ? <Button variant="secondary" onClick={() => setEditing('new')}>CONFIGURE PROVIDER</Button> : undefined} />
      : <div className="provider-list">{providers.map(provider => <article className="provider-row" key={provider.id}>
        <button className="provider-main" onClick={() => setEditing(provider)} aria-disabled={!online}>
          <span className={`provider-pulse ${provider.enabled ? 'enabled' : ''}`} />
          <span><strong>{provider.name}</strong><small>{provider.model || 'Model not selected'} · {provider.credential.configured ? provider.credential.masked || 'Stored credential' : 'No credential'}</small></span>
          {provider.isDefault && <em>DEFAULT</em>}<Icon name="edit" />
        </button>
        <div className="provider-actions"><Switch label="Enabled" checked={provider.enabled} disabled={!online} onChange={value => void quickUpdate(provider, { enabled: value })} /><button className={provider.isDefault ? 'default active' : 'default'} disabled={!online || provider.isDefault || !provider.enabled} onClick={() => void quickUpdate(provider, { isDefault: true })}>{provider.isDefault ? 'ACTIVE DEFAULT' : 'SET DEFAULT'}</button></div>
      </article>)}</div>}
    {editing && <ProviderEditor kind={kind} online={online} confirmationOpen={deleteTarget !== null} deleteButtonRef={deleteButtonRef} provider={editing === 'new' ? undefined : editing} onClose={() => setEditing(null)} onSaved={saved => {
      setProviders(current => {
        const without = current.filter(item => item.id !== saved.id).map(item => saved.isDefault ? { ...item, isDefault: false } : item)
        return [saved, ...without]
      })
      setEditing(null)
    }} onDelete={provider => setDeleteTarget(provider)} />}
    <ConfirmDialog open={deleteTarget !== null} title={deleteTarget ? `Delete “${deleteTarget.name}”?` : 'Delete provider?'} description="The provider and its stored server-side credential will be permanently removed. Other Xultron surfaces will remain available." confirmLabel="DELETE PROVIDER" busy={deleting} onCancel={() => setDeleteTarget(null)} onConfirm={() => void remove()} fallbackFocusRef={addButtonRef} />
  </div>
}

function ProviderEditor({ kind, online, provider, confirmationOpen, deleteButtonRef, onClose, onSaved, onDelete }: { kind: ProviderKind; online: boolean; provider?: Provider; confirmationOpen: boolean; deleteButtonRef: RefObject<HTMLButtonElement | null>; onClose: () => void; onSaved: (provider: Provider) => void; onDelete: (provider: Provider) => void }) {
  const [form, setForm] = useState<ProviderInput>(() => provider ? providerToInput(provider) : blank(kind))
  const [models, setModels] = useState<ModelOption[]>([])
  const [busy, setBusy] = useState('')
  const [status, setStatus] = useState<{ ok: boolean; message: string } | null>(null)
  const [error, setError] = useState('')
  const panelRef = useRef<HTMLDivElement>(null); const returnFocusRef = useRef<HTMLElement | null>(null); const onCloseRef = useRef(onClose); const confirmationOpenRef = useRef(confirmationOpen); onCloseRef.current = onClose; confirmationOpenRef.current = confirmationOpen
  const update = <K extends keyof ProviderInput>(key: K, value: ProviderInput[K]) => setForm(current => ({ ...current, [key]: value }))

  useEffect(() => {
    returnFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { if (confirmationOpenRef.current) return; event.preventDefault(); onCloseRef.current(); return }
      if (event.key !== 'Tab') return
      const focusable = [...(panelRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])') ?? [])]
      if (!focusable.length) return
      const first = focusable[0]!; const last = focusable[focusable.length - 1]!
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => { document.removeEventListener('keydown', onKeyDown); window.setTimeout(() => returnFocusRef.current?.isConnected && returnFocusRef.current.focus(), 0) }
  }, [])

  const save = async (event?: FormEvent): Promise<Provider | undefined> => {
    event?.preventDefault()
    if (!online) { setError('Reconnect before changing provider settings.'); return }
    if (!form.name.trim() || !form.baseUrl.trim()) { setError('Name and base URL are required.'); return }
    setBusy('save'); setError('')
    try {
      const result = provider ? await providersApi.update(provider.id, form) : await providersApi.create(form)
      update('apiKey', '')
      onSaved(result.provider)
      return result.provider
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Provider could not be saved.')
    } finally {
      setBusy('')
    }
  }

  const test = async () => {
    if (!online) { setError('Reconnect before testing this provider.'); return }
    if (!provider) { setError('Save this provider before testing its connection.'); return }
    setBusy('test'); setStatus(null)
    try {
      const result = await providersApi.test(provider.id)
      setStatus({ ok: result.ok, message: `${result.message}${result.latencyMs ? ` · ${result.latencyMs} ms` : ''}` })
    } catch (caught) {
      setStatus({ ok: false, message: caught instanceof Error ? caught.message : 'Connection test failed.' })
    } finally {
      setBusy('')
    }
  }

  const refreshModels = async () => {
    if (!online) { setError('Reconnect before refreshing models.'); return }
    if (!provider) { setError('Save this provider before refreshing models.'); return }
    setBusy('models')
    try {
      const result = await providersApi.models(provider.id)
      setModels(result.models)
      setStatus({ ok: true, message: `${result.models.length} models discovered.` })
    } catch (caught) {
      setStatus({ ok: false, message: caught instanceof Error ? caught.message : 'Models could not be refreshed.' })
    } finally {
      setBusy('')
    }
  }

  return <div className="modal-layer"><div ref={panelRef} className="modal-panel provider-editor" role="dialog" aria-modal="true" aria-labelledby="provider-title">
    <header><div><span className="section-index">{kind.toUpperCase()} LINK CONFIGURATION</span><h2 id="provider-title">{provider ? provider.name : 'New provider'}</h2></div><button className="icon-button" onClick={onClose} aria-label="Close provider editor"><Icon name="close" /></button></header>
    <form onSubmit={event => void save(event)} autoComplete="off"><fieldset className="provider-editor-fields" disabled={!online}>
      <div className="form-grid">
        <Field label="Provider name"><Input value={form.name} onChange={event => update('name', event.target.value)} required autoFocus /></Field>
        <Field label="Adapter"><select className="field" value={form.adapter} onChange={event => update('adapter', event.target.value)}><option value="openai_compatible">OpenAI compatible</option><option value="custom_http">Custom HTTP</option><option value="local_http">Local endpoint</option></select></Field>
        <Field label="Base URL" hint="Credentials are sent only to Xultron's backend."><Input value={form.baseUrl} onChange={event => update('baseUrl', event.target.value)} type="url" placeholder="https://api.example.com/v1" required /></Field>
        <Field label="API key" hint={provider?.credential.configured ? `Stored securely: ${provider.credential.masked || 'masked credential'}. Leave blank to keep it.` : 'Never saved in browser storage.'}><Input value={form.apiKey ?? ''} onChange={event => update('apiKey', event.target.value)} type="password" placeholder={provider?.credential.configured ? 'Leave blank to keep existing key' : 'Enter secret once'} autoComplete="new-password" /></Field>
        <Field label="Model ID" hint="Enter manually or use model discovery."><div className="compound-field"><Input value={form.model} onChange={event => update('model', event.target.value)} list="provider-models" /><button type="button" onClick={() => void refreshModels()} disabled={!!busy} aria-label="Refresh models"><Icon name="refresh" /></button></div><datalist id="provider-models">{models.map(model => <option value={model.id} key={model.id}>{model.label}</option>)}</datalist></Field>
        {kind === 'ai' && <><Field label="Temperature"><Input value={form.temperature ?? .3} onChange={event => update('temperature', Number(event.target.value))} type="number" min="0" max="2" step="0.1" /></Field><Field label="Max output tokens"><Input value={form.maxTokens ?? 800} onChange={event => update('maxTokens', Number(event.target.value))} type="number" min="1" max="32000" /></Field></>}
        {kind === 'stt' && <Field label="Language override"><Input value={String(form.config.language ?? '')} onChange={event => update('config', { ...form.config, language: event.target.value })} placeholder="auto" /></Field>}
        {kind === 'tts' && <><Field label="Voice"><Input value={String(form.config.voice ?? '')} onChange={event => update('config', { ...form.config, voice: event.target.value })} /></Field><Field label="Speed"><Input type="number" min="0.5" max="2" step="0.1" value={Number(form.config.speed ?? 1)} onChange={event => update('config', { ...form.config, speed: Number(event.target.value) })} /></Field></>}
      </div>
      <div className="toggle-group"><Switch label="Enabled" description="Allow Xultron to use this provider." checked={form.enabled} onChange={value => update('enabled', value)} /><Switch label="Default provider" description="Prefer this link for new operations." checked={form.isDefault} onChange={value => update('isDefault', value)} />{kind === 'ai' && <Switch label="Streaming" description="Receive response output progressively." checked={form.streaming ?? true} onChange={value => update('streaming', value)} />}</div>
      {status && <div className={`test-status ${status.ok ? 'success' : 'failure'}`} role="status"><Icon name={status.ok ? 'check' : 'close'} />{status.message}</div>}
      {error && <div className="inline-error" role="alert">{error}</div>}
      {provider && <small className="saved-config-note">Connection tests use the last saved server configuration. Save edits before testing them.</small>}
      <div className="provider-form-actions">{provider && <Button ref={deleteButtonRef} type="button" variant="danger" onClick={() => onDelete(provider)}><Icon name="trash" /> DELETE</Button>}<span /><Button type="button" variant="secondary" onClick={() => void test()} disabled={!!busy}>{busy === 'test' ? <Spinner /> : 'TEST SAVED CONFIG'}</Button><Button type="submit" disabled={!!busy}>{busy === 'save' ? <Spinner /> : 'SAVE PROVIDER'}</Button></div>
    </fieldset></form>
  </div></div>
}
