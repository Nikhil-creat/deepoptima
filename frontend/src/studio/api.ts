const envBase: string = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/+$/, '') ?? ''
let base = envBase
export const getBase = (): string => base

/** The API address comes from VITE_API_URL at build time, or from /config.json at run time (edit frontend/public/config.json, no rebuild settings needed). */
export const ready: Promise<void> = envBase
  ? Promise.resolve()
  : fetch('/config.json', { cache: 'no-store' }).then(r => (r.ok ? r.json() : null)).then((c: { apiUrl?: string } | null) => {
      const u = (c?.apiUrl ?? '').trim().replace(/\/+$/, '')
      if (/^https:\/\/[^\s/]+$/.test(u) || /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(u)) base = u
    }).catch(() => undefined)
const TOKEN_KEY = 'dopt_token'

let token: string | null = (() => { try { return localStorage.getItem(TOKEN_KEY) } catch { return null } })()
export const getToken = (): string | null => token
export function setToken(t: string | null): void {
  token = t
  try { if (t) localStorage.setItem(TOKEN_KEY, t); else localStorage.removeItem(TOKEN_KEY) } catch { /* storage unavailable */ }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
}

function detailText(d: unknown): string {
  if (typeof d === 'string') return d
  if (Array.isArray(d)) {
    return d.slice(0, 3).map((x: { loc?: unknown[]; msg?: string }) => {
      const loc = Array.isArray(x?.loc) && x.loc.length ? String(x.loc[x.loc.length - 1]) : ''
      return `${loc ? loc + ': ' : ''}${x?.msg ?? 'invalid value'}`
    }).join('; ')
  }
  return 'Request failed.'
}

async function fail(r: Response): Promise<never> {
  let msg = `Request failed (${r.status}).`
  try { const j = await r.json(); msg = detailText(j.detail) } catch { /* not JSON */ }
  if (r.status === 401 && token) window.dispatchEvent(new Event('dopt:unauth'))
  throw new ApiError(r.status, msg)
}

export async function api<T = unknown>(path: string, o: { method?: string; body?: unknown; form?: FormData; auth?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = {}
  if (token && o.auth !== false) headers.Authorization = `Bearer ${token}`
  let body: BodyInit | undefined
  if (o.form) body = o.form
  else if (o.body !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(o.body) }
  await ready
  let r: Response
  try { r = await fetch(base + path, { method: o.method ?? (body ? 'POST' : 'GET'), headers, body }) }
  catch { throw new ApiError(0, 'Cannot reach the server. Check your connection and try again.') }
  if (!r.ok) return fail(r)
  return (r.status === 204 ? undefined : await r.json()) as T
}

/** Fetch a file with the auth header and save it. */
export async function download(path: string, filename: string, form?: FormData): Promise<void> {
  const headers: Record<string, string> = {}
  if (token) headers.Authorization = `Bearer ${token}`
  await ready
  let r: Response
  try { r = await fetch(base + path, { method: form ? 'POST' : 'GET', headers, body: form }) }
  catch { throw new ApiError(0, 'Cannot reach the server. Check your connection and try again.') }
  if (!r.ok) return fail(r)
  const url = URL.createObjectURL(await r.blob())
  const a = document.createElement('a')
  a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 2000)
}

export const errText = (e: unknown): string => (e instanceof Error ? e.message : 'Something went wrong.')
