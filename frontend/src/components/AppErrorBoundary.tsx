import { Component, Fragment, type ErrorInfo, type ReactNode } from 'react'
import { Button } from './ui'

interface ErrorBoundaryProps { children: ReactNode }
interface ErrorBoundaryState { failed: boolean; recoveryKey: number }

export class AppErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  override state: ErrorBoundaryState = { failed: false, recoveryKey: 0 }

  static getDerivedStateFromError(): Partial<ErrorBoundaryState> {
    return { failed: true }
  }

  override componentDidCatch(_error: Error, _info: ErrorInfo): void {
    // Detailed errors stay in developer tooling. The recovery surface never renders them.
  }

  private retry = () => this.setState(state => ({ failed: false, recoveryKey: state.recoveryKey + 1 }))
  private reload = () => window.location.reload()

  override render() {
    if (!this.state.failed) return <Fragment key={this.state.recoveryKey}>{this.props.children}</Fragment>
    return <main className="fatal-recovery" role="alert">
      <div className="fatal-mark" aria-hidden="true">X</div>
      <span className="section-index">SYSTEM RECOVERY / 01</span>
      <h1>Xultron paused safely.</h1>
      <p>The interface encountered an unexpected condition. Your server-side conversations, providers, and memory were not changed.</p>
      <div className="fatal-actions"><Button onClick={this.retry}>TRY INTERFACE AGAIN</Button><Button variant="secondary" onClick={this.reload}>RELOAD XULTRON</Button></div>
    </main>
  }
}
