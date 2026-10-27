import type { ReactNode } from 'react'
import { fmtKb, fmtMs, fmtScore, METRIC_SHORT } from './format'
import type { Result, Task, Trial } from './types'
import { card, Chip } from './ui'

export const finalsOf = (trials: Trial[]): Trial[] => trials.filter(t => t.is_final && t.test_score !== null).sort((a, b) => (b.test_score as number) - (a.test_score as number))

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) {
  return <div className={card}><p className="text-[12px] text-gray-500">{label}</p><p className="text-[1.5rem] leading-tight font-medium text-gray-900">{value}</p>{sub && <p className="text-[11.5px] text-gray-500 mt-0.5">{sub}</p>}</div>
}

export function SummaryCards({ trials, result, metric, baselineVal }: { trials: Trial[]; result: Result | null; metric: string; baselineVal: number | null }) {
  const finals = finalsOf(trials)
  const best = finals[0]
  const ok = trials.filter(t => t.status === 'ok')
  const front = ok.filter(t => t.pareto_rank === 0).length
  const base = result?.baseline_test ?? baselineVal
  const gain = best && base !== null && base !== undefined ? (best.test_score as number) - base : null
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <Stat label={`Best test ${METRIC_SHORT[metric] ?? 'score'}`} value={fmtScore(metric, best?.test_score)} sub="on data the models never saw" />
      <Stat label="Simple baseline" value={fmtScore(metric, base)} sub={gain !== null ? `best model is ${gain >= 0 ? '+' : ''}${fmtScore(metric, gain).replace('%', ' pts')} better` : 'always guesses the common answer'} />
      <Stat label="Models tried" value={ok.length} sub={trials.length > ok.length ? `${trials.length - ok.length} failed safely` : undefined} />
      <Stat label="Best trade-offs" value={front} sub="models not beaten on score, speed and size" />
    </div>
  )
}

export function ModelsTable({ trials, metric, task, selected, onSelect, action }: { trials: Trial[]; metric: string; task: Task; selected?: number | null; onSelect?: (t: Trial) => void; action?: (t: Trial) => ReactNode }) {
  const finals = finalsOf(trials)
  if (!finals.length) return null
  const fastest = finals.reduce((a, b) => ((b.latency_ms as number) < (a.latency_ms as number) ? b : a))
  const smallest = finals.reduce((a, b) => ((b.size_kb as number) < (a.size_kb as number) ? b : a))
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-[12.5px]">
        <thead><tr className="text-gray-500"><th className="pb-2 pr-3 font-medium">Model</th><th className="pb-2 pr-3 font-medium">Test {METRIC_SHORT[metric] ?? 'score'}</th><th className="pb-2 pr-3 font-medium">Search score</th>
          <th className="pb-2 pr-3 font-medium whitespace-nowrap">ms / 1,000 rows</th><th className="pb-2 pr-3 font-medium">Size</th><th className="pb-2 font-medium" /></tr></thead>
        <tbody>{finals.map((t, i) => (
          <tr key={t.id} className={`border-t border-gray-300 align-top ${selected === t.id ? 'bg-white/60' : ''}`}>
            <td className="py-2 pr-3 min-w-[190px]"><p className="font-medium text-gray-900">{t.label}</p>
              <div className="flex flex-wrap gap-1 mt-1">{i === 0 && <Chip tone="blue">Most accurate</Chip>}{t.id === fastest.id && <Chip tone="green">Fastest</Chip>}{t.id === smallest.id && <Chip tone="amber">Smallest</Chip>}</div></td>
            <td className="py-2 pr-3 font-medium whitespace-nowrap">{fmtScore(metric, t.test_score)}{t.ci_low != null && t.ci_high != null && <span className="block text-[10.5px] font-normal text-gray-500">95% range {fmtScore(metric, t.ci_low)} – {fmtScore(metric, t.ci_high)}</span>}</td>
            <td className="py-2 pr-3 text-gray-600 whitespace-nowrap">{fmtScore(metric, t.score)}</td>
            <td className="py-2 pr-3 whitespace-nowrap">{fmtMs(t.latency_ms)}</td>
            <td className="py-2 pr-3 whitespace-nowrap">{fmtKb(t.blob_kb ?? t.size_kb)}</td>
            <td className="py-2 whitespace-nowrap">{onSelect && <button className={`text-[12px] ${selected === t.id ? 'text-gray-500' : 'text-blue-600 hover:underline'}`} onClick={() => onSelect(t)} disabled={selected === t.id}>{selected === t.id ? 'Selected' : 'Use this'}</button>}{action?.(t)}</td>
          </tr>
        ))}</tbody>
      </table>
      <p className="text-[11.5px] text-gray-500 mt-2">{task === 'classification' ? 'Higher is better.' : 'Higher (closer to the top) is better.'} “Test” scores come from rows kept aside from the start; “search score” is what the search used to compare models.</p>
    </div>
  )
}

export function TrialsTable({ trials, metric }: { trials: Trial[]; metric: string }) {
  const rows = [...trials].sort((a, b) => (b.score ?? -Infinity) - (a.score ?? -Infinity))
  return (
    <div className="overflow-x-auto max-h-80 overflow-y-auto">
      <table className="w-full text-left text-[12px]">
        <thead className="text-gray-500 sticky top-0 bg-[#EDEDED]"><tr><th className="pb-2 pr-3 font-medium">Model</th><th className="pb-2 pr-3 font-medium">Gen</th><th className="pb-2 pr-3 font-medium">Score</th><th className="pb-2 pr-3 font-medium">ms/1k</th><th className="pb-2 pr-3 font-medium">Size</th><th className="pb-2 font-medium">Front</th></tr></thead>
        <tbody>{rows.map(t => (
          <tr key={t.id} className="border-t border-gray-300"><td className="py-1.5 pr-3 text-gray-800">{t.label}{t.status === 'failed' && <span className="text-red-600"> · failed</span>}</td><td className="py-1.5 pr-3">{t.gen + 1}</td>
            <td className="py-1.5 pr-3">{fmtScore(metric, t.score)}</td><td className="py-1.5 pr-3">{fmtMs(t.latency_ms)}</td><td className="py-1.5 pr-3">{fmtKb(t.size_kb)}</td><td className="py-1.5">{t.pareto_rank === 0 ? '●' : ''}</td></tr>
        ))}</tbody>
      </table>
    </div>
  )
}
