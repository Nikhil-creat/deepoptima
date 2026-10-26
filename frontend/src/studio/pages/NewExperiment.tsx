import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { api, errText } from '../api'
import { FAMILIES, METRICS } from '../format'
import { navigate } from '../router'
import type { Dataset, Experiment, Limits, Task } from '../types'
import { btnCls, card, Field, inputCls, Notice, PageTitle, Spinner, useAction, useTitle } from '../ui'

export function NewExperiment({ preset }: { preset?: number }) {
  useTitle('New experiment')
  const [sets, setSets] = useState<Dataset[] | null>(null)
  const [limits, setLimits] = useState<Limits | null>(null)
  const [dsId, setDsId] = useState<number | null>(preset ?? null)
  const [ds, setDs] = useState<Dataset | null>(null)
  const [err, setErr] = useState('')
  const [f, setF] = useState({ name: '', target: '', task: 'auto' as 'auto' | Task, metric: '', generations: 4, population: 8, time_limit_s: 90, test_size: 0.2, seed: 42 })
  const [fams, setFams] = useState<string[]>(Object.keys(FAMILIES))
  const { busy, error, run } = useAction()

  useEffect(() => {
    api<{ datasets: Dataset[] }>('/api/datasets').then(r => { setSets(r.datasets); if (!dsId && r.datasets[0]) setDsId(r.datasets[0].id) }).catch(e => setErr(errText(e)))
    api<{ limits: Limits }>('/api/me').then(r => setLimits(r.limits)).catch(() => undefined)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  useEffect(() => {
    if (!dsId) return
    setDs(null)
    api<Dataset>(`/api/datasets/${dsId}`).then(d => {
      setDs(d)
      const first = d.profile?.targets.slice().reverse().find(t => t.usable)
      setF(p => ({ ...p, target: first?.name ?? '', metric: '', name: p.name || `${d.name} model` }))
    }).catch(e => setErr(errText(e)))
  }, [dsId])

  const tInfo = ds?.profile?.targets.find(t => t.name === f.target)
  const task: Task = f.task === 'auto' ? (tInfo?.task_hint ?? 'classification') : f.task
  const metrics = METRICS[task]
  const metricValue = f.metric && f.metric in metrics ? f.metric : (task === 'regression' ? 'r2' : (tInfo?.min_class_share ?? 1) < 0.25 ? 'balanced_accuracy' : 'accuracy')
  const maxT = limits?.max_time_limit_s ?? 300
  const timeLimit = Math.min(f.time_limit_s, maxT)
  const rows = ds?.n_rows ?? 0
  const warns = useMemo(() => {
    const w: string[] = []
    if (rows > 20000 && (fams.includes('knn') || fams.includes('mlp'))) w.push('Large dataset: k-nearest neighbours and neural networks can be slow. Consider turning them off.')
    if (tInfo && !tInfo.usable) w.push(`This column cannot be the target: ${tInfo.reason}.`)
    if (f.task !== 'auto' && tInfo && f.task !== tInfo.task_hint) w.push(`This column looks like ${tInfo.task_hint}, but you chose ${f.task}. Make sure that is intended.`)
    if (task === 'classification' && tInfo && tInfo.n_unique > 50) w.push('More than 50 classes is not supported.')
    return w
  }, [rows, fams, tInfo, f.task, task])

  if (err) return <Notice kind="error">{err}</Notice>
  if (!sets) return <Spinner />
  if (sets.length === 0) return <div><PageTitle title="New experiment" /><Notice kind="info">Upload a dataset first. <a className="underline font-medium" href="#/datasets">Go to datasets</a></Notice></div>

  const toggle = (k: string) => setFams(cur => (cur.includes(k) ? cur.filter(x => x !== k) : [...cur, k]))
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!ds) return
    const r = await run(() => api<Experiment>('/api/experiments', { body: { dataset_id: ds.id, name: f.name.trim(), target: f.target, task: f.task, metric: metricValue,
      families: fams, generations: f.generations, population: f.population, time_limit_s: timeLimit, test_size: f.test_size, seed: f.seed } }))
    if (r) navigate(`/experiments/${r.id}`)
  }
  const canSubmit = !!ds && f.name.trim().length > 0 && !!f.target && fams.length > 0 && !!tInfo?.usable && !busy
  const slider = (label: string, key: 'generations' | 'population' | 'time_limit_s', min: number, max: number, step: number, unit = '') => (
    <Field label={`${label}: ${f[key]}${unit}`}><input type="range" className="w-full" min={min} max={max} step={step} value={f[key]} onChange={e => setF({ ...f, [key]: Number(e.target.value) })} /></Field>
  )
  return (
    <div>
      <p className="text-[12.5px] mb-2"><a className="text-blue-600" href="#/app">← Overview</a></p>
      <PageTitle title="New experiment" sub="Tell us what to predict. We try many models, keep the best trade-offs between accuracy, speed and size, and test them on data they never saw." />
      <form onSubmit={e => { void submit(e) }} className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-4">
          <div className={card}>
            <h2 className="text-[15px] font-medium mb-3">1 · What do you want to predict?</h2>
            {error && <Notice kind="error">{error}</Notice>}
            <Field label="Dataset"><select className={inputCls} value={dsId ?? ''} onChange={e => setDsId(Number(e.target.value))}>{sets.map(d => <option key={d.id} value={d.id}>{d.name} ({d.n_rows.toLocaleString()} rows)</option>)}</select></Field>
            <Field label="Experiment name"><input className={inputCls} maxLength={80} value={f.name} onChange={e => setF({ ...f, name: e.target.value })} /></Field>
            <Field label="Column to predict (target)" hint={tInfo ? `${tInfo.n_unique} distinct values · looks like ${tInfo.task_hint}` : ''}>
              <select className={inputCls} value={f.target} onChange={e => setF({ ...f, target: e.target.value, metric: '' })} disabled={!ds}>
                {ds?.profile?.targets.map(t => <option key={t.name} value={t.name} disabled={!t.usable}>{t.name}{t.usable ? '' : ` (unusable: ${t.reason})`}</option>)}
              </select></Field>
            <div className="grid sm:grid-cols-2 gap-x-4">
              <Field label="Type of problem" hint="Auto is right for most data."><select className={inputCls} value={f.task} onChange={e => setF({ ...f, task: e.target.value as 'auto' | Task, metric: '' })}>
                <option value="auto">Auto-detect ({tInfo?.task_hint ?? '…'})</option><option value="classification">Classification (categories)</option><option value="regression">Regression (numbers)</option></select></Field>
              <Field label="How to score models"><select className={inputCls} value={metricValue} onChange={e => setF({ ...f, metric: e.target.value })}>{Object.entries(metrics).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
            </div>
          </div>
          <div className={card}>
            <h2 className="text-[15px] font-medium mb-1">2 · Which kinds of models?</h2>
            <p className="text-[12px] text-gray-500 mb-3">More families means a better search but a longer run. Linear and trees are tiny and fast; boosting is often most accurate.</p>
            <div className="grid sm:grid-cols-2 gap-2">
              {Object.entries(FAMILIES).map(([k, v]) => (
                <label key={k} className="flex items-start gap-2 rounded-lg bg-white/70 px-3 py-2 cursor-pointer"><input type="checkbox" className="mt-1" checked={fams.includes(k)} onChange={() => toggle(k)} />
                  <span><span className="block text-[13px] font-medium text-gray-900">{v.name}</span><span className="block text-[11.5px] text-gray-500">{v.hint}</span></span></label>
              ))}
            </div>
          </div>
        </div>
        <div className="space-y-4">
          <div className={card}>
            <h2 className="text-[15px] font-medium mb-3">3 · Search budget</h2>
            {slider('Generations', 'generations', 1, 8, 1)}
            {slider('Models per generation', 'population', 4, 16, 1)}
            {slider('Time limit', 'time_limit_s', 20, maxT, 10, ' s')}
            <p className="text-[11.5px] text-gray-500 -mt-2 mb-3">The search stops at the time limit and still returns the best models found. Final refitting can take a little longer.</p>
            <details className="text-[12.5px] text-gray-700"><summary className="cursor-pointer font-medium">Advanced</summary>
              <div className="mt-3">
                <Field label={`Held-out test data: ${Math.round(f.test_size * 100)}%`} hint="Never used for training or model selection. Used for honest final scores."><input type="range" className="w-full" min={0.1} max={0.3} step={0.05} value={f.test_size} onChange={e => setF({ ...f, test_size: Number(e.target.value) })} /></Field>
                <Field label="Random seed" hint="Same seed and settings reproduce the same search."><input className={inputCls} type="number" min={0} max={9999} value={f.seed} onChange={e => setF({ ...f, seed: Math.max(0, Math.min(9999, Number(e.target.value) || 0)) })} /></Field>
              </div></details>
          </div>
          {warns.map(w => <Notice key={w} kind="warn">{w}</Notice>)}
          <button type="submit" className={`${btnCls.primary} w-full`} disabled={!canSubmit}>{busy ? 'Starting…' : 'Start experiment'}</button>
          <p className="text-[11.5px] text-gray-500">Runs in the background. About {Math.ceil(timeLimit / 60)} min at most. You can leave this page.</p>
        </div>
      </form>
    </div>
  )
}
