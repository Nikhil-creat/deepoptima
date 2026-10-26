import { useEffect, useState } from 'react'
import { api, errText } from '../api'
import { useAuth } from '../auth'
import { dateOnly } from '../format'
import { navigate } from '../router'
import type { Limits, User } from '../types'
import { btnCls, card, Field, inputCls, Meter, Notice, PageTitle, Spinner, useAction, useTitle } from '../ui'

export function Account() {
  useTitle('Account')
  const { user, setUser, signIn, signOut } = useAuth()
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
      <PageTitle title="Account" sub={`${user.email} · member since ${dateOnly(user.created_at)}`} />
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
