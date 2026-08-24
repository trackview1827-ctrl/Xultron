import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import type { Conversation, Message, Provider } from '../../types'
import { chatApi } from '../../services/chatApi'
import { providersApi } from '../../services/providersApi'
import { ApiError } from '../../services/apiClient'
import { useApp } from '../../stores/AppContext'
import { useVoice } from '../../hooks/useVoice'
import { XultronCore } from '../core/XultronCore'
import { Icon } from '../../components/Icon'
import { Button, Spinner } from '../../components/ui'

function id(): string { return crypto.randomUUID?.() ?? `${Date.now()}-${Math.random()}` }
function normalizeProviderList(data: { providers: Provider[] } | Provider[]): Provider[] { return Array.isArray(data) ? data : data.providers }

export function HomePage() {
  const { coreState, dispatchCore, settings, online, setPage } = useApp(); const [messages, setMessages] = useState<Message[]>([]); const [conversations, setConversations] = useState<Conversation[]>([])
  const [conversationId, setConversationId] = useState<string>(); const [input, setInput] = useState(''); const [aiReady, setAiReady] = useState<boolean | null>(null)
  const [sttReady, setSttReady] = useState(false); const [ttsReady, setTtsReady] = useState(false); const [error, setError] = useState(''); const [streaming, setStreaming] = useState(false); const [historyOpen, setHistoryOpen] = useState(false)
  const abortRef = useRef<AbortController | null>(null); const timelineRef = useRef<HTMLDivElement | null>(null)
  const voice = useVoice(text => { setInput(text); requestAnimationFrame(() => document.querySelector<HTMLTextAreaElement>('#command-input')?.focus()) })
  const loadSystem = async () => { try { const [providers, history] = await Promise.all([providersApi.list(), chatApi.conversations(settings.lowDataMode ? 6 : 20)]); const list = normalizeProviderList(providers); setAiReady(list.some(item => item.kind === 'ai' && item.enabled)); setSttReady(list.some(item => item.kind === 'stt' && item.enabled)); setTtsReady(list.some(item => item.kind === 'tts' && item.enabled)); setConversations(history.conversations) } catch { setAiReady(null) } }
  useEffect(() => { if (online) void loadSystem(); else setAiReady(null) }, [online, settings.lowDataMode])
  useEffect(() => { timelineRef.current?.scrollTo({ top: timelineRef.current.scrollHeight, behavior: settings.reducedMotion ? 'auto' : 'smooth' }) }, [messages, settings.reducedMotion])
  const selectConversation = async (conversation: Conversation) => { setHistoryOpen(false); setConversationId(conversation.id); setError(''); try { const result = await chatApi.messages(conversation.id, settings.lowDataMode ? 20 : 50); setMessages(result.messages) } catch (caught) { setError(caught instanceof Error ? caught.message : 'Conversation could not be loaded.') } }
  const newConversation = () => { abortRef.current?.abort(); setConversationId(undefined); setMessages([]); setError(''); setHistoryOpen(false) }
  const send = async () => {
    const text = input.trim(); if (!text || streaming) return; if (!online) { setError('Xultron is offline. Reconnect before sending.'); dispatchCore({ type: 'NETWORK_LOST' }); return }
    if (aiReady === false) { setError('No AI provider is configured.'); return }
    const requestId = id(); const userMessage: Message = { id: `local-${requestId}`, conversationId: conversationId ?? '', role: 'user', content: text, createdAt: new Date().toISOString() }
    const assistantId = `stream-${requestId}`; setMessages(current => [...current, userMessage, { id: assistantId, conversationId: conversationId ?? '', role: 'assistant', content: '', createdAt: new Date().toISOString(), pending: true }]); setInput(''); setError(''); setStreaming(true); dispatchCore({ type: 'THINK' })
    const controller = new AbortController(); abortRef.current = controller; let streamError = ''
    try { await chatApi.stream({ conversationId, message: text, requestId }, {
      onState: state => { if (state.toLowerCase() === 'thinking') dispatchCore({ type: 'THINK' }) },
      onConversation: conversation => { setConversationId(conversation.id); setConversations(current => current.some(item => item.id === conversation.id) ? current : [conversation, ...current]) },
      onDelta: delta => setMessages(current => current.map(item => item.id === assistantId ? { ...item, content: item.content + delta } : item)),
      onDone: message => setMessages(current => current.map(item => item.id === assistantId ? { ...(message?.id ? message : item), content: message?.content || item.content, pending: false } : item)),
      onError: message => { streamError = message; throw new ApiError(message) },
    }, controller.signal) } catch (caught) {
      if (!(caught instanceof DOMException && caught.name === 'AbortError')) { const message = streamError || (caught instanceof Error ? caught.message : 'Response interrupted.'); setError(message); setMessages(current => current.map(item => item.id === assistantId ? { ...item, pending: false, failed: true, content: item.content || 'Response interrupted before output was received.' } : item)); dispatchCore({ type: 'FAIL' }) }
    } finally { setStreaming(false); abortRef.current = null; dispatchCore({ type: online ? 'COMPLETE' : 'NETWORK_LOST' }) }
  }
  const stop = () => { abortRef.current?.abort(); setStreaming(false); dispatchCore({ type: 'COMPLETE' }) }
  const coreCompact = messages.length > 0
  return <div className="home-page">
    <aside className={`conversation-ledger ${historyOpen ? 'open' : ''}`} aria-label="Conversation history"><div className="ledger-head"><span>CONVERSATION LOG</span><button onClick={() => setHistoryOpen(false)} aria-label="Close history"><Icon name="close" /></button></div><button className="new-thread" onClick={newConversation}><Icon name="plus" /> NEW THREAD</button><div className="ledger-list">{conversations.map(item => <button key={item.id} className={item.id === conversationId ? 'active' : ''} onClick={() => void selectConversation(item)}><span>{item.title || 'Untitled sequence'}</span><small>{new Date(item.updatedAt).toLocaleDateString()}</small></button>)}{!conversations.length && <p>No previous sequences.</p>}</div></aside>
    {historyOpen && <button className="scrim" aria-label="Close history" onClick={() => setHistoryOpen(false)} />}
    <section className="command-space">
      <div className="home-tools"><button className="icon-button history-trigger" onClick={() => setHistoryOpen(true)} aria-label="Open conversation history"><span className="history-lines" /></button><span className="section-index">CORE INTERFACE / 01</span><button className="icon-button" onClick={newConversation} aria-label="New conversation"><Icon name="plus" /></button></div>
      <motion.div layout className={`core-stage ${coreCompact ? 'compact' : ''}`}><XultronCore state={coreState} reducedMotion={settings.reducedMotion || settings.lowDataMode} compact={coreCompact} level={voice.level} />{!coreCompact && <motion.div className="core-intro" initial={{ opacity: 0 }} animate={{ opacity: 1 }}><h1>How can I assist you?</h1><p>Voice, thought, and memory aligned.</p></motion.div>}</motion.div>
      <div className="timeline" ref={timelineRef} aria-live="polite">
        <AnimatePresence initial={false}>{messages.map((message, index) => <motion.article key={message.id} className={`transmission ${message.role} ${message.failed ? 'failed' : ''}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <header><span>{message.role === 'assistant' ? 'XULTRON' : 'YOU'}</span><span>{String(index + 1).padStart(2, '0')} / {new Date(message.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span></header><div className="transmission-line" /><p>{message.content}{message.pending && <span className="cursor" />}</p>{message.role === 'assistant' && !message.pending && message.content && ttsReady && <button className="speak-action" onClick={() => void voice.speak(message.content)}><Icon name="voice" /> PLAY VOICE</button>}
        </motion.article>)}</AnimatePresence>
      </div>
      {(aiReady === false || (!online && messages.length === 0)) && <div className="system-notice"><span className="notice-code">{!online ? 'LINK / 00' : 'PROVIDER / 00'}</span><div><strong>{!online ? 'Connection unavailable' : 'No AI provider configured'}</strong><p>{!online ? 'The interface remains available. AI actions resume after reconnection.' : 'Connect an intelligence provider to activate conversations.'}</p></div>{online && <Button variant="secondary" onClick={() => setPage('settings')}>CONFIGURE PROVIDER</Button>}</div>}
      {(error || voice.error) && <div className="command-error" role="alert"><span>{error || voice.error}</span><button onClick={() => { setError(''); voice.clearError() }} aria-label="Dismiss error"><Icon name="close" /></button></div>}
      <div className="command-dock"><div className="input-line"><textarea id="command-input" rows={1} value={input} onChange={event => setInput(event.target.value.slice(0, 12000))} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send() } }} placeholder={online ? 'Ask Xultron…' : 'Reconnect to transmit…'} aria-label="Message Xultron" disabled={!online || streaming} /><span className="char-count">{input.length > 10000 ? `${input.length}/12000` : ''}</span></div><div className="dock-actions"><button className={`voice-button ${voice.recording ? 'recording' : ''}`} onClick={() => voice.recording ? voice.stop() : void voice.start()} disabled={!online || !sttReady || streaming} aria-label={voice.recording ? 'Stop recording' : sttReady ? 'Start voice input' : 'Configure an STT provider first'}>{voice.recording ? <Icon name="stop" /> : <Icon name="mic" />}</button>{streaming ? <button className="send-button stop" onClick={stop} aria-label="Stop response"><Icon name="stop" /></button> : <button className="send-button" onClick={() => void send()} disabled={!input.trim() || !online} aria-label="Send message">{aiReady === null ? <Spinner /> : <Icon name="send" />}</button>}</div></div>
    </section>
  </div>
}
