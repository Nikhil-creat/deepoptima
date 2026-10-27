import type { Trial } from './types'
import { fmtMs, fmtScore } from './format'

interface Pt { t: Trial; x: number; y: number }

/** Score (higher = better) vs prediction time (lower = better). Dot size = model file size. Blue = Pareto-optimal. */
export function ParetoChart({ trials, metric, selectedId, onSelect }: { trials: Trial[]; metric: string; selectedId?: number | null; onSelect?: (t: Trial) => void }) {
  const ok = trials.filter(t => t.status === 'ok' && t.score !== null && t.latency_ms !== null && t.size_kb !== null)
  const W = 460, H = 280, L = 48, R = 14, T = 14, B = 44
  if (ok.length < 2) return <div className="h-[220px] flex items-center justify-center text-[13px] text-gray-500 text-center px-6">The chart appears as soon as a few models have been tried.</div>
  const lat = ok.map(t => t.latency_ms as number)
  const lo = Math.min(...lat), hi = Math.max(...lat)
  const useLog = hi / Math.max(lo, 1e-6) > 20
  const tx = (v: number): number => (useLog ? Math.log10(Math.max(v, 1e-6)) : v)
  const x0 = tx(lo), x1 = tx(hi)
  const ys = ok.map(t => t.score as number)
  const ya = Math.min(...ys), yb = Math.max(...ys), pad = (yb - ya || 0.02) * 0.12
  const y0 = ya - pad, y1 = yb + pad
  const X = (v: number): number => L + ((tx(v) - x0) / (x1 - x0 || 1)) * (W - L - R)
  const Y = (v: number): number => H - B - ((v - y0) / (y1 - y0 || 1)) * (H - B - T)
  const sizes = ok.map(t => Math.log10(Math.max(t.size_kb as number, 0.5)))
  const s0 = Math.min(...sizes), s1 = Math.max(...sizes)
  const rad = (t: Trial): number => 3 + 5 * ((Math.log10(Math.max(t.size_kb as number, 0.5)) - s0) / (s1 - s0 || 1))
  const pts: Pt[] = ok.map(t => ({ t, x: X(t.latency_ms as number), y: Y(t.score as number) }))
  const sorted = [...ok].sort((a, b) => (a.latency_ms as number) - (b.latency_ms as number) || (b.score as number) - (a.score as number))
  const stair: Trial[] = []
  let top = -Infinity
  for (const t of sorted) if ((t.score as number) > top) { stair.push(t); top = t.score as number }
  let line = ''
  stair.forEach((t, i) => { line += i === 0 ? `M${X(t.latency_ms as number)},${Y(t.score as number)}` : `H${X(t.latency_ms as number)}V${Y(t.score as number)}` })
  line += `H${W - R}`
  const area = `${line}V${H - B}H${X(stair[0].latency_ms as number)}Z`
  const front = pts.filter(p => p.t.pareto_rank === 0), rest = pts.filter(p => p.t.pareto_rank !== 0)
  const ticks = [0, 1, 2, 3]
  const xv = (i: number): number => { const v = x0 + (i / 3) * (x1 - x0); return useLog ? Math.pow(10, v) : v }
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Chart of model score against prediction time. Blue dots are the best trade-offs.">
        <defs><linearGradient id="pfill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#3b82f6" stopOpacity="0.25" /><stop offset="1" stopColor="#3b82f6" stopOpacity="0" /></linearGradient></defs>
        {ticks.map(i => {
          const gy = T + (i / 3) * (H - B - T), gx = L + (i / 3) * (W - L - R)
          return (
            <g key={i}>
              <line x1={L} x2={W - R} y1={gy} y2={gy} stroke="#d1d5db" strokeWidth="0.6" />
              <line x1={gx} x2={gx} y1={T} y2={H - B} stroke="#d1d5db" strokeWidth="0.6" />
              <text x={L - 6} y={gy + 3} fontSize="9" fill="#6b7280" textAnchor="end">{fmtScore(metric, y1 - (i / 3) * (y1 - y0))}</text>
              <text x={gx} y={H - B + 14} fontSize="9" fill="#6b7280" textAnchor="middle">{fmtMs(xv(i))}</text>
            </g>
          )
        })}
        <text x={(L + W - R) / 2} y={H - 6} fontSize="10" fill="#6b7280" textAnchor="middle">prediction time (ms per 1,000 rows){useLog ? ', log scale' : ''} → faster is left</text>
        <text x={11} y={(T + H - B) / 2} fontSize="10" fill="#6b7280" textAnchor="middle" transform={`rotate(-90 11 ${(T + H - B) / 2})`}>score ↑ better</text>
        <path d={area} fill="url(#pfill)" />
        <path d={line} fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinejoin="round" />
        {rest.map(p => <circle key={p.t.id} cx={p.x} cy={p.y} r={rad(p.t)} fill="#9ca3af" opacity="0.45" />)}
        {front.map(p => <circle key={p.t.id} cx={p.x} cy={p.y} r={rad(p.t)} fill="#3b82f6" opacity="0.9" />)}
        {selectedId ? pts.filter(p => p.t.id === selectedId).map(p => <circle key={`s${p.t.id}`} cx={p.x} cy={p.y} r={rad(p.t) + 4} fill="none" stroke="#111827" strokeWidth="1.5" />) : null}
        {onSelect ? pts.map(p => <circle key={`h${p.t.id}`} cx={p.x} cy={p.y} r="11" fill="transparent" className="cursor-pointer" onClick={() => onSelect(p.t)} />) : null}
      </svg>
      <p className="text-[11.5px] text-gray-500 mt-1"><span className="text-blue-500">●</span> best trade-offs (Pareto-optimal) · <span className="text-gray-400">●</span> other models · bigger dot = bigger file</p>
    </div>
  )
}

