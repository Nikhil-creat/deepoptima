import { Component, StrictMode } from 'react'
import type { ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

class Boundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div style={{ padding: 24, fontFamily: 'system-ui, sans-serif' }}>
        <h1 style={{ fontSize: 20 }}>Something went wrong</h1>
        <p style={{ color: '#6b7280', fontSize: 14 }}>Reload the page. If it keeps happening, clear this site&apos;s data and try again.</p>
        <button onClick={() => location.reload()} style={{ marginTop: 12, padding: '8px 16px', borderRadius: 999, border: '1px solid #3b82f6', color: '#3b82f6', background: 'transparent' }}>Reload</button>
      </div>
    )
  }
}
createRoot(document.getElementById('root')!).render(<StrictMode><Boundary><App /></Boundary></StrictMode>)
