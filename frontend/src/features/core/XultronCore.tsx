import { motion } from 'framer-motion'
import type { CoreState } from '../../types'
import { coreLabel } from './coreMachine'

const stateTone: Record<CoreState, { status: string; glow: string }> = {
  BOOTING: { status: '#a1a1aa', glow: '#73737b' },
  OFFLINE: { status: '#55555e', glow: '#34343a' },
  CONNECTING: { status: '#d1d1d6', glow: '#8b8b92' },
  ONLINE: { status: '#f1f1f2', glow: '#a8a8ad' },
  LISTENING: { status: '#ffffff', glow: '#c8c8cc' },
  THINKING: { status: '#d8d8dc', glow: '#99999f' },
  SPEAKING: { status: '#ffffff', glow: '#d2d2d5' },
  ERROR: { status: '#8b8b92', glow: '#5c5c63' },
}

export function XultronCore({ state, reducedMotion = false, compact = false, level = 0.4 }: { state: CoreState; reducedMotion?: boolean; compact?: boolean; level?: number }) {
  const tone = stateTone[state]
  const activeMotion = !reducedMotion && state !== 'OFFLINE' && state !== 'ERROR'
  const spinDuration = state === 'THINKING' ? 3.2 : state === 'CONNECTING' ? 5.8 : state === 'LISTENING' ? 8 : 18
  const pulseScale = state === 'LISTENING' ? 1 + level * .14 : state === 'SPEAKING' ? 1.07 : state === 'ERROR' ? 1.02 : 1.025
  const style = {
    '--core-status': tone.status,
    '--core-glow': tone.glow,
    '--voice-opacity': String(.58 + level * .36),
  } as React.CSSProperties

  return <figure className={`x-core ${compact ? 'x-core-compact' : ''} ${reducedMotion ? 'motion-reduced' : ''}`} data-state={state} aria-label={`Xultron Core: ${coreLabel(state)}`}>
    <div className="core-field" style={style}>
      <div className="core-shadow" />
      <div className="core-grid" />
      <div className="core-scan" />

      <motion.svg className="core-orbit-layer orbit-layer-outer" viewBox="0 0 320 320" role="img" aria-hidden="true" animate={activeMotion ? { rotate: 360 } : { rotate: 0 }} transition={{ duration: spinDuration, repeat: activeMotion ? Infinity : 0, ease: 'linear' }}>
        <circle cx="160" cy="160" r="145" className="core-orbit orbit-outer" />
        <path d="M160 15A145 145 0 0 1 305 160M160 305A145 145 0 0 1 15 160" className="core-arc outer-arc" />
        <g className="core-ticks">{Array.from({ length: 32 }, (_, i) => <line key={i} x1="160" y1="18" x2="160" y2={i % 4 === 0 ? 31 : 25} transform={`rotate(${i * 11.25} 160 160)`} />)}</g>
        <circle cx="160" cy="15" r="3.5" className="core-node" />
      </motion.svg>

      <motion.svg className="core-orbit-layer orbit-layer-middle" viewBox="0 0 320 320" aria-hidden="true" animate={activeMotion ? { rotate: -360 } : { rotate: 0 }} transition={{ duration: spinDuration * .72, repeat: activeMotion ? Infinity : 0, ease: 'linear' }}>
        <circle cx="160" cy="160" r="116" className="core-orbit orbit-middle" />
        <path d="M78 78a116 116 0 0 1 164 0M242 242a116 116 0 0 1-164 0" className="core-arc middle-arc" />
        <circle cx="160" cy="44" r="4" className="core-node core-node-glass" />
        <circle cx="160" cy="276" r="2.5" className="core-node" />
      </motion.svg>

      <motion.svg className="core-orbit-layer orbit-layer-inner" viewBox="0 0 320 320" aria-hidden="true" animate={activeMotion ? { rotate: 360 } : { rotate: 0 }} transition={{ duration: spinDuration * .46, repeat: activeMotion ? Infinity : 0, ease: 'linear' }}>
        <circle cx="160" cy="160" r="88" className="core-orbit orbit-inner" />
        <path d="M98 98a88 88 0 0 1 124 0M222 222a88 88 0 0 1-124 0" className="core-arc inner-arc" />
        <path d="M160 72v13M160 235v13M72 160h13M235 160h13" className="core-cardinals" />
      </motion.svg>

      <motion.div className="core-energy" animate={activeMotion ? { scale: [1, pulseScale, 1], opacity: [.84, 1, .84] } : { scale: 1, opacity: state === 'OFFLINE' ? .46 : .78 }} transition={{ duration: state === 'LISTENING' ? .52 : state === 'SPEAKING' ? .78 : 3.6, repeat: activeMotion ? Infinity : 0, ease: 'easeInOut' }}>
        <div className="core-liquid-orb">
          <span className="liquid-flow liquid-flow-one" />
          <span className="liquid-flow liquid-flow-two" />
          <span className="liquid-highlight" />
          <svg viewBox="0 0 160 160" aria-hidden="true">
            <circle cx="80" cy="80" r="67" className="energy-shell" />
            <circle cx="80" cy="80" r="48" className="energy-inner" />
            <circle cx="80" cy="80" r="21" className="energy-center" />
            <circle cx="80" cy="80" r="7" className="energy-seed" />
          </svg>
        </div>
      </motion.div>

      {(state === 'LISTENING' || state === 'SPEAKING') && <div className="audio-ring" style={{ transform: `scale(${.93 + level * .14})` }} />}
      <div className="core-axis axis-x" /><div className="core-axis axis-y" />
    </div>
    <figcaption><span className="core-state-dot" style={{ background: tone.status, color: tone.status }} /><span>{coreLabel(state)}</span></figcaption>
  </figure>
}
