import { useEffect, useState } from 'react'
import { api, errText } from '../api'
import { useAction } from '../ui'
import { ago } from '../format'
import { card, Notice, PageTitle, Spinner, useTitle } from '../ui'

interface Overview { users: number; datasets: number; experiments: Record<string, number>; recent_failures: { id: number; message: string; at: string }[]; recent_feedback: { id: number; email: string; message: string; at: string }[] }

interface AdminUser { id: number; email: string; name: string; is_admin: boolean; is_active: boolean; email_verified: boolean; created_at: string; last_login_at: string | null; datasets: number; experiments: number }

export function Admin() {
  useTitle('Admin')
  const [d, setD] = useState<Overview | null>(null)
  const [users, setUsers] = useState<AdminUser[]>([])
  const [err, setErr] = useState('')
  const { error, run } = useAction()
  const loadUsers = () => { api<{ users: AdminUser[] }>('/api/admin/users').then(r => setUsers(r.users)).catch(() => undefined) }
  useEffect(() => { api<Overview>('/api/admin/overview').then(setD).catch(e => setErr(errText(e))); loadUsers() }, [])
  const toggle = async (u: AdminUser) => {
    if (u.is_active && !window.confirm(`Deactivate ${u.email}? They will be signed out and their running experiments cancelled.`)) return
    const r = await run(() => api(`/api/admin/users/${u.id}/active`, { body: { active: !u.is_active } }))
    if (r !== undefined) loadUsers()
  }
  if (err) return <Notice kind="error">{err}</Notice>
  if (!d) return <Spinner />
  return (
    <div>
      <PageTitle title="Admin overview" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <div className={card}><p className="text-[12px] text-gray-500">Users</p><p className="text-[1.5rem] font-medium">{d.users}</p></div>
        <div className={card}><p className="text-[12px] text-gray-500">Datasets</p><p className="text-[1.5rem] font-medium">{d.datasets}</p></div>
        {Object.entries(d.experiments).map(([k, v]) => <div key={k} className={card}><p className="text-[12px] text-gray-500">Experiments · {k}</p><p className="text-[1.5rem] font-medium">{v}</p></div>)}
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      <div className={`${card} overflow-x-auto mb-4`}>
        <h2 className="text-[15px] font-medium mb-3">Users ({users.length})</h2>
        <table className="w-full text-left text-[12.5px]"><thead className="text-gray-500"><tr><th className="pb-2 pr-3 font-medium">Email</th><th className="pb-2 pr-3 font-medium">Name</th><th className="pb-2 pr-3 font-medium">Data</th><th className="pb-2 pr-3 font-medium">Last seen</th><th className="pb-2 font-medium" /></tr></thead>
          <tbody>{users.map(u => (
            <tr key={u.id} className="border-t border-gray-300"><td className="py-2 pr-3 whitespace-nowrap">{u.email}{u.is_admin && <span className="text-blue-600"> · admin</span>}{!u.email_verified && <span className="text-gray-400"> · unverified</span>}</td>
              <td className="py-2 pr-3">{u.name}</td><td className="py-2 pr-3 whitespace-nowrap">{u.datasets} datasets · {u.experiments} exp.</td><td className="py-2 pr-3 whitespace-nowrap">{u.last_login_at ? ago(u.last_login_at) : '-'}</td>
              <td className="py-2 whitespace-nowrap">{!u.is_admin && <button className={u.is_active ? 'text-red-600 hover:underline' : 'text-blue-600 hover:underline'} onClick={() => { void toggle(u) }}>{u.is_active ? 'Deactivate' : 'Reactivate'}</button>}</td></tr>
          ))}</tbody></table>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className={card}><h2 className="text-[15px] font-medium mb-2">Recent failures</h2>{d.recent_failures.length ? <ul className="space-y-1.5 text-[12.5px]">{d.recent_failures.map(f => <li key={f.id}>#{f.id} · {ago(f.at)} · {f.message}</li>)}</ul> : <p className="text-[12.5px] text-gray-500">None.</p>}</div>
        <div className={card}><h2 className="text-[15px] font-medium mb-2">Feedback</h2>{d.recent_feedback.length ? <ul className="space-y-2 text-[12.5px]">{d.recent_feedback.map(f => <li key={f.id}><span className="text-gray-500">{ago(f.at)} {f.email && `· ${f.email}`}</span><br />{f.message}</li>)}</ul> : <p className="text-[12.5px] text-gray-500">None yet.</p>}</div>
      </div>
    </div>
  )
}
