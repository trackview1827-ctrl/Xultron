import { motion } from 'framer-motion'
import type { CoreState } from '../../types'
import { coreLabel } from './coreMachine'

const stateColors: Record<CoreState, { main: string; soft: string }> = {
  BOOTING: { main: '#8ca5b5', soft: '#243746' }, OFFLINE: { main: '#65727e', soft: '#151d25' }, CONNECTING: { main: '#987dff', soft: '#2e2854' }, ONLINE: { main: '#57d7ff', soft: '#14384a' },
  LISTENING: { main: '#58f0bc', soft: '#16483b' }, THINKING: { main: '#987dff', soft: '#352a66' }, SPEAKING: { main: '#bcefff', soft: '#17445b' }, ERROR: { main: '#ff627d', soft: '#4b1b29' },
}
export function XultronCore({ state, reducedMotion = false, compact = false, level = 0.4 }: { state: CoreState; reducedMotion?: boolean; compact?: boolean; level?: number }) {
  const color = stateColors[state]; const activeMotion = !reducedMotion && state !== 'OFFLINE'
  const spinDuration = state === 'THINKING' ? 2.6 : state === 'CONNECTING' ? 5 : 18
  const pulseScale = state === 'LISTENING' ? 1 + level * .12 : state === 'SPEAKING' ? 1.055 : state === 'ERROR' ? 1.025 : 1.018
  return <figure className={`x-core ${compact ? 'x-core-compact' : ''}`} data-state={state} aria-label={`Xultron Core: ${coreLabel(state)}`}>
    <div className="core-field" style={{ '--core-color': color.main, '--core-soft': color.soft } as React.CSSProperties}>
      <div className="core-grid" />
      <motion.svg viewBox="0 0 320 320" role="img" aria-hidden="true" animate={activeMotion ? { rotate: state === 'LISTENING' ? 0 : 360 } : { rotate: 0 }} transition={{ duration: spinDuration, repeat: Infinity, ease: 'linear' }}>
        <circle cx="160" cy="160" r="143" className="core-orbit orbit-outer" />
        <path d="M160 17A143 143 0 0 1 303 160M160 303A143 143 0 0 1 17 160" className="core-arc outer-arc" />
        <g className="core-ticks">{Array.from({ length: 24 }, (_, i) => <line key={i} x1="160" y1="26" x2="160" y2={i % 3 === 0 ? 36 : 32} transform={`rotate(${i * 15} 160 160)`} />)}</g>
      </motion.svg>
      <motion.svg viewBox="0 0 320 320" aria-hidden="true" animate={activeMotion && (state === 'THINKING' || state === 'CONNECTING') ? { rotate: -360 } : { rotate: 0 }} transition={{ duration: spinDuration * .72, repeat: Infinity, ease: 'linear' }}>
        <circle cx="160" cy="160" r="108" className="core-orbit" />
        <path d="M86 82a108 108 0 0 1 148 0M234 238a108 108 0 0 1-148 0" className="core-arc inner-arc" />
        <circle cx="160" cy="52" r="3" className="core-node" /><circle cx="160" cy="268" r="3" className="core-node" />
      </motion.svg>
      <motion.div className="core-energy" animate={activeMotion ? { scale: [1, pulseScale, 1], opacity: state === 'ERROR' ? [1, .55, 1] : [0.72, 1, 0.72] } : { scale: 1, opacity: .45 }} transition={{ duration: state === 'LISTENING' ? .48 : state === 'SPEAKING' ? .75 : state === 'ERROR' ? .8 : 3.4, repeat: Infinity, ease: 'easeInOut' }}>
        <svg viewBox="0 0 160 160" aria-hidden="true"><path d="M80 15 132 45 145 102 104 145 46 138 15 89 35 36Z" className="energy-shell" /><path d="m80 38 31 18 8 34-25 27-35-4-19-29 12-31Z" className="energy-inner" /><circle cx="80" cy="80" r="17" className="energy-center" /><circle cx="80" cy="80" r="6" className="energy-seed" /></svg>
      </motion.div>
      {(state === 'LISTENING' || state === 'SPEAKING') && <div className="audio-ring" style={{ transform: `scale(${.92 + level * .12})` }} />}
      <div className="core-axis axis-x" /><div className="core-axis axis-y" />
    </div>
    <figcaption><span className="core-state-dot" style={{ background: color.main }} /><span>{coreLabel(state)}</span></figcaption>
  </figure>
}
