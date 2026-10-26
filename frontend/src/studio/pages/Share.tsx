import { useEffect, useState } from 'react'
import { api, errText } from '../api'
import { Bars, ParetoChart } from '../charts'
import { dateOnly } from '../format'
import { ModelsTable, SummaryCards } from '../results'
import type { Config, Result, Task, Trial } from '../types'
import { btnCls, card, Notice, Spinner, useTitle } from '../ui'

interface Shared { name: string; task: Task; metric: string; target: string; config: Config; baseline_score: number | null; finished_at: string | null; result: Result; trials: Trial[] }

export function SharePage({ token }: { token: string }) {
  const [d, setD] = useState<Shared | null>(null)
  const [err, setErr] = useState('')
  useTitle(d?.name ?? 'Shared result')
  useEffect(() => { api<Shared>(`/api/public/experiments/${encodeURIComponent(token)}`, { auth: false }).then(setD).catch(e => setErr(errText(e))) }, [token])
  if (err) return <div className="max-w-xl mx-auto mt-10"><Notice kind="error">{err}</Notice><a className={btnCls.outline} href="#/">Go to DeepOptima Studio</a></div>
  if (!d) return <Spinner />
  return (
    <div className="space-y-4">
      <div><span className="text-[11.5px] rounded-full bg-white px-2.5 py-0.5 text-gray-600">Shared result · read-only</span>
        <h1 className="text-[1.5rem] sm:text-[1.75rem] font-medium tracking-tight mt-2">{d.name}</h1>
        <p className="text-[13px] text-gray-500">Predicting “{d.target}” ({d.task}) · finished {dateOnly(d.finished_at)} · {d.config.families.length} model families searched</p></div>
      <SummaryCards trials={d.trials} result={d.result} metric={d.metric} baselineVal={d.baseline_score} />
      <div className={card}><h2 className="text-[15px] font-medium mb-3">Recommended models</h2><ModelsTable trials={d.trials} metric={d.metric} task={d.task} /></div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className={card}><h2 className="text-[15px] font-medium mb-2">Score vs speed vs size</h2><ParetoChart trials={d.trials} metric={d.metric} /></div>
        <div className={card}><h2 className="text-[15px] font-medium mb-3">What mattered most</h2>
          {d.result.importance?.length ? <Bars items={d.result.importance.slice(0, 10).map(i => ({ label: i.feature, value: i.importance }))} /> : <p className="text-[12.5px] text-gray-500">Not available.</p>}</div>
      </div>
      <div className={`${card} flex flex-wrap items-center gap-3`}><p className="text-[13px] text-gray-700 flex-1 min-w-[220px]">Have a table of your own? Upload a CSV and get the same kind of report in minutes. Free.</p><a className={btnCls.primary} href="#/register">Try DeepOptima Studio</a></div>
    </div>
  )
}
