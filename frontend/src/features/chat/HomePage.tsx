import { AnimatePresence, motion } from 'framer-motion'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { Conversation, Message, Provider } from '../../types'
import { chatApi } from '../../services/chatApi'
import { providersApi } from '../../services/providersApi'
import { ApiError } from '../../services/apiClient'
import { useApp } from '../../stores/AppContext'
import { useVoice } from '../../hooks/useVoice'
import { XultronCore } from '../core/XultronCore'
import { Icon } from '../../components/Icon'
import { Button, Spinner } from '../../components/ui'
import { conservesMotion, timelineScrollBehavior } from '../../theme/motionPolicy'
import { useLocale } from '../../hooks/useLocale'

function id(): string { return crypto.randomUUID?.() ?? `${Date.now()}-${Math.random()}` }
function normalizeProviderList(data: { providers: Provider[] } | Provider[]): Provider[] { return Array.isArray(data) ? data : data.providers }

export function HomePage() {
  const context = useApp(); const [fallbackMessages, setFallbackMessages] = useState<Message[]>([]); const [fallbackInput, setFallbackInput] = useState(''); const [fallbackConversationId, setFallbackConversationId] = useState<string>();
  const { coreState, dispatchCore, settings, online, networkOnline, setPage } = context; const conversationId = context.activeConversationId ?? fallbackConversationId; const setConversationId = context.setActiveConversationId ?? setFallbackConversationId; const messages = context.activeMessages ?? fallbackMessages; const setMessages = context.setActiveMessages ?? setFallbackMessages; const input = context.activeDraft ?? fallbackInput; const setInput = context.setActiveDraft ?? setFallbackInput; const setActiveConversation = context.setActiveConversation ?? (() => undefined); const [conversations, setConversations] = useState<Conversation[]>([])
  const { t, locale } = useLocale()
  const [aiReady, setAiReady] = useState<boolean | null>(null)
  const [sttReady, setSttReady] = useState(false); const [ttsReady, setTtsReady] = useState(false); const [error, setError] = useState(''); const [streaming, setStreaming] = useState(false); const [historyOpen, setHistoryOpen] = useState(false)
  const abortRef = useRef<AbortController | null>(null); const historyAbortRef = useRef<AbortController | null>(null); const timelineRef = useRef<HTMLDivElement | null>(null); const activeResponseRef = useRef<{ requestId: string; assistantId: string; stopped: boolean } | null>(null); const systemLoadGenerationRef = useRef(0); const selectionGenerationRef = useRef(0); const liveConversationRef = useRef(false)
  const [liveConversation, setLiveConversation] = useState(false); const [liveTranscript, setLiveTranscript] = useState(''); const [liveRetry, setLiveRetry] = useState(0)
  const handleVoiceTranscript = useCallback((text: string) => {
    if (liveConversationRef.current) { setLiveTranscript(text); return }
    setInput(text); requestAnimationFrame(() => document.querySelector<HTMLTextAreaElement>('#command-input')?.focus())
  }, [setInput])
  const handleVoiceNoSpeech = useCallback(() => { if (liveConversationRef.current) setLiveRetry(value => value + 1) }, [])
  const voice = useVoice(handleVoiceTranscript, handleVoiceNoSpeech)
  const conserveMotion = conservesMotion(settings)
  useEffect(() => {
    const generation = ++systemLoadGenerationRef.current
    if (!online) { setAiReady(null); setSttReady(false); setTtsReady(false); return }
    void Promise.all([providersApi.list(), chatApi.conversations(settings.lowDataMode ? 6 : 20)]).then(([providers, history]) => {
      if (generation !== systemLoadGenerationRef.current) return
      const list = normalizeProviderList(providers)
      setAiReady(list.some(item => item.kind === 'ai' && item.enabled)); setSttReady(list.some(item => item.kind === 'stt' && item.enabled)); setTtsReady(list.some(item => item.kind === 'tts' && item.enabled)); setConversations(history.conversations)
    }).catch(() => { if (generation === systemLoadGenerationRef.current) { setAiReady(null); setSttReady(false); setTtsReady(false) } })
    return () => { systemLoadGenerationRef.current += 1 }
  }, [online, settings.lowDataMode])
  useEffect(() => { timelineRef.current?.scrollTo({ top: timelineRef.current.scrollHeight, behavior: timelineScrollBehavior(settings) }) }, [messages, conserveMotion])
  const cancelActiveResponse = (preservePartial: boolean, dispatchState = true) => {
    const active = activeResponseRef.current
    if (!active) return
    active.stopped = true
    abortRef.current?.abort()
    if (preservePartial) setMessages(current => current.flatMap(item => item.id !== active.assistantId ? [item] : item.content ? [{ ...item, pending: false, cancelled: true }] : []))
    setStreaming(false)
    if (dispatchState) dispatchCore({ type: online ? 'CANCEL' : 'NETWORK_LOST' })
  }
  const stopLiveConversation = () => {
    liveConversationRef.current = false; setLiveConversation(false); setLiveTranscript(''); setLiveRetry(0); voice.stop(); voice.stopSpeaking(); cancelActiveResponse(true)
  }
  useEffect(() => () => { historyAbortRef.current?.abort(); const active = activeResponseRef.current; if (active) { active.stopped = true; abortRef.current?.abort(); dispatchCore({ type: 'CANCEL' }) } }, [dispatchCore])
  const selectConversation = async (conversation: Conversation) => {
    cancelActiveResponse(false); historyAbortRef.current?.abort(); const generation = ++selectionGenerationRef.current; const controller = new AbortController(); historyAbortRef.current = controller
    setHistoryOpen(false); setConversationId(conversation.id); setActiveConversation(conversation); setMessages([]); setError('')
    try { const result = await chatApi.messages(conversation.id, settings.lowDataMode ? 20 : 50, undefined, controller.signal); if (generation === selectionGenerationRef.current) setMessages(result.messages) }
    catch (caught) { if (!(caught instanceof DOMException && caught.name === 'AbortError') && generation === selectionGenerationRef.current) setError(caught instanceof Error ? caught.message : 'Conversation could not be loaded.') }
    finally { if (generation === selectionGenerationRef.current) historyAbortRef.current = null }
  }
  const newConversation = () => { cancelActiveResponse(false); selectionGenerationRef.current += 1; historyAbortRef.current?.abort(); historyAbortRef.current = null; setConversationId(undefined); setActiveConversation(undefined); setMessages([]); setError(''); setHistoryOpen(false) }
  const send = async (overrideText?: string, liveTurn = false) => {
    const text = (overrideText ?? input).trim(); if (!text || streaming) return; if (!online) { setError(networkOnline ? t('The Xultron backend is unavailable. Retry the link before sending.', 'Xultron backend kullanılamıyor. Göndermeden önce bağlantıyı yenile.') : t('Xultron is offline. Reconnect before sending.', 'Xultron çevrimdışı. Göndermeden önce yeniden bağlan.')); if (!networkOnline) dispatchCore({ type: 'NETWORK_LOST' }); if (liveTurn) stopLiveConversation(); return }
    if (aiReady !== true) { setError(t('No AI provider is configured.', 'AI sağlayıcısı yapılandırılmadı.')); if (liveTurn) stopLiveConversation(); return }
    const requestId = id(); const userMessage: Message = { id: `local-${requestId}`, conversationId: conversationId ?? '', role: 'user', content: text, createdAt: new Date().toISOString() }
    const assistantId = `stream-${requestId}`; setMessages(current => [...current, userMessage, { id: assistantId, conversationId: conversationId ?? '', role: 'assistant', content: '', createdAt: new Date().toISOString(), pending: true }]); setInput(''); setError(''); setStreaming(true)
    if (coreState === 'ERROR') dispatchCore({ type: 'RECOVER' })
    dispatchCore({ type: 'THINK' })
    const controller = new AbortController(); abortRef.current = controller; activeResponseRef.current = { requestId, assistantId, stopped: false }; let streamError = ''; let failed = false; let assistantOutput = ''
    const acceptsStreamEvent = () => activeResponseRef.current?.requestId === requestId && !activeResponseRef.current.stopped
    try { await chatApi.stream({ conversationId, message: text, requestId }, {
      onState: state => { if (acceptsStreamEvent() && state.toLowerCase() === 'thinking') dispatchCore({ type: 'THINK' }) },
      onConversation: conversation => { if (!acceptsStreamEvent()) return; setConversationId(conversation.id); setConversations(current => [conversation, ...current.filter(item => item.id !== conversation.id)]) },
      onDelta: delta => { if (acceptsStreamEvent()) { assistantOutput += delta; setMessages(current => current.map(item => item.id === assistantId ? { ...item, content: item.content + delta } : item)) } },
      onDone: message => { if (acceptsStreamEvent()) { assistantOutput = message?.content || assistantOutput; setMessages(current => current.map(item => item.id === assistantId ? { ...(message?.id ? message : item), content: message?.content || item.content, pending: false } : item)) } },
      onError: message => { if (!acceptsStreamEvent()) return; streamError = message; throw new ApiError(message) },
    }, controller.signal) } catch (caught) {
      if (!(caught instanceof DOMException && caught.name === 'AbortError')) { failed = true; const message = streamError || (caught instanceof Error ? caught.message : 'Response interrupted.'); setError(message); setMessages(current => current.map(item => item.id === assistantId ? { ...item, pending: false, failed: true, content: item.content || 'Response interrupted before output was received.' } : item)); dispatchCore({ type: 'FAIL' }) }
    } finally {
      if (activeResponseRef.current?.requestId === requestId) {
        const stopped = activeResponseRef.current.stopped
        setStreaming(false); abortRef.current = null; activeResponseRef.current = null
        if (!failed && !stopped) dispatchCore({ type: online ? 'COMPLETE' : 'NETWORK_LOST' })
        if (liveTurn && !failed && !stopped && liveConversationRef.current) {
          if (assistantOutput.trim()) await voice.speak(assistantOutput.trim())
          if (liveConversationRef.current) {
            const started = await voice.start({ autoStopSilenceMs: 900 })
            if (!started && liveConversationRef.current) stopLiveConversation()
          }
        }
      }
    }
  }
  const stop = () => {
    cancelActiveResponse(true)
  }
  const startLiveConversation = async () => {
    if (liveConversationRef.current) return
    if (!online || !sttReady || !ttsReady || aiReady !== true) {
      setError(t('Configure AI, STT, and TTS providers before starting live voice.', 'Canlı sesi başlatmadan önce AI, STT ve TTS sağlayıcılarını yapılandır.'))
      return
    }
    setError(''); setLiveRetry(0); liveConversationRef.current = true; setLiveConversation(true)
    const started = await voice.start({ autoStopSilenceMs: 900 })
    if (!started && liveConversationRef.current) stopLiveConversation()
  }
  useEffect(() => {
    if (!liveConversation || !liveTranscript) return
    const text = liveTranscript; setLiveTranscript(''); void send(text, true)
  }, [liveConversation, liveTranscript])
  useEffect(() => {
    if (!liveConversation || !liveRetry) return
    void voice.start({ autoStopSilenceMs: 900 })
  }, [liveConversation, liveRetry])
  useEffect(() => {
    if (!online && liveConversation) stopLiveConversation()
  }, [liveConversation, online])
  const coreCompact = messages.length > 0
  return <div className="home-page">
    <aside className={`conversation-ledger ${historyOpen ? 'open' : ''}`} aria-label={t('Conversation history', 'Sohbet geçmişi')}><div className="ledger-head"><span>{t('CONVERSATION LOG', 'SOHBET KAYDI')}</span><button onClick={() => setHistoryOpen(false)} aria-label={t('Close history', 'Geçmişi kapat')}><Icon name="close" /></button></div><button className="new-thread" onClick={newConversation}><Icon name="plus" /> {t('NEW THREAD', 'YENİ SOHBET')}</button><div className="ledger-list">{conversations.map(item => <button key={item.id} className={item.id === conversationId ? 'active' : ''} onClick={() => void selectConversation(item)}><span>{item.title || t('Untitled sequence', 'Adsız sohbet')}</span><small>{new Date(item.updatedAt).toLocaleDateString(locale)}</small></button>)}{!conversations.length && <p>{t('No previous sequences.', 'Önceki sohbet yok.')}</p>}</div></aside>
    {historyOpen && <button className="scrim" aria-label={t('Close history', 'Geçmişi kapat')} onClick={() => setHistoryOpen(false)} />}
    <section className="command-space">
      <div className="home-tools"><button className="icon-button history-trigger" onClick={() => setHistoryOpen(true)} aria-label={t('Open conversation history', 'Sohbet geçmişini aç')}><span className="history-lines" /></button><span className="section-index">{t('CORE INTERFACE / 01', 'ÇEKİRDEK ARAYÜZÜ / 01')}</span><button className="icon-button" onClick={newConversation} aria-label={t('New conversation', 'Yeni sohbet')}><Icon name="plus" /></button></div>
      <motion.div layout={!conserveMotion} transition={{ duration: conserveMotion ? 0 : .3 }} className={`core-stage ${coreCompact ? 'compact' : ''}`}><XultronCore state={coreState} reducedMotion={conserveMotion} compact={coreCompact} level={voice.level} />{!coreCompact && <motion.div className="core-intro" initial={conserveMotion ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: conserveMotion ? 0 : .32 }}><h1>{t('How can I assist you?', 'Sana nasıl yardımcı olabilirim?')}</h1><p>{t('Voice, thought, and memory aligned.', 'Ses, düşünce ve hafıza birlikte çalışır.')}</p></motion.div>}</motion.div>
      <div className="timeline" ref={timelineRef} aria-live="polite">
        <AnimatePresence initial={false}>{messages.map((message, index) => <motion.article key={message.id} className={`transmission ${message.role} ${message.failed ? 'failed' : ''} ${message.cancelled ? 'cancelled' : ''}`} initial={conserveMotion ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: conserveMotion ? 0 : .18 }}>
          <header><span>{message.role === 'assistant' ? 'XULTRON' : t('YOU', 'SEN')}</span><span>{message.cancelled ? t('STOPPED · ', 'DURDU · ') : ''}{String(index + 1).padStart(2, '0')} / {new Date(message.createdAt).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })}</span></header><div className="transmission-line" /><p>{message.content}{message.pending && <span className="cursor" />}</p>{message.role === 'assistant' && !message.pending && message.content && ttsReady && <button className="speak-action" onClick={() => voice.speaking ? voice.stopSpeaking() : void voice.speak(message.content)}><Icon name={voice.speaking ? 'stop' : 'voice'} /> {voice.speaking ? t('STOP VOICE', 'SESİ DURDUR') : t('PLAY VOICE', 'SESLENDİR')}</button>}
        </motion.article>)}</AnimatePresence>
      </div>
      {(aiReady === false || (!online && messages.length === 0)) && <div className="system-notice"><span className="notice-code">{!online ? 'LINK / 00' : 'PROVIDER / 00'}</span><div><strong>{!online ? 'Connection unavailable' : 'No AI provider configured'}</strong><p>{!online ? 'The interface remains available. AI actions resume after reconnection.' : 'Connect an intelligence provider to activate conversations.'}</p></div>{online && <Button variant="secondary" onClick={() => setPage('settings')}>CONFIGURE PROVIDER</Button>}</div>}
      {(error || voice.error) && <div className="command-error" role="alert"><span>{error || voice.error}</span><button onClick={() => { setError(''); voice.clearError() }} aria-label="Dismiss error"><Icon name="close" /></button></div>}
      <div className="command-dock"><div className="input-line"><textarea id="command-input" rows={1} value={input} maxLength={8000} onChange={event => setInput(event.target.value.slice(0, 8000))} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send() } }} placeholder={online ? t('Ask Xultron…', 'Xultron’a sor…') : t('Reconnect to transmit…', 'Göndermek için yeniden bağlan…')} aria-label={t('Message Xultron', 'Xultron’a mesaj gönder')} disabled={!online || streaming || liveConversation} /><span className="char-count">{input.length > 7000 ? `${input.length}/8000` : ''}</span></div><div className="dock-actions"><button className={`live-voice-button ${liveConversation ? 'active' : ''}`} onClick={() => liveConversation ? stopLiveConversation() : void startLiveConversation()} disabled={liveConversation ? false : !online || !sttReady || !ttsReady || aiReady !== true} aria-pressed={liveConversation} aria-label={liveConversation ? t('Stop live conversation', 'Anlık konuşmayı durdur') : t('Start live conversation', 'Anlık konuşmayı başlat')}><span className="live-waveform" aria-hidden="true"><span /><span /><span /><span /><span /></span></button><button className={`voice-button ${voice.recording ? 'recording' : ''}`} onClick={() => voice.recording ? voice.stop() : void voice.start()} disabled={!online || !sttReady || streaming || liveConversation} aria-label={voice.recording ? t('Stop recording', 'Kaydı durdur') : sttReady ? t('Start voice input', 'Sesli girişi başlat') : t('Configure an STT provider first', 'Önce bir STT sağlayıcısı yapılandır')} >{voice.recording ? <Icon name="stop" /> : <Icon name="mic" />}</button>{streaming ? <button className="send-button stop" onClick={stop} aria-label={t('Stop response', 'Yanıtı durdur')}><Icon name="stop" /></button> : <button className="send-button" onClick={() => void send()} disabled={!input.trim() || !online || liveConversation} aria-label={t('Send message', 'Mesaj gönder')}>{aiReady === null ? <Spinner /> : <Icon name="send" />}</button>}</div></div>
    </section>
  </div>
}
