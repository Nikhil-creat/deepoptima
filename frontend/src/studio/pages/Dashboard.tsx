import { useEffect, useState } from 'react'
import { api, errText } from '../api'
import { useAuth } from '../auth'
import { ago } from '../format'
import { navigate } from '../router'
import { sampleChurnCsv } from '../sample'
import type { Dataset, Experiment, Limits } from '../types'
import { btnCls, card, Empty, Meter, Notice, PageTitle, Spinner, StatusBadge, useAction, useTitle } from '../ui'

export function Dashboard() {
  useTitle('Overview')
  const { user } = useAuth()
  const [exps, setExps] = useState<Experiment[] | null>(null)
  const [sets, setSets] = useState<Dataset[]>([])
  const [meta, setMeta] = useState<{ limits: Limits; usage: { datasets: number; experiments: number } } | null>(null)
  const [err, setErr] = useState('')
  const { busy, error, run } = useAction()
  useEffect(() => {
    let live = true
    Promise.all([api<{ experiments: Experiment[] }>('/api/experiments'), api<{ datasets: Dataset[] }>('/api/datasets'),
      api<{ limits: Limits; usage: { datasets: number; experiments: number } }>('/api/me')])
      .then(([e, d, m]) => { if (live) { setExps(e.experiments); setSets(d.datasets); setMeta(m) } })
      .catch(e => { if (live) setErr(errText(e)) })
    return () => { live = false }
  }, [])
  const useSample = async () => {
    const form = new FormData()
    form.append('file', new File([sampleChurnCsv()], 'sample-customer-churn.csv', { type: 'text/csv' }))
    form.append('name', 'Sample: customer churn')
    const d = await run(() => api<Dataset>('/api/datasets', { form }))
    if (d) navigate(`/new?dataset=${d.id}`)
  }
  if (err) return <Notice kind="error">{err}</Notice>
  if (!exps || !meta) return <Spinner />
  const done = exps.some(e => e.status === 'done')
  const steps = [
    { t: 'Upload a CSV', d: 'Any table with a column you want to predict.', ok: sets.length > 0, href: '#/datasets' },
    { t: 'Run an experiment', d: 'The platform tries many models for you.', ok: exps.length > 0, href: '#/new' },
    { t: 'Download or use the model', d: 'Predict in the browser or download the Python model.', ok: done, href: exps[0] ? `#/experiments/${exps[0].id}` : '#/new' },
  ]
  return (
    <div>
      <PageTitle title={`Hi ${user?.name.split(' ')[0] ?? 'there'}`} sub="Your datasets and experiments live here. Experiments run in the background, so you can close the tab and come back."
        right={<a className={btnCls.primary} href="#/new">+ New experiment</a>} />
      {error && <Notice kind="error">{error}</Notice>}
      <div className="grid gap-3 md:grid-cols-3 mb-4">
        {steps.map((s, i) => (
          <a key={s.t} href={s.href} className={`${card} block hover:bg-[#e6e6e4] transition-colors`}>
            <div className="flex items-center gap-2 mb-1"><span className={`w-6 h-6 rounded-full flex items-center justify-center text-[12px] font-medium ${s.ok ? 'bg-green-500 text-white' : 'bg-white text-gray-600'}`}>{s.ok ? '✓' : i + 1}</span>
              <span className="text-[14px] font-medium text-gray-900">{s.t}</span></div>
            <p className="text-[12.5px] text-gray-500">{s.d}</p>
          </a>
        ))}
      </div>
      <div className="grid gap-3 lg:grid-cols-[2fr_1fr]">
        <div>
          <h2 className="text-[15px] font-medium mb-2">Recent experiments</h2>
          {exps.length === 0 ? (
            <Empty title="No experiments yet" text="Upload your own CSV, or try the built-in sample table (customer churn) to see how it works."
              action={<div className="flex flex-wrap justify-center gap-2"><button className={btnCls.primary} disabled={busy} onClick={() => { void useSample() }}>{busy ? 'Preparing…' : 'Try with sample data'}</button><a className={btnCls.outline} href="#/datasets">Upload my CSV</a></div>} />
          ) : (
            <ul className="space-y-2">
              {exps.slice(0, 8).map(e => (
                <li key={e.id}><a href={`#/experiments/${e.id}`} className={`${card} !py-3.5 flex flex-wrap items-center gap-x-4 gap-y-1 hover:bg-[#e6e6e4] transition-colors`}>
                  <span className="text-[14px] font-medium text-gray-900 min-w-0 truncate max-w-[16rem]">{e.name}</span><StatusBadge s={e.status} />
                  <span className="text-[12px] text-gray-500">{e.dataset_name} → <b className="font-medium">{e.target}</b></span>
                  <span className="text-[12px] text-gray-400 ml-auto">{ago(e.created_at)}</span></a></li>
              ))}
            </ul>
          )}
        </div>
        <div className={card}>
          <h2 className="text-[15px] font-medium mb-3">Your plan: Free</h2>
          <div className="space-y-3">
            <Meter label="Datasets" used={meta.usage.datasets} max={meta.limits.max_datasets} />
            <Meter label="Experiments" used={meta.usage.experiments} max={meta.limits.max_experiments} />
          </div>
          <p className="text-[11.5px] text-gray-500 mt-3">Files up to {meta.limits.max_upload_mb} MB, {meta.limits.max_rows.toLocaleString()} rows, {meta.limits.max_cols} columns. One experiment at a time, up to {Math.round(meta.limits.max_time_limit_s / 60)} min each.</p>
        </div>
      </div>
    </div>
  )
}
