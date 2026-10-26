import { useEffect, useState } from 'react'
import { api, errText } from '../api'
import { ago } from '../format'
import { card, Notice, PageTitle, Spinner, useTitle } from '../ui'

interface Overview { users: number; datasets: number; experiments: Record<string, number>; recent_failures: { id: number; message: string; at: string }[]; recent_feedback: { id: number; email: string; message: string; at: string }[] }

export function Admin() {
  useTitle('Admin')
  const [d, setD] = useState<Overview | null>(null)
  const [err, setErr] = useState('')
  useEffect(() => { api<Overview>('/api/admin/overview').then(setD).catch(e => setErr(errText(e))) }, [])
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
      <div className="grid gap-4 lg:grid-cols-2">
        <div className={card}><h2 className="text-[15px] font-medium mb-2">Recent failures</h2>{d.recent_failures.length ? <ul className="space-y-1.5 text-[12.5px]">{d.recent_failures.map(f => <li key={f.id}>#{f.id} · {ago(f.at)} · {f.message}</li>)}</ul> : <p className="text-[12.5px] text-gray-500">None.</p>}</div>
        <div className={card}><h2 className="text-[15px] font-medium mb-2">Feedback</h2>{d.recent_feedback.length ? <ul className="space-y-2 text-[12.5px]">{d.recent_feedback.map(f => <li key={f.id}><span className="text-gray-500">{ago(f.at)} {f.email && `· ${f.email}`}</span><br />{f.message}</li>)}</ul> : <p className="text-[12.5px] text-gray-500">None yet.</p>}</div>
      </div>
    </div>
  )
}
