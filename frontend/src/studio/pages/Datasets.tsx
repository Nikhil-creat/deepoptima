import { useEffect, useRef, useState } from 'react'
import type { DragEvent } from 'react'
import { api, errText } from '../api'
import { useAuth } from '../auth'
import { dateOnly } from '../format'
import { navigate } from '../router'
import { sampleChurnCsv } from '../sample'
import type { Dataset, Limits } from '../types'
import { btnCls, card, Chip, Empty, Field, inputCls, Notice, PageTitle, Spinner, useAction, useTitle } from '../ui'

function UploadBox({ limits, onDone }: { limits: Limits | null; onDone: (d: Dataset) => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [over, setOver] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const { busy, error, setError, run } = useAction()
  const pick = (f: File | undefined) => {
    setError('')
    if (!f) return
    if (!/\.(csv|txt|tsv)$/i.test(f.name)) { setError('Please choose a .csv file.'); return }
    if (limits && f.size > limits.max_upload_mb * 1024 * 1024) { setError(`That file is larger than ${limits.max_upload_mb} MB.`); return }
    setFile(f); if (!name) setName(f.name.replace(/\.[^.]+$/, '').slice(0, 80))
  }
  const send = async (f: File, n: string) => {
    const form = new FormData(); form.append('file', f); form.append('name', n)
    const d = await run(() => api<Dataset>('/api/datasets', { form }))
    if (d) onDone(d)
  }
  const drop = (e: DragEvent<HTMLDivElement>) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files[0]) }
  return (
    <div className={card}>
      {error && <Notice kind="error">{error}</Notice>}
      <div onDragOver={e => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)} onDrop={drop}
        className={`rounded-lg border-2 border-dashed px-4 py-8 text-center transition-colors ${over ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-white/60'}`}>
        <p className="text-[14px] font-medium text-gray-900">{file ? file.name : 'Drop a CSV file here'}</p>
        <p className="text-[12px] text-gray-500 mt-1">{file ? `${(file.size / 1024).toFixed(0)} KB` : `or choose one · up to ${limits?.max_upload_mb ?? 5} MB, ${(limits?.max_rows ?? 50000).toLocaleString()} rows, header row required`}</p>
        <button type="button" className={`${btnCls.outline} mt-3`} onClick={() => input.current?.click()}>Choose file</button>
        <input ref={input} type="file" accept=".csv,.txt,.tsv,text/csv" className="hidden" aria-label="CSV file" onChange={e => { pick(e.target.files?.[0]); e.target.value = '' }} />
      </div>
      {file && (
        <div className="mt-4">
          <Field label="Dataset name"><input className={inputCls} maxLength={80} value={name} onChange={e => setName(e.target.value)} /></Field>
          <button className={btnCls.primary} disabled={busy || !name.trim()} onClick={() => { void send(file, name.trim()) }}>{busy ? 'Uploading and checking…' : 'Upload'}</button>
        </div>
      )}
      <p className="text-[11.5px] text-gray-500 mt-4">Your file is stored privately in your account and used only to train your models. Do not upload passwords, health records or other sensitive personal data. <a className="text-blue-600 underline" href="#/privacy">Privacy</a></p>
      <button className="text-[12.5px] text-blue-600 hover:underline mt-2" disabled={busy} onClick={() => { void send(new File([sampleChurnCsv()], 'sample-customer-churn.csv', { type: 'text/csv' }), 'Sample: customer churn') }}>No data handy? Use the sample customer-churn table</button>
    </div>
  )
}

