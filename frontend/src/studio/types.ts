export interface User { id: number; email: string; name: string; is_admin: boolean; email_verified: boolean; created_at: string }
export interface ColumnInfo { name: string; kind: 'numeric' | 'categorical' | 'ignored'; dtype: string; missing_pct: number; n_unique: number; examples: string[]; min?: number | null; max?: number | null; mean?: number | null }
export interface TargetInfo { name: string; task_hint: 'classification' | 'regression'; n_unique: number; usable: boolean; reason: string; min_class_share: number | null }
export interface Profile { n_rows: number; n_cols: number; columns: ColumnInfo[]; targets: TargetInfo[]; warnings: string[] }
export interface Dataset { id: number; name: string; filename: string; n_rows: number; n_cols: number; created_at: string; profile?: Profile; preview?: Record<string, unknown>[] }
export interface Config { families: string[]; generations: number; population: number; time_limit_s: number; test_size: number; seed: number; exclude?: string[] }
export type Status = 'queued' | 'running' | 'done' | 'failed' | 'cancelled'
export type Task = 'classification' | 'regression'
export interface Experiment {
  id: number; name: string; dataset_id: number; dataset_name: string | null; target: string; task: Task; metric: string; config: Config
  status: Status; generation: number; total_generations: number; message: string; baseline_score: number | null; share_token: string | null
  created_at: string; started_at: string | null; finished_at: string | null
}
export interface Trial {
  id: number; gen: number; family: string; label: string; params: Record<string, unknown>; status: 'ok' | 'failed'; error: string | null
  score: number | null; test_score: number | null; latency_ms: number | null; size_kb: number | null; fit_seconds: number | null
  pareto_rank: number | null; is_final: boolean; blob_kb: number | null; ci_low: number | null; ci_high: number | null
}
export interface FeatureMeta { name: string; kind: 'numeric' | 'categorical'; min?: number; max?: number; median?: number; values?: string[] }
export interface Result {
  n_train?: number; n_val?: number; n_test?: number; n_features?: number; notes?: string[]; classes?: string[]
  importance?: { feature: string; importance: number }[]; features?: FeatureMeta[]; sklearn_version?: string
  baseline_test?: number; best_trial_id?: number | null; stopped?: string; cv?: boolean; diagnostics?: Diagnostics | null
}
export type Diagnostics =
  | { kind: 'confusion'; labels: string[]; matrix: number[][] }
  | { kind: 'regression'; mae: number; rmse: number; scatter: number[][] }
export interface ExperimentDetail extends Experiment { result: Result | null; trials: Trial[] }
export interface ApiKeyInfo { id: number; name: string; prefix: string; created_at: string; last_used_at: string | null }
export interface Limits { max_upload_mb: number; max_rows: number; max_cols: number; max_datasets: number; max_experiments: number; max_time_limit_s: number; registration_open: boolean }
