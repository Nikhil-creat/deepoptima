import { useEffect, useState } from 'react'
import { api, download, errText, getBase } from '../api'
import { ActualVsPredicted, Bars, ConfusionMatrix, ParetoChart, ProgressBar } from '../charts'
import { dateOnly, fmtScore } from '../format'
import { navigate } from '../router'
import { buildReport, saveText } from '../report'
import { finalsOf, ModelsTable, SummaryCards, TrialsTable } from '../results'
import type { ExperimentDetail, FeatureMeta, Trial } from '../types'
import { btnCls, card, inputCls, Notice, PageTitle, Spinner, StatusBadge, useAction, useTitle } from '../ui'

const ACTIVE = ['queued', 'running']

function Duration({ e }: { e: ExperimentDetail }) {
  if (!e.started_at) return null
  const end = e.finished_at ? new Date(e.finished_at).getTime() : Date.now()
  const s = Math.max(0, Math.round((end - new Date(e.started_at).getTime()) / 1000))
  return <span>{s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`}</span>
}

function PredictPanel({ e, modelId }: { e: ExperimentDetail; modelId: number | null }) {
  const feats: FeatureMeta[] = e.result?.features ?? []
  const [tab, setTab] = useState<'form' | 'file'>('form')
  const [vals, setVals] = useState<Record<string, string>>({})
  const [out, setOut] = useState<{ prediction: string; confidence?: number } | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [fileOut, setFileOut] = useState<{ n: number; predictions: (string | number)[]; confidence?: number[]; preview: Record<string, unknown>[] } | null>(null)
  const { busy, error, run } = useAction()
  const single = async () => {
    const row: Record<string, string | number> = {}
    for (const f of feats) {
      const v = (vals[f.name] ?? '').trim()
      if (v === '') continue
      row[f.name] = f.kind === 'numeric' ? Number(v) : v
    }
    const r = await run(() => api<{ predictions: (string | number)[]; confidence?: number[] }>(`/api/experiments/${e.id}/predict`, { body: { trial_id: modelId, rows: [row] } }))
    if (r) setOut({ prediction: String(r.predictions[0]), confidence: r.confidence?.[0] })
  }
  const form = (fmt: string): FormData => { const fd = new FormData(); if (file) fd.append('file', file); fd.append('fmt', fmt); if (modelId) fd.append('trial_id', String(modelId)); return fd }
  const predictFile = async () => {
    const r = await run(() => api<NonNullable<typeof fileOut>>(`/api/experiments/${e.id}/predict-file`, { form: form('json') }))
    if (r) setFileOut(r)
  }
  return (
    <div className={card}>
      <h2 className="text-[15px] font-medium mb-1">Use the model</h2>
      <p className="text-[12px] text-gray-500 mb-3">Get predictions right here, or download the model below to use it in your own code. Blank fields are treated as “unknown”.</p>
      <div className="flex gap-2 mb-4">{(['form', 'file'] as const).map(t => <button key={t} onClick={() => setTab(t)} className={`rounded-full px-4 py-1.5 text-[12.5px] border ${tab === t ? 'bg-blue-500 text-white border-blue-500' : 'border-gray-300 text-gray-700'}`}>{t === 'form' ? 'One row' : 'Upload CSV'}</button>)}</div>
      {error && <Notice kind="error">{error}</Notice>}
      {tab === 'form' ? (
        <div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {feats.map(f => (
              <label key={f.name} className="block"><span className="block text-[12px] font-medium text-gray-800 mb-1 truncate" title={f.name}>{f.name}</span>
                <input className={inputCls} value={vals[f.name] ?? ''} onChange={ev => setVals({ ...vals, [f.name]: ev.target.value })} inputMode={f.kind === 'numeric' ? 'decimal' : 'text'} list={f.kind === 'categorical' ? `dl-${f.name}` : undefined}
                  placeholder={f.kind === 'numeric' ? `e.g. ${Math.round(((f.median ?? 0) + Number.EPSILON) * 100) / 100}` : (f.values?.[0] ?? 'text')} />
                {f.kind === 'categorical' && <datalist id={`dl-${f.name}`}>{f.values?.map(v => <option key={v} value={v} />)}</datalist>}
                {f.kind === 'numeric' && f.min !== undefined && <span className="block text-[10.5px] text-gray-400 mt-0.5">seen {Math.round((f.min ?? 0) * 100) / 100} … {Math.round((f.max ?? 0) * 100) / 100}</span>}</label>
            ))}
          </div>
          <button className={`${btnCls.primary} mt-4`} disabled={busy} onClick={() => { void single() }}>{busy ? 'Predicting…' : 'Predict'}</button>
          {out && <div className="mt-4 rounded-lg bg-white p-4"><p className="text-[12px] text-gray-500">Prediction for “{e.target}”</p><p className="text-[1.5rem] font-medium text-gray-900 break-words">{out.prediction}</p>
            {out.confidence !== undefined && <p className="text-[12px] text-gray-500">model confidence {(out.confidence * 100).toFixed(0)}%</p>}</div>}
        </div>
      ) : (
        <div>
          <input type="file" accept=".csv,.txt,.tsv,text/csv" aria-label="CSV to predict" className="text-[12.5px]" onChange={ev => { setFile(ev.target.files?.[0] ?? null); setFileOut(null) }} />
          <p className="text-[11.5px] text-gray-500 mt-1">Same column names as your training data (the target column is not needed). Up to 1,000 rows, 2 MB.</p>
          <div className="flex flex-wrap gap-2 mt-3">
            <button className={btnCls.primary} disabled={busy || !file} onClick={() => { void predictFile() }}>{busy ? 'Predicting…' : 'Predict'}</button>
            <button className={btnCls.outline} disabled={!file} onClick={() => { void run(() => download(`/api/experiments/${e.id}/predict-file`, 'predictions.csv', form('csv'))) }}>Download predictions CSV</button>
          </div>
          {fileOut && (
            <div className="mt-4 overflow-x-auto"><p className="text-[12px] text-gray-500 mb-1">{fileOut.n} rows predicted. Showing the first {fileOut.preview.length}.</p>
              <table className="text-[12px] whitespace-nowrap"><thead><tr className="text-gray-500">{Object.keys(fileOut.preview[0] ?? {}).slice(0, 6).map(k => <th key={k} className="pr-4 pb-1 font-medium text-left">{k}</th>)}<th className="pr-4 pb-1 font-medium text-left text-blue-600">prediction</th>{fileOut.confidence && <th className="pb-1 font-medium text-left">confidence</th>}</tr></thead>
                <tbody>{fileOut.preview.map((row, i) => <tr key={i} className="border-t border-gray-300">{Object.keys(fileOut.preview[0]).slice(0, 6).map(k => <td key={k} className="pr-4 py-1">{String(row[k] ?? '')}</td>)}<td className="pr-4 py-1 font-medium">{String(fileOut.predictions[i])}</td>{fileOut.confidence && <td className="py-1">{((fileOut.confidence[i] ?? 0) * 100).toFixed(0)}%</td>}</tr>)}</tbody></table></div>
          )}
        </div>
      )}
    </div>
  )
}

function ApiPanel({ e, modelId }: { e: ExperimentDetail; modelId: number | null }) {
  const [copied, setCopied] = useState(false)
  const base = getBase() || window.location.origin
  const feats = (e.result?.features ?? []).slice(0, 3)
  const row = Object.fromEntries(feats.map(f => [f.name, f.kind === 'numeric' ? Math.round((f.median ?? 0) * 100) / 100 : (f.values?.[0] ?? 'value')]))
  const body = JSON.stringify({ trial_id: modelId, rows: [row] }).replace(/'/g, "'\\''")
  const cmd = `curl -X POST ${base}/api/experiments/${e.id}/predict \\\n  -H "Authorization: Bearer YOUR_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '${body}'`
  return (
    <div className={card}>
      <h2 className="text-[15px] font-medium mb-1">Use it from your own app (API)</h2>
      <p className="text-[12px] text-gray-500 mb-3">Create a key under <a className="text-blue-600 underline" href="#/account">Account → API keys</a>. Keys can only request predictions and read experiments. Send as many columns as you have; missing ones count as unknown.</p>
      <div className="flex items-start gap-2 rounded-lg bg-gray-900 text-gray-100 px-3 py-2.5 min-w-0">
        <pre className="flex-1 min-w-0 overflow-x-auto text-[11.5px] leading-relaxed whitespace-pre">{cmd}</pre>
        <button className="text-[12px] text-gray-300 hover:text-white shrink-0" onClick={() => { void navigator.clipboard.writeText(cmd).then(() => { setCopied(true); window.setTimeout(() => setCopied(false), 1500) }).catch(() => undefined) }}>{copied ? 'Copied' : 'Copy'}</button>
      </div>
    </div>
  )
}

function SharePanel({ e, onChange }: { e: ExperimentDetail; onChange: () => void }) {
  const { busy, error, run } = useAction()
  const [copied, setCopied] = useState(false)
  const link = e.share_token ? `${window.location.origin}${window.location.pathname}#/share/${e.share_token}` : ''
  const toggle = async () => { const r = await run(() => api(`/api/experiments/${e.id}/share`, { body: { enabled: !e.share_token } })); if (r !== undefined) onChange() }
  return (
    <div className={card}>
      <h2 className="text-[15px] font-medium mb-1">Share results</h2>
      <p className="text-[12px] text-gray-500 mb-3">A read-only page with model names, scores and feature names. Your data and models are never shared. Turn it off any time.</p>
      {error && <Notice kind="error">{error}</Notice>}
      {link && <div className="flex gap-2 mb-3"><input className={inputCls} readOnly value={link} aria-label="Share link" onFocus={ev => ev.currentTarget.select()} />
        <button className={btnCls.outline} onClick={() => { void navigator.clipboard.writeText(link).then(() => { setCopied(true); window.setTimeout(() => setCopied(false), 1500) }).catch(() => undefined) }}>{copied ? 'Copied' : 'Copy'}</button></div>}
      <button className={e.share_token ? btnCls.danger : btnCls.outline} disabled={busy || e.status !== 'done'} onClick={() => { void toggle() }}>{e.share_token ? 'Stop sharing' : 'Create share link'}</button>
    </div>
  )
}

export function ExperimentPage({ id }: { id: number }) {
  const [e, setE] = useState<ExperimentDetail | null>(null)
  const [err, setErr] = useState('')
  const [key, setKey] = useState(0)
  const [model, setModel] = useState<number | null>(null)
  const { busy, error, run } = useAction()
  useTitle(e?.name ?? 'Experiment')
  useEffect(() => {
    let live = true
    let timer = 0
    const tick = async () => {
      try {
        const d = await api<ExperimentDetail>(`/api/experiments/${id}`)
        if (!live) return
        setE(d); setErr('')
        if (ACTIVE.includes(d.status)) timer = window.setTimeout(() => { void tick() }, 2000)
      } catch (x) {
        if (!live) return
        setErr(errText(x))
        timer = window.setTimeout(() => { void tick() }, 5000)       // keep trying (server may be waking up)
      }
    }
    void tick()
    return () => { live = false; window.clearTimeout(timer) }
  }, [id, key])
  useEffect(() => { if (e && model === null && e.result?.best_trial_id) setModel(e.result.best_trial_id) }, [e, model])

  if (!e) return err ? <Notice kind="error">{err} <a className="underline" href="#/app">Back</a></Notice> : <Spinner label="Loading experiment…" />
  const active = ACTIVE.includes(e.status)
  const finals = finalsOf(e.trials)
  const chartSel = model
  const refresh = () => setKey(k => k + 1)
  const cancel = async () => { const r = await run(() => api(`/api/experiments/${id}/cancel`, { method: 'POST' })); if (r !== undefined) refresh() }
  const del = async () => {
    if (!window.confirm('Delete this experiment and its models? This cannot be undone.')) return
    const r = await run(() => api(`/api/experiments/${id}`, { method: 'DELETE' }))
    if (r !== undefined) navigate('/app')
  }
  const progress = e.status === 'queued' ? 3 : e.total_generations ? (e.generation / e.total_generations) * 100 : 0
  const dl = (t: Trial) => <button className="ml-3 text-[12px] text-blue-600 hover:underline" onClick={() => { void run(() => download(`/api/experiments/${id}/models/${t.id}/download`, `model-${t.id}.joblib`)) }}>Download</button>
  return (
    <div className="space-y-4">
      <p className="text-[12.5px]"><a className="text-blue-600" href="#/app">← Overview</a></p>
      <PageTitle title={e.name} sub={`${e.dataset_name ?? 'Dataset'} → predict “${e.target}” · ${e.task} · ${e.metric.replace('_', ' ')} · ${dateOnly(e.created_at)}`}
        right={<div className="flex items-center gap-2 flex-wrap"><StatusBadge s={e.status} />{active && <button className={btnCls.outline} disabled={busy} onClick={() => { void cancel() }}>Cancel</button>}
          {e.status === 'done' && <button className={btnCls.outline} onClick={() => saveText(`report-${e.id}.html`, buildReport(e))}>Report</button>}
          {!active && <a className={btnCls.outline} href={`#/new?clone=${e.id}`}>Run again…</a>}
          {!active && <button className={btnCls.danger} disabled={busy} onClick={() => { void del() }}>Delete</button>}</div>} />
      {error && <Notice kind="error">{error}</Notice>}
      {err && <Notice kind="warn">Connection problem: {err}. Retrying…</Notice>}
      {active && (
        <div className={card}>
          <div className="flex justify-between text-[12.5px] text-gray-700 mb-2"><span>{e.message || 'Working…'}</span><span>{e.started_at && <>running <Duration e={e} /></>}</span></div>
          <ProgressBar value={progress} />
          <p className="text-[11.5px] text-gray-500 mt-2">You can close this tab. Experiments keep running and appear in your Overview.</p>
        </div>
      )}
      {e.status === 'failed' && <Notice kind="error"><b>This experiment could not finish.</b> {e.message} <a className="underline ml-1" href={`#/new?dataset=${e.dataset_id}`}>Try again with other settings</a></Notice>}
      {e.status === 'cancelled' && <Notice kind="warn">{e.message}</Notice>}
      {e.status === 'done' && e.message.startsWith('Stopped') && <Notice kind="info">{e.message}</Notice>}
      {(e.result?.notes ?? []).map(n => <Notice key={n} kind="info">{n}</Notice>)}
      {finals[0] && (finals[0].test_score as number) >= 0.99 && (e.task === 'regression' || (e.result?.baseline_test ?? 0) < 0.9) && (
        <Notice kind="warn"><b>Suspiciously perfect.</b> A near-perfect score often means a column leaks the answer (an ID, or something only known after the outcome). Check “What mattered most”, then use <a className="underline" href={`#/new?clone=${e.id}`}>Run again</a> to exclude suspicious columns.</Notice>
      )}
      {e.trials.length > 0 && <SummaryCards trials={e.trials} result={e.result} metric={e.metric} baselineVal={e.baseline_score} />}
      {finals.length > 0 && (
        <div className={card}>
          <h2 className="text-[15px] font-medium mb-3">Recommended models</h2>
          <ModelsTable trials={e.trials} metric={e.metric} task={e.task} selected={model} onSelect={t => setModel(t.id)} action={dl} />
          <div className="mt-4 flex flex-wrap gap-2">
            <button className={btnCls.outline} onClick={() => { void run(() => download(`/api/experiments/${id}/script${model ? `?trial_id=${model}` : ''}`, 'predict.py')) }}>Download predict.py</button>
            <span className="text-[11.5px] text-gray-500 self-center">Needs: pip install scikit-learn=={e.result?.sklearn_version ?? '…'} pandas joblib · put model.joblib next to predict.py</span>
          </div>
        </div>
      )}
      {e.trials.length > 1 && (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className={card}><h2 className="text-[15px] font-medium mb-2">Score vs speed vs size</h2><ParetoChart trials={e.trials} metric={e.metric} selectedId={chartSel} onSelect={t => { if (t.is_final) setModel(t.id) }} /></div>
          <div className={card}><h2 className="text-[15px] font-medium mb-3">What mattered most</h2>
            {e.result?.importance?.length ? <Bars items={e.result.importance.slice(0, 10).map(i => ({ label: i.feature, value: i.importance }))} /> : <p className="text-[12.5px] text-gray-500">Feature importance appears when the experiment finishes.</p>}
            <p className="text-[11.5px] text-gray-500 mt-3">How much the best model's score drops when a column is scrambled. Correlation, not proof of cause.</p></div>
        </div>
      )}
      {e.result?.diagnostics && (
        <div className={card}>
          <h2 className="text-[15px] font-medium mb-3">{e.result.diagnostics.kind === 'confusion' ? 'Where the best model is right and wrong' : 'How far off the predictions are'}</h2>
          {e.result.diagnostics.kind === 'confusion'
            ? <ConfusionMatrix labels={e.result.diagnostics.labels} matrix={e.result.diagnostics.matrix} />
            : <div className="grid gap-4 md:grid-cols-[1fr_1.4fr] items-center"><div><p className="text-[12.5px] text-gray-600">Typical error (MAE): <b>{e.result.diagnostics.mae}</b></p><p className="text-[12.5px] text-gray-600">Large errors weigh more (RMSE): <b>{e.result.diagnostics.rmse}</b></p>
              <p className="text-[11.5px] text-gray-500 mt-2">Same units as “{e.target}”, measured on test rows.</p></div><ActualVsPredicted points={e.result.diagnostics.scatter} /></div>}
        </div>
      )}
      {e.status === 'done' && finals.length > 0 && <PredictPanel e={e} modelId={model} />}
      {e.status === 'done' && finals.length > 0 && <ApiPanel e={e} modelId={model} />}
      <div className="grid gap-4 lg:grid-cols-2">
        {e.status === 'done' && <SharePanel e={e} onChange={refresh} />}
        {e.trials.length > 0 && <details className={card}><summary className="cursor-pointer text-[15px] font-medium">All {e.trials.length} models tried</summary><div className="mt-3"><TrialsTable trials={e.trials} metric={e.metric} /></div></details>}
      </div>
      <p className="text-[11.5px] text-gray-500">{e.result?.n_train ? `Data split: ${e.result.n_train} train · ${e.result.n_val} validation · ${e.result.n_test} test rows. ` : ''}{e.status === 'done' ? `Score shown: ${fmtScore(e.metric, finals[0]?.test_score)} (best, on test rows). ` : ''}Models are statistical estimates; validate them before relying on them for important decisions.</p>
    </div>
  )
}