export function Datasets() {
  useTitle('Datasets')
  const [sets, setSets] = useState<Dataset[] | null>(null)
  const [limits, setLimits] = useState<Limits | null>(null)
  const [err, setErr] = useState('')
  useEffect(() => {
    api<{ datasets: Dataset[] }>('/api/datasets').then(r => setSets(r.datasets)).catch(e => setErr(errText(e)))
    api<{ limits: Limits }>('/api/me').then(r => setLimits(r.limits)).catch(() => undefined)
  }, [])
  if (err) return <Notice kind="error">{err}</Notice>
  return (
    <div>
      <PageTitle title="Datasets" sub="Upload a CSV table. We check it, summarise every column and flag problems before you train." />
      <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
        <UploadBox limits={limits} onDone={d => navigate(`/datasets/${d.id}`)} />
        <div>
          {!sets ? <Spinner /> : sets.length === 0 ? <Empty title="No datasets yet" text="Your uploaded tables will be listed here." /> : (
            <ul className="space-y-2">
              {sets.map(d => (
                <li key={d.id}><a href={`#/datasets/${d.id}`} className={`${card} !py-3.5 flex items-center gap-3 hover:bg-[#e6e6e4] transition-colors`}>
                  <div className="min-w-0"><p className="text-[14px] font-medium text-gray-900 truncate">{d.name}</p><p className="text-[12px] text-gray-500">{d.n_rows.toLocaleString()} rows · {d.n_cols} columns · {dateOnly(d.created_at)}</p></div>
                  <span className="ml-auto text-[12px] text-blue-600">Open →</span></a></li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}

export function DatasetDetail({ id }: { id: number }) {
  const [d, setD] = useState<Dataset | null>(null)
  const [err, setErr] = useState('')
  const { busy, error, run } = useAction()
  useTitle(d?.name ?? 'Dataset')
  useEffect(() => { api<Dataset>(`/api/datasets/${id}`).then(setD).catch(e => setErr(errText(e))) }, [id])
  if (err) return <Notice kind="error">{err} <a className="underline" href="#/datasets">Back to datasets</a></Notice>
  if (!d || !d.profile) return <Spinner />
  const p = d.profile
  const del = async () => {
    if (!window.confirm('Delete this dataset and every experiment that used it? This cannot be undone.')) return
    const r = await run(() => api(`/api/datasets/${id}`, { method: 'DELETE' }))
    if (r) navigate('/datasets')
  }
  const kindChip = (k: string) => k === 'numeric' ? <Chip tone="blue">number</Chip> : k === 'categorical' ? <Chip tone="green">category</Chip> : <Chip tone="amber">ignored</Chip>
  return (
    <div>
      <p className="text-[12.5px] mb-2"><a className="text-blue-600" href="#/datasets">← Datasets</a></p>
      <PageTitle title={d.name} sub={`${p.n_rows.toLocaleString()} rows · ${p.n_cols} columns · uploaded ${dateOnly(d.created_at)}`}
        right={<div className="flex gap-2"><a className={btnCls.primary} href={`#/new?dataset=${d.id}`}>Create experiment</a><button className={btnCls.danger} disabled={busy} onClick={() => { void del() }}>Delete</button></div>} />
      {error && <Notice kind="error">{error}</Notice>}
      {p.warnings.length > 0 && <Notice kind="warn"><b>Heads up:</b><ul className="list-disc ml-5 mt-1">{p.warnings.map(w => <li key={w}>{w}</li>)}</ul></Notice>}
      <div className={`${card} overflow-x-auto mb-4`}>
        <h2 className="text-[15px] font-medium mb-3">Columns</h2>
        <table className="w-full text-left text-[12.5px]"><thead><tr className="text-gray-500"><th className="pb-2 pr-3 font-medium">Name</th><th className="pb-2 pr-3 font-medium">Type</th><th className="pb-2 pr-3 font-medium">Missing</th><th className="pb-2 pr-3 font-medium">Distinct</th><th className="pb-2 font-medium">Examples</th></tr></thead>
          <tbody>{p.columns.map(c => (
            <tr key={c.name} className="border-t border-gray-300 align-top"><td className="py-2 pr-3 font-medium text-gray-900 whitespace-nowrap">{c.name}</td><td className="py-2 pr-3">{kindChip(c.kind)}</td>
              <td className="py-2 pr-3 whitespace-nowrap">{c.missing_pct}%</td><td className="py-2 pr-3">{c.n_unique}</td><td className="py-2 text-gray-600 min-w-[160px]">{c.kind === 'numeric' && c.min != null ? `${c.min} … ${c.max}` : c.examples.join(', ')}</td></tr>
          ))}</tbody></table>
      </div>
      {d.preview && d.preview.length > 0 && (
        <div className={`${card} overflow-x-auto`}>
          <h2 className="text-[15px] font-medium mb-3">First rows</h2>
          <table className="text-left text-[12px] whitespace-nowrap"><thead><tr className="text-gray-500">{Object.keys(d.preview[0]).map(k => <th key={k} className="pb-2 pr-4 font-medium">{k}</th>)}</tr></thead>
            <tbody>{d.preview.map((row, i) => <tr key={i} className="border-t border-gray-300">{Object.keys(d.preview![0]).map(k => <td key={k} className="py-1.5 pr-4 text-gray-700">{row[k] === null || row[k] === undefined ? '' : String(row[k])}</td>)}</tr>)}</tbody></table>
        </div>
      )}
    </div>
  )
}

export { useAuth }