export function Bars({ items }: { items: { label: string; value: number }[] }) {
  const max = Math.max(...items.map(i => i.value), 1e-9)
  return (
    <ul className="space-y-1.5">
      {items.map(i => (
        <li key={i.label} className="flex items-center gap-3 text-[12.5px]">
          <span className="w-32 sm:w-44 truncate text-gray-700" title={i.label}>{i.label}</span>
          <span className="flex-1 h-2.5 rounded-full bg-white overflow-hidden"><span className="block h-full bg-blue-500" style={{ width: `${Math.max(2, (i.value / max) * 100)}%` }} /></span>
          <span className="w-12 text-right text-gray-500">{i.value.toFixed(3)}</span>
        </li>
      ))}
    </ul>
  )
}

export function ProgressBar({ value, tone = 'blue' }: { value: number; tone?: 'blue' | 'green' | 'red' }) {
  const c = { blue: 'bg-blue-500', green: 'bg-green-500', red: 'bg-red-400' }[tone]
  return <div className="h-2.5 rounded-full bg-white overflow-hidden" role="progressbar" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100}><div className={`h-full ${c} transition-all duration-500`} style={{ width: `${Math.max(2, Math.min(100, value))}%` }} /></div>
}

/** Rows = what was true, columns = what the model said. Green diagonal = correct. */
export function ConfusionMatrix({ labels, matrix }: { labels: string[]; matrix: number[][] }) {
  const totals = matrix.map(r => r.reduce((a, b) => a + b, 0))
  return (
    <div className="overflow-x-auto">
      <table className="text-[12px] border-separate border-spacing-1">
        <thead><tr><th />{labels.map(l => <th key={l} className="px-2 font-medium text-gray-600 max-w-[90px] truncate" title={`predicted ${l}`}>{l}</th>)}</tr></thead>
        <tbody>{matrix.map((row, i) => (
          <tr key={labels[i]}>
            <th className="pr-2 text-right font-medium text-gray-600 max-w-[90px] truncate" title={`actual ${labels[i]}`}>{labels[i]}</th>
            {row.map((v, j) => {
              const share = totals[i] ? v / totals[i] : 0
              return <td key={labels[j]} className="text-center rounded px-3 py-2 text-gray-900" title={`${v} rows (${Math.round(share * 100)}% of actual “${labels[i]}”)`}
                style={{ background: i === j ? `rgba(34,197,94,${0.12 + 0.7 * share})` : `rgba(239,68,68,${0.75 * share})` }}>{v}</td>
            })}
          </tr>
        ))}</tbody>
      </table>
      <p className="text-[11.5px] text-gray-500 mt-2">Rows: actual value · columns: model’s answer · computed on the held-out test rows.</p>
    </div>
  )
}

export function ActualVsPredicted({ points }: { points: number[][] }) {
  const W = 360, H = 260, L = 44, R = 12, T = 10, B = 36
  if (points.length < 2) return null
  const all = points.flat()
  const lo = Math.min(...all), hi = Math.max(...all), span = hi - lo || 1
  const X = (v: number): number => L + ((v - lo) / span) * (W - L - R)
  const Y = (v: number): number => H - B - ((v - lo) / span) * (H - B - T)
  const fmt = (v: number): string => (Math.abs(v) >= 1000 ? String(Math.round(v)) : String(Math.round(v * 100) / 100))
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Predicted against actual values on the test rows">
        <line x1={L} y1={H - B} x2={W - R} y2={H - B} stroke="#9ca3af" /><line x1={L} y1={T} x2={L} y2={H - B} stroke="#9ca3af" />
        <line x1={X(lo)} y1={Y(lo)} x2={X(hi)} y2={Y(hi)} stroke="#3b82f6" strokeDasharray="4 3" />
        {points.map((p, i) => <circle key={i} cx={X(p[0])} cy={Y(p[1])} r="2.6" fill="#3b82f6" opacity="0.5" />)}
        {[0, 1, 2].map(i => { const v = lo + (i / 2) * span; return <g key={i}><text x={X(v)} y={H - B + 14} fontSize="9" fill="#6b7280" textAnchor="middle">{fmt(v)}</text><text x={L - 5} y={Y(v) + 3} fontSize="9" fill="#6b7280" textAnchor="end">{fmt(v)}</text></g> })}
        <text x={(L + W - R) / 2} y={H - 4} fontSize="10" fill="#6b7280" textAnchor="middle">actual →</text>
        <text x={10} y={(T + H - B) / 2} fontSize="10" fill="#6b7280" textAnchor="middle" transform={`rotate(-90 10 ${(T + H - B) / 2})`}>predicted ↑</text>
      </svg>
      <p className="text-[11.5px] text-gray-500">Dots on the dashed line would be perfect predictions.</p>
    </div>
  )
}
