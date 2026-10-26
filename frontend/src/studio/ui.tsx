import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import type { Status } from './types'

export const card = 'rounded-xl bg-[#EDEDED] p-5'
export const inputCls = 'w-full rounded-lg bg-white border border-gray-300 px-3 py-2 text-[13px] text-gray-900 outline-none focus:border-blue-400 disabled:opacity-60'
const btnBase = 'inline-flex items-center justify-center gap-2 rounded-full text-[13px] font-medium px-5 py-2.5 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed'
export const btnCls = {
  primary: `${btnBase} bg-blue-500 text-white hover:bg-blue-600`,
  outline: `${btnBase} text-blue-500 border border-blue-400 hover:bg-blue-500 hover:text-white hover:border-blue-500`,
  danger: `${btnBase} text-red-600 border border-red-300 hover:bg-red-500 hover:text-white hover:border-red-500`,
  ghost: `${btnBase} text-gray-700 hover:bg-white`,
}

export function Btn({ kind = 'primary', children, ...rest }: { kind?: keyof typeof btnCls; children: ReactNode; onClick?: () => void; disabled?: boolean; type?: 'button' | 'submit'; title?: string }) {
  return <button type="button" className={btnCls[kind]} {...rest}>{children}</button>
}

export function Field({ label, hint, error, children }: { label: string; hint?: string; error?: string; children: ReactNode }) {
  return (
    <label className="block mb-4">
      <span className="block text-[12.5px] font-medium text-gray-800 mb-1">{label}</span>
      {children}
      {hint && !error && <span className="block text-[11.5px] text-gray-500 mt-1">{hint}</span>}
      {error && <span className="block text-[11.5px] text-red-600 mt-1" role="alert">{error}</span>}
    </label>
  )
}

export function Notice({ kind = 'info', children }: { kind?: 'info' | 'error' | 'success' | 'warn'; children: ReactNode }) {
  const c = { info: 'bg-blue-50 border-blue-200 text-blue-900', error: 'bg-red-50 border-red-200 text-red-800', success: 'bg-green-50 border-green-200 text-green-800', warn: 'bg-amber-50 border-amber-200 text-amber-900' }[kind]
  return <div role={kind === 'error' ? 'alert' : 'status'} className={`rounded-lg border px-3.5 py-2.5 text-[12.5px] mb-4 ${c}`}>{children}</div>
}

export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return <div className="flex items-center gap-2 text-[13px] text-gray-500 py-6" role="status"><span className="inline-block w-4 h-4 rounded-full border-2 border-blue-400 border-t-transparent animate-spin" />{label}</div>
}

const STATUS: Record<Status, { t: string; c: string }> = {
  queued: { t: 'Queued', c: 'bg-gray-200 text-gray-700' }, running: { t: 'Running', c: 'bg-blue-100 text-blue-700' },
  done: { t: 'Done', c: 'bg-green-100 text-green-700' }, failed: { t: 'Failed', c: 'bg-red-100 text-red-700' }, cancelled: { t: 'Cancelled', c: 'bg-amber-100 text-amber-800' },
}
export function StatusBadge({ s }: { s: Status }) {
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-[11.5px] font-medium ${STATUS[s].c}`}>{STATUS[s].t}</span>
}

export function Chip({ children, tone = 'gray' }: { children: ReactNode; tone?: 'gray' | 'blue' | 'green' | 'amber' }) {
  const c = { gray: 'bg-white text-gray-700', blue: 'bg-blue-100 text-blue-700', green: 'bg-green-100 text-green-700', amber: 'bg-amber-100 text-amber-800' }[tone]
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-[11.5px] font-medium ${c}`}>{children}</span>
}

export function PageTitle({ title, sub, right }: { title: string; sub?: string; right?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3 mb-5">
      <div><h1 className="text-[1.5rem] sm:text-[1.75rem] leading-[1.15] font-medium text-gray-900 tracking-tight">{title}</h1>
        {sub && <p className="text-[13px] text-gray-500 mt-1 max-w-xl">{sub}</p>}</div>
      {right}
    </div>
  )
}

export function Meter({ label, used, max }: { label: string; used: number; max: number }) {
  const p = Math.min(100, Math.round((used / Math.max(max, 1)) * 100))
  return (
    <div>
      <div className="flex justify-between text-[12px] text-gray-600 mb-1"><span>{label}</span><span>{used} / {max}</span></div>
      <div className="h-2 rounded-full bg-white overflow-hidden"><div className={`h-full ${p >= 90 ? 'bg-amber-500' : 'bg-blue-500'}`} style={{ width: `${p}%` }} /></div>
    </div>
  )
}

export function Empty({ title, text, action }: { title: string; text: string; action?: ReactNode }) {
  return <div className={`${card} text-center py-10`}><p className="text-[15px] font-medium text-gray-900">{title}</p><p className="text-[13px] text-gray-500 mt-1 mb-4">{text}</p>{action}</div>
}

/** Tracks which async action is running; surfaces errors in one place. */
export function useAction() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const run = async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setBusy(true); setError('')
    try { return await fn() } catch (e) { setError(e instanceof Error ? e.message : 'Something went wrong.'); return undefined } finally { setBusy(false) }
  }
  return { busy, error, setError, run }
}

export function useTitle(t: string): void {
  useEffect(() => { document.title = `${t} · DeepOptima Studio` }, [t])
}
