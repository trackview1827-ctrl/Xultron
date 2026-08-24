import { useCallback, useEffect, useRef, useState } from 'react'
import { voiceApi } from '../services/voiceApi'
import { useApp } from '../stores/AppContext'

export function useVoice(onTranscript: (text: string) => void) {
  const { dispatchCore, settings, online } = useApp(); const recorderRef = useRef<MediaRecorder | null>(null); const streamRef = useRef<MediaStream | null>(null)
  const analyserFrame = useRef<number | null>(null); const audioContextRef = useRef<AudioContext | null>(null); const [recording, setRecording] = useState(false); const [level, setLevel] = useState(0); const [error, setError] = useState('')
  const stopTracks = () => { streamRef.current?.getTracks().forEach(track => track.stop()); streamRef.current = null; if (analyserFrame.current) cancelAnimationFrame(analyserFrame.current); analyserFrame.current = null; if (audioContextRef.current) void audioContextRef.current.close(); audioContextRef.current = null; setLevel(0) }
  useEffect(() => () => stopTracks(), [])
  const start = useCallback(async () => {
    setError(''); if (!online) { setError('Voice input needs a network connection.'); dispatchCore({ type: 'NETWORK_LOST' }); return }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') { setError('Microphone recording is not supported in this browser.'); return }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 } }); streamRef.current = stream
      const recorder = new MediaRecorder(stream, { mimeType: MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : undefined }); recorderRef.current = recorder
      const chunks: Blob[] = []; recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data) }
      recorder.onstop = async () => { setRecording(false); stopTracks(); if (!chunks.length) { setError('No audio was captured.'); dispatchCore({ type: 'COMPLETE' }); return }
        dispatchCore({ type: 'THINK' }); try { const result = await voiceApi.transcribe(new Blob(chunks, { type: recorder.mimeType }), settings.sttLanguage); onTranscript(result.text) } catch (caught) { setError(caught instanceof Error ? caught.message : 'Transcription failed.'); dispatchCore({ type: 'FAIL' }) } finally { dispatchCore({ type: 'COMPLETE' }) }
      }
      recorder.start(250); setRecording(true); dispatchCore({ type: 'LISTEN' })
      if (!settings.lowDataMode && !settings.reducedMotion) { const context = new AudioContext(); audioContextRef.current = context; const source = context.createMediaStreamSource(stream); const analyser = context.createAnalyser(); analyser.fftSize = 64; source.connect(analyser); const data = new Uint8Array(analyser.frequencyBinCount); const sample = () => { analyser.getByteFrequencyData(data); setLevel(data.reduce((a, b) => a + b, 0) / data.length / 255); analyserFrame.current = requestAnimationFrame(sample) }; sample() }
    } catch (caught) { setError(caught instanceof DOMException && caught.name === 'NotAllowedError' ? 'Microphone access was denied. Enable it in browser permissions.' : 'Xultron could not activate the microphone.'); dispatchCore({ type: 'FAIL' }); stopTracks() }
  }, [dispatchCore, onTranscript, online, settings.lowDataMode, settings.reducedMotion, settings.sttLanguage])
  const stop = useCallback(() => { if (recorderRef.current?.state === 'recording') recorderRef.current.stop() }, [])
  const speak = useCallback(async (text: string) => { setError(''); if (!online) { setError('Speech output needs a network connection.'); return }
    dispatchCore({ type: 'SPEAK' }); try { const blob = await voiceApi.synthesize(text, undefined, settings.preferredVoice || undefined); const url = URL.createObjectURL(blob); const audio = new Audio(url); await new Promise<void>((resolve, reject) => { audio.onended = () => resolve(); audio.onerror = () => reject(new Error('Audio playback failed.')); void audio.play() }); URL.revokeObjectURL(url) } catch (caught) { setError(caught instanceof Error ? caught.message : 'Speech synthesis failed.'); dispatchCore({ type: 'FAIL' }) } finally { dispatchCore({ type: 'COMPLETE' }) }
  }, [dispatchCore, online, settings.preferredVoice])
  return { recording, level, error, start, stop, speak, clearError: () => setError('') }
}
