import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import { navigate } from '../router'
import type { User } from '../types'
import { btnCls, card, Field, inputCls, Notice, useAction, useTitle } from '../ui'

export const SUPPORT_EMAIL = 'sriramojunikhil66@gmail.com'
const EMAIL_RE = /^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$/

function afterAuth(): void {
  let next = '/app'
  try { next = sessionStorage.getItem('dopt_next') || '/app'; sessionStorage.removeItem('dopt_next') } catch { /* ignore */ }
  navigate(next.startsWith('/') ? next : '/app')
}

function Frame({ title, sub, children }: { title: string; sub: string; children: ReactNode }) {
  return (
    <div className="max-w-md mx-auto mt-6 sm:mt-12">
      <h1 className="text-[1.5rem] font-medium tracking-tight">{title}</h1>
      <p className="text-[13px] text-gray-500 mb-5">{sub}</p>
      <div className={card}>{children}</div>
    </div>
  )
}

export function Login() {
  useTitle('Sign in')
  const { signIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const { busy, error, run } = useAction()
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const r = await run(() => api<{ token: string; user: User }>('/api/auth/login', { body: { email, password }, auth: false }))
    if (r) { signIn(r.token, r.user); afterAuth() }
  }
  return (
    <Frame title="Welcome back" sub="Sign in to see your datasets and experiments.">
      <form onSubmit={e => { void submit(e) }} noValidate>
        {error && <Notice kind="error">{error}</Notice>}
        <Field label="Email"><input className={inputCls} type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} required /></Field>
        <Field label="Password"><input className={inputCls} type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required /></Field>
        <button className={`${btnCls.primary} w-full`} type="submit" disabled={busy || !email || !password}>{busy ? 'Signing in…' : 'Sign in'}</button>
        <p className="text-[12px] text-gray-500 mt-3">Forgot your password? Automatic email reset is not available yet; <a className="text-blue-600 underline" href={`mailto:${SUPPORT_EMAIL}?subject=Password%20reset%20for%20DeepOptima%20Studio`}>email the site owner</a> from your account address.</p>
      </form>
      <p className="text-[13px] text-gray-600 mt-5 text-center">New here? <a className="text-blue-600 font-medium" href="#/register">Create a free account</a></p>
    </Frame>
  )
}

export function Register() {
  useTitle('Create account')
  const { signIn } = useAuth()
  const [f, setF] = useState({ name: '', email: '', password: '', confirm: '', terms: false })
  const [show, setShow] = useState(false)
  const [touched, setTouched] = useState(false)
  const { busy, error, run } = useAction()
  const errs: Record<string, string> = {}
  if (!f.name.trim()) errs.name = 'Enter your name.'
  if (!EMAIL_RE.test(f.email.trim())) errs.email = 'Enter a valid email address.'
  if (f.password.length < 10) errs.password = 'Use at least 10 characters (a phrase of 3-4 words works well).'
  if (f.confirm !== f.password) errs.confirm = 'Passwords do not match.'
  if (!f.terms) errs.terms = 'Please accept the Terms and Privacy Policy.'
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setTouched(true)
    if (Object.keys(errs).length) return
    const r = await run(() => api<{ token: string; user: User }>('/api/auth/register', { auth: false, body: { name: f.name, email: f.email, password: f.password, accept_terms: f.terms } }))
    if (r) { signIn(r.token, r.user); afterAuth() }
  }
  const e = (k: string): string | undefined => (touched ? errs[k] : undefined)
  return (
    <Frame title="Create your free account" sub="No credit card. Upload a CSV and get a model in minutes.">
      <form onSubmit={ev => { void submit(ev) }} noValidate>
        {error && <Notice kind="error">{error}</Notice>}
        <Field label="Your name" error={e('name')}><input className={inputCls} autoComplete="name" maxLength={80} value={f.name} onChange={ev => setF({ ...f, name: ev.target.value })} /></Field>
        <Field label="Email" error={e('email')} hint="Used only to sign you in."><input className={inputCls} type="email" autoComplete="username" value={f.email} onChange={ev => setF({ ...f, email: ev.target.value })} /></Field>
        <Field label="Password" error={e('password')}>
          <div className="flex gap-2"><input className={inputCls} type={show ? 'text' : 'password'} autoComplete="new-password" value={f.password} onChange={ev => setF({ ...f, password: ev.target.value })} />
            <button type="button" className="text-[12px] text-blue-600 px-2" onClick={() => setShow(s => !s)}>{show ? 'Hide' : 'Show'}</button></div>
        </Field>
        <Field label="Confirm password" error={e('confirm')}><input className={inputCls} type={show ? 'text' : 'password'} autoComplete="new-password" value={f.confirm} onChange={ev => setF({ ...f, confirm: ev.target.value })} /></Field>
        <label className="flex items-start gap-2 text-[12.5px] text-gray-700 mb-1"><input type="checkbox" className="mt-0.5" checked={f.terms} onChange={ev => setF({ ...f, terms: ev.target.checked })} />
          <span>I agree to the <a className="text-blue-600 underline" href="#/terms" target="_blank" rel="noopener noreferrer">Terms</a> and <a className="text-blue-600 underline" href="#/privacy" target="_blank" rel="noopener noreferrer">Privacy Policy</a>, and I will not upload sensitive personal data.</span></label>
        {e('terms') && <p className="text-[11.5px] text-red-600 mb-2" role="alert">{e('terms')}</p>}
        <button className={`${btnCls.primary} w-full mt-3`} type="submit" disabled={busy}>{busy ? 'Creating account…' : 'Create account'}</button>
      </form>
      <p className="text-[13px] text-gray-600 mt-5 text-center">Already registered? <a className="text-blue-600 font-medium" href="#/login">Sign in</a></p>
    </Frame>
  )
}
