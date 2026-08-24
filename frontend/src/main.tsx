import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import { AppProvider } from './stores/AppContext'
import { AppErrorBoundary } from './components/AppErrorBoundary'
import './theme/global.css'
import './theme/app.css'

if ('serviceWorker' in navigator && import.meta.env.PROD) window.addEventListener('load', () => { void navigator.serviceWorker.register('/sw.js') })

createRoot(document.getElementById('root')!).render(<StrictMode><AppErrorBoundary><AppProvider><App /></AppProvider></AppErrorBoundary></StrictMode>)
