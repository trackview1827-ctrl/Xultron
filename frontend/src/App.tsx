import { useApp } from './stores/AppContext'
import { AuthGateway } from './features/auth/AuthGateway'
import { AppShell } from './layouts/AppShell'
import { Spinner } from './components/ui'

export function App() {
  const { sessionReady, user } = useApp()
  if (!sessionReady) return <div className="boot-screen"><span className="boot-mark">X</span><Spinner /><span>INITIALIZING XULTRON</span></div>
  return user ? <AppShell /> : <AuthGateway />
}
