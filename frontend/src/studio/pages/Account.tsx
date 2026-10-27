import { useEffect, useState } from 'react'
import { api, download, errText } from '../api'
import { useAuth } from '../auth'
import { useServerConfig } from '../config'
import { ago, dateOnly } from '../format'
import { navigate } from '../router'
import type { ApiKeyInfo, Limits, User } from '../types'
import { btnCls, card, Chip, Field, inputCls, Meter, Notice, PageTitle, Spinner, useAction, useTitle } from '../ui'

function KeysPanel() {
  const [keys, setKeys] = useState<ApiKeyInfo[] | null>(null)
  const [name, setName] = useState('')
  const [fresh, setFresh] = useState('')
  const [copied, setCopied] = useState(false)
  const { busy, error, run } = useAction()
  const load = () => { api<{ keys: ApiKeyInfo[] }>('/api/me/keys').then(r => setKeys(r.keys)).catch(() => setKeys([])) }
  useEffect(load, [])
  const create = async () => {
    const r = await run(() => api<ApiKeyInfo & { key: string }>('/api/me/keys', { body: { name } }))
    if (r) { setFresh(r.key); setName(''); load() }
  }
  const revoke = async (id: number) => {
    if (!window.confirm('Revoke this key? Apps using it will stop working.')) return
    const r = await run(() => api(`/api/me/keys/${id}`, { method: 'DELETE' }))
    if (r !== undefined) load()
  }
  return (
    <div className={card}>
      <h2 className="text-[15px] font-medium mb-1">API keys</h2>
      <p className="text-[12px] text-gray-500 mb-3">Let your own app request predictions from your models. Keys can only request predictions and read experiments, and you can revoke them any time.</p>
      {error && <Notice kind="error">{error}</Notice>}
      {fresh && <Notice kind="success"><b>Copy your key now; it is shown only once.</b><div className="flex gap-2 mt-2"><input className={inputCls} readOnly value={fresh} aria-label="New API key" onFocus={e => e.currentTarget.select()} />
        <button className={btnCls.outline} onClick={() => { void navigator.clipboard.writeText(fresh).then(() => setCopied(true)).catch(() => undefined) }}>{copied ? 'Copied' : 'Copy'}</button></div></Notice>}
      <ul className="space-y-2 mb-3">{(keys ?? []).map(k => (
        <li key={k.id} className="flex items-center gap-3 rounded-lg bg-white/70 px-3 py-2 text-[12.5px]"><span className="font-medium">{k.name}</span><code className="text-gray-500">{k.prefix}…</code>
          <span className="text-gray-400 ml-auto">{k.last_used_at ? `used ${ago(k.last_used_at)}` : 'never used'}</span><button className="text-red-600 hover:underline" onClick={() => { void revoke(k.id) }}>Revoke</button></li>
      ))}{keys && keys.length === 0 && <li className="text-[12px] text-gray-500">No keys yet.</li>}</ul>
      <div className="flex gap-2"><input className={inputCls} maxLength={60} placeholder="Key name, e.g. my website" value={name} onChange={e => setName(e.target.value)} aria-label="Key name" />
        <button className={btnCls.primary} disabled={busy || !name.trim()} onClick={() => { void create() }}>Create</button></div>
    </div>
  )
}

