/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        void: '#05080d', graphite: '#0a1019', panel: '#0e1722', line: '#1a2b3c',
        cyan: '#57d7ff', ice: '#bcefff', violet: '#987dff', danger: '#ff627d', success: '#58f0bc',
      },
      fontFamily: { sans: ['Inter', 'ui-sans-serif', 'system-ui'], mono: ['IBM Plex Mono', 'ui-monospace', 'monospace'] },
      boxShadow: { core: '0 0 70px rgba(87,215,255,.15)', insetline: 'inset 0 0 0 1px rgba(87,215,255,.12)' },
    },
  },
  plugins: [],
}
