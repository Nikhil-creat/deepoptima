import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Logo } from '../Logo'
import { api, errText } from './api'
import { useAuth } from './auth'
import { useServerConfig } from './config'
import { navigate } from './router'
import type { Route } from './router'
import { btnCls, inputCls, Notice, useAction } from './ui'

const OWNER_REPO = 'https://github.com/Nikhil-creat/deepoptima'

function useDarkMode(): [boolean, () => void] {
  const [dark, setDark] = useState<boolean>(() => { try { return localStorage.getItem('deepoptima_dark') === '1' } catch { return false } })
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    try { localStorage.setItem('deepoptima_dark', dark ? '1' : '0') } catch { /* ignore */ }
  }, [dark])
  return [dark, () => setDark(d => !d)]
}

function FeedbackBox() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [msg, setMsg] = useState('')
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const { busy, error, run } = useAction()
  const send = async () => {
    const r = await run(() => api('/api/feedback', { body: { message: msg, email: user ? user.email : email } }))
    if (r !== undefined) { setSent(true); setMsg('') }
  }
  if (!open) return <button className="text-[12.5px] text-blue-600 hover:underline" onClick={() => setOpen(true)}>Send feedback</button>
  return (
    <div className="max-w-md">
      {sent ? <Notice kind="success">Thank you! Your message was sent.</Notice> : (
        <>
          {error && <Notice kind="error">{error}</Notice>}
          <textarea className={inputCls} rows={3} maxLength={2000} placeholder="What went well? What was confusing? What is missing?" value={msg} onChange={e => setMsg(e.target.value)} aria-label="Feedback message" />
          {!user && <input className={`${inputCls} mt-2`} type="email" placeholder="Your email (optional, if you want a reply)" value={email} onChange={e => setEmail(e.target.value)} aria-label="Email" />}
          <button className={`${btnCls.primary} mt-2`} disabled={busy || msg.trim().length < 3} onClick={() => { void send() }}>{busy ? 'Sending…' : 'Send'}</button>
        </>
      )}
    </div>
  )
}

export function Footer() {
  return (
    <footer className="border-t border-gray-300 mt-14 px-4 sm:px-8 py-8">
      <div className="max-w-6xl mx-auto grid gap-6 sm:grid-cols-3">
        <div><p className="text-[13px] font-medium text-gray-900 mb-1">DeepOptima Studio</p>
          <p className="text-[12px] text-gray-500 max-w-xs">Free automatic model search for your tables. Compare accuracy, speed and size, then download the model.</p></div>
        <div className="text-[12.5px] space-y-1.5">
          <a className="block text-gray-600 hover:text-gray-900" href="#/help">Help &amp; FAQ</a>
          <a className="block text-gray-600 hover:text-gray-900" href="#/privacy">Privacy</a>
          <a className="block text-gray-600 hover:text-gray-900" href="#/terms">Terms</a>
          <a className="block text-gray-600 hover:text-gray-900" href={OWNER_REPO} target="_blank" rel="noopener noreferrer">Source code</a>
        </div>
        <FeedbackBox />
      </div>
      <p className="max-w-6xl mx-auto text-[11.5px] text-gray-400 mt-6">© {new Date().getFullYear()} Nikhil Chary Sriramoju · MIT License. Results are estimates, not professional advice.</p>
    </footer>
  )
}

const NAV: { path: string; label: string; name: Route['name'][] }[] = [
  { path: '/app', label: 'Overview', name: ['app', 'experiment'] },
  { path: '/datasets', label: 'Datasets', name: ['datasets', 'dataset'] },
  { path: '/help', label: 'Help', name: ['help'] },
]

