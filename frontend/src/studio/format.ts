import type { Task } from './types'

export const METRICS: Record<Task, Record<string, string>> = {
  classification: { accuracy: 'Accuracy', balanced_accuracy: 'Balanced accuracy (best for imbalanced classes)', f1_macro: 'F1 score (macro average)' },
  regression: { r2: 'R² (1.0 is perfect)', neg_mae: 'Negative MAE (closer to 0 is better)', neg_rmse: 'Negative RMSE (closer to 0 is better)' },
}
export const FAMILIES: Record<string, { name: string; hint: string }> = {
  linear: { name: 'Linear / logistic', hint: 'Fast, tiny, easy to explain. Great baseline.' },
  tree: { name: 'Decision tree', hint: 'Simple rules. Very small and fast.' },
  rf: { name: 'Random forest', hint: 'Robust all-rounder. Larger models.' },
  hgb: { name: 'Gradient boosting', hint: 'Often the most accurate on tables.' },
  mlp: { name: 'Neural network', hint: 'Searches layer sizes (architecture search).' },
  knn: { name: 'k-nearest neighbours', hint: 'Compares to similar rows. Slow on big data.' },
}
export const METRIC_SHORT: Record<string, string> = { accuracy: 'accuracy', balanced_accuracy: 'balanced acc.', f1_macro: 'F1', r2: 'R²', neg_mae: '−MAE', neg_rmse: '−RMSE' }

export const isPct = (metric: string): boolean => ['accuracy', 'balanced_accuracy', 'f1_macro'].includes(metric)
export const fmtScore = (metric: string, v: number | null | undefined): string =>
  v === null || v === undefined ? '–' : isPct(metric) ? `${(v * 100).toFixed(1)}%` : v.toFixed(3)
export const fmtMs = (v: number | null | undefined): string => (v === null || v === undefined ? '–' : v < 10 ? v.toFixed(2) : v < 100 ? v.toFixed(1) : String(Math.round(v)))
export const fmtKb = (v: number | null | undefined): string => (v === null || v === undefined ? '–' : v < 1024 ? `${v < 10 ? v.toFixed(1) : Math.round(v)} KB` : `${(v / 1024).toFixed(1)} MB`)
export const fmtNum = (v: number | null | undefined): string => (v === null || v === undefined ? '–' : Math.abs(v) >= 1000 ? Math.round(v).toLocaleString() : String(Math.round(v * 1000) / 1000))

export function ago(iso: string | null | undefined): string {
  if (!iso) return ''
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return `${Math.floor(s / 86400)} d ago`
}
export const dateOnly = (iso: string | null | undefined): string => (iso ? new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '')
