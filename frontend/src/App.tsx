import { useApp } from './stores/AppContext'
import { AuthGateway } from './features/auth/AuthGateway'
import { AppShell } from './layouts/AppShell'
import { Spinner } from './components/ui'
import { AmbientBackdrop } from './components/AmbientBackdrop'

export function App() {
  const { sessionReady, user } = useApp()
  return <>
    <AmbientBackdrop />
    {!sessionReady
      ? <div className="boot-screen"><span className="boot-mark">X</span><Spinner /><span>INITIALIZING XULTRON</span></div>
      : user ? <AppShell /> : <AuthGateway />}
  </>
}