export function Shell({ route, children }: { route: Route; children: ReactNode }) {
  const { user, signOut } = useAuth()
  const [dark, toggleDark] = useDarkMode()
  const cfg = useServerConfig()
  const { busy: resending, run: runResend } = useAction()
  const [resent, setResent] = useState(false)
  const [server, setServer] = useState<'checking' | 'slow' | 'up' | 'down'>('checking')
  useEffect(() => {
    let live = true
    const slow = window.setTimeout(() => { if (live) setServer(s => (s === 'checking' ? 'slow' : s)) }, 3500)
    api('/api/health', { auth: false }).then(() => { if (live) setServer('up') }).catch(() => { if (live) setServer('down') })
    return () => { live = false; window.clearTimeout(slow) }
  }, [])
  return (
    <div className="min-h-screen bg-[#f0f0ee] text-gray-900 flex flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-2 focus:rounded-lg focus:bg-white focus:px-3 focus:py-2 text-[13px]">Skip to content</a>
      <header className="sticky top-0 z-30 bg-[#f0f0ee]/95 backdrop-blur border-b border-gray-300">
        <div className="max-w-6xl mx-auto px-4 sm:px-8 py-3 flex items-center gap-3 sm:gap-6">
          <a href="#/" className="flex items-center gap-2 shrink-0" aria-label="DeepOptima home">
            <span className="flex items-center justify-center rounded-full w-9 h-9" style={{ backgroundColor: '#EDEDED' }}><Logo /></span>
            <span className="hidden sm:inline text-[14px] font-medium">DeepOptima Studio</span>
          </a>
          <nav className="flex items-center gap-1 overflow-x-auto min-w-0" aria-label="Main">
            {(user ? NAV : NAV.filter(n => n.path === '/help')).map(n => (
              <a key={n.path} href={`#${n.path}`} aria-current={n.name.includes(route.name) ? 'page' : undefined}
                className={`whitespace-nowrap rounded-full px-3 py-1.5 text-[13px] font-medium transition-colors ${n.name.includes(route.name) ? 'bg-[#EDEDED] text-gray-900' : 'text-gray-600 hover:text-gray-900'}`}>{n.label}</a>
            ))}
            {user?.is_admin && <a href="#/admin" className="whitespace-nowrap rounded-full px-3 py-1.5 text-[13px] font-medium text-gray-600 hover:text-gray-900">Admin</a>}
          </nav>
          <div className="ml-auto flex items-center gap-2 shrink-0">
            <button onClick={toggleDark} aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'} className="rounded-full px-2.5 py-1.5 text-[13px] text-gray-600 hover:bg-[#EDEDED]">{dark ? '☀' : '☾'}</button>
            {user ? (
              <>
                <button className={`${btnCls.primary} !px-4 !py-2`} onClick={() => navigate('/new')}>+ New<span className="hidden sm:inline"> experiment</span></button>
                <a href="#/account" className="hidden sm:inline text-[13px] text-gray-700 hover:text-gray-900 max-w-[120px] truncate" title={user.email}>{user.name}</a>
                <button className="text-[12.5px] text-gray-500 hover:text-gray-900" onClick={signOut}>Sign out</button>
              </>
            ) : (
              <>
                <a href="#/login" className="text-[13px] font-medium text-gray-700 hover:text-gray-900">Sign in</a>
                <a href="#/register" className={`${btnCls.primary} !px-4 !py-2`}>Start free</a>
              </>
            )}
          </div>
        </div>
      </header>
      <main id="main" className="flex-1 w-full max-w-6xl mx-auto px-4 sm:px-8 pt-6">
        {server === 'slow' && <Notice kind="info">Waking up the server… this can take up to a minute on the free plan.</Notice>}
        {server === 'down' && <Notice kind="warn">The Studio server is not reachable right now. Please try again in a minute. (Site owner: set <code>apiUrl</code> in <code>frontend/public/config.json</code> to your running backend, then redeploy.)</Notice>}
        {user && cfg?.email_enabled && !user.email_verified && (
          <Notice kind="warn">Please confirm your email address{cfg.require_verification ? ' to upload data and run experiments' : ''}. {resent ? 'A new link is on its way.' : (
            <button className="underline font-medium" disabled={resending} onClick={() => { void runResend(() => api('/api/me/resend-verification', { method: 'POST' })).then(r => { if (r !== undefined) setResent(true) }) }}>Resend the email</button>)}</Notice>
        )}
        {children}
      </main>
      <Footer />
    </div>
  )
}

export { errText }