export function Account() {
  useTitle('Account')
  const { user, setUser, signIn, signOut } = useAuth()
  const cfg = useServerConfig()
  const a4 = useAction()
  const [name, setName] = useState(user?.name ?? '')
  const [pw, setPw] = useState({ old: '', next: '', confirm: '' })
  const [del, setDel] = useState('')
  const [meta, setMeta] = useState<{ limits: Limits; usage: { datasets: number; experiments: number } } | null>(null)
  const [okMsg, setOkMsg] = useState('')
  const a1 = useAction(), a2 = useAction(), a3 = useAction()
  useEffect(() => { api<{ limits: Limits; usage: { datasets: number; experiments: number } }>('/api/me').then(setMeta).catch(() => undefined) }, [])
  if (!user) return <Spinner />
  const saveName = async () => {
    const r = await a1.run(() => api<{ user: User }>('/api/me', { method: 'PATCH', body: { name } }))
    if (r) { setUser(r.user); setOkMsg('Name updated.') }
  }
  const changePw = async () => {
    if (pw.next !== pw.confirm) { a2.setError('The new passwords do not match.'); return }
    const r = await a2.run(() => api<{ token: string; user: User }>('/api/me/password', { body: { old_password: pw.old, new_password: pw.next } }))
    if (r) { signIn(r.token, r.user); setPw({ old: '', next: '', confirm: '' }); setOkMsg('Password changed. Other devices were signed out.') }
  }
  const remove = async () => {
    if (!window.confirm('Permanently delete your account, datasets, experiments and models? This cannot be undone.')) return
    const r = await a3.run(() => api('/api/me', { method: 'DELETE', body: { password: del } }))
    if (r !== undefined) { signOut(); navigate('/') }
  }
  return (
    <div>
      <PageTitle title="Account" sub={`${user.email} · member since ${dateOnly(user.created_at)}`} right={cfg?.email_enabled ? (user.email_verified ? <Chip tone="green">Email confirmed</Chip> : <Chip tone="amber">Email not confirmed</Chip>) : undefined} />
      {okMsg && <Notice kind="success">{okMsg}</Notice>}
      <div className="grid gap-4 lg:grid-cols-2">
        <div className={card}>
          <h2 className="text-[15px] font-medium mb-3">Profile</h2>
          {a1.error && <Notice kind="error">{a1.error}</Notice>}
          <Field label="Name"><input className={inputCls} maxLength={80} value={name} onChange={e => setName(e.target.value)} /></Field>
          <button className={btnCls.primary} disabled={a1.busy || !name.trim() || name === user.name} onClick={() => { void saveName() }}>Save</button>
        </div>
        <div className={card}>
          <h2 className="text-[15px] font-medium mb-3">Your usage (free plan)</h2>
          {meta ? <div className="space-y-3"><Meter label="Datasets" used={meta.usage.datasets} max={meta.limits.max_datasets} /><Meter label="Experiments" used={meta.usage.experiments} max={meta.limits.max_experiments} /></div> : <Spinner />}
        </div>
        <div className={card}>
          <h2 className="text-[15px] font-medium mb-3">Change password</h2>
          {a2.error && <Notice kind="error">{a2.error}</Notice>}
          <Field label="Current password"><input className={inputCls} type="password" autoComplete="current-password" value={pw.old} onChange={e => setPw({ ...pw, old: e.target.value })} /></Field>
          <Field label="New password" hint="At least 10 characters."><input className={inputCls} type="password" autoComplete="new-password" value={pw.next} onChange={e => setPw({ ...pw, next: e.target.value })} /></Field>
          <Field label="Confirm new password"><input className={inputCls} type="password" autoComplete="new-password" value={pw.confirm} onChange={e => setPw({ ...pw, confirm: e.target.value })} /></Field>
          <button className={btnCls.primary} disabled={a2.busy || !pw.old || !pw.next} onClick={() => { void changePw() }}>Change password</button>
        </div>
        <KeysPanel />
        <div className={card}>
          <h2 className="text-[15px] font-medium mb-1">Your data</h2>
          <p className="text-[12px] text-gray-500 mb-3">Download everything we hold about you (profile, dataset summaries, experiments and results) as JSON. Raw files and models can be downloaded from their own pages.</p>
          {a4.error && <Notice kind="error">{a4.error}</Notice>}
          <button className={btnCls.outline} disabled={a4.busy} onClick={() => { void a4.run(() => download('/api/me/export', 'deepoptima-my-data.json')) }}>Download my data</button>
        </div>
        <div className={`${card} border border-red-200`}>
          <h2 className="text-[15px] font-medium mb-1 text-red-700">Delete account</h2>
          <p className="text-[12px] text-gray-600 mb-3">Removes your profile, uploaded data, experiments and trained models right away. This cannot be undone.</p>
          {a3.error && <Notice kind="error">{a3.error}</Notice>}
          <Field label="Confirm with your password"><input className={inputCls} type="password" autoComplete="current-password" value={del} onChange={e => setDel(e.target.value)} /></Field>
          <button className={btnCls.danger} disabled={a3.busy || !del} onClick={() => { void remove() }}>Delete my account</button>
        </div>
      </div>
      <p className="text-[12px] text-gray-500 mt-4"><button className="text-blue-600 hover:underline" onClick={signOut}>Sign out</button></p>
    </div>
  )
}
export { errText }
