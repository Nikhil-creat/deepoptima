import { useEffect, useState } from 'react'

export type Route =
  | { name: 'landing' } | { name: 'login' } | { name: 'register' } | { name: 'app' } | { name: 'datasets' } | { name: 'dataset'; id: number }
  | { name: 'new'; dataset?: number } | { name: 'experiment'; id: number } | { name: 'account' } | { name: 'share'; token: string }
  | { name: 'privacy' } | { name: 'terms' } | { name: 'help' } | { name: 'admin' } | { name: 'notfound' }

export function parseRoute(hash: string): Route {
  if (!hash.startsWith('#/')) return { name: 'landing' }
  const [path, query = ''] = hash.slice(1).split('?')
  const p = path.split('/').filter(Boolean)
  const num = (s: string | undefined): number => { const n = Number(s); return Number.isInteger(n) && n > 0 ? n : 0 }
  const q = new URLSearchParams(query)
  switch (p[0]) {
    case undefined: return { name: 'landing' }
    case 'login': return { name: 'login' }
    case 'register': return { name: 'register' }
    case 'app': return { name: 'app' }
    case 'datasets': return p[1] ? (num(p[1]) ? { name: 'dataset', id: num(p[1]) } : { name: 'notfound' }) : { name: 'datasets' }
    case 'new': return { name: 'new', dataset: num(q.get('dataset') ?? '') || undefined }
    case 'experiments': return num(p[1]) ? { name: 'experiment', id: num(p[1]) } : { name: 'app' }
    case 'account': return { name: 'account' }
    case 'share': return p[1] ? { name: 'share', token: p[1] } : { name: 'notfound' }
    case 'privacy': return { name: 'privacy' }
    case 'terms': return { name: 'terms' }
    case 'help': return { name: 'help' }
    case 'admin': return { name: 'admin' }
    default: return { name: 'notfound' }
  }
}

export function useRoute(): Route {
  const [r, setR] = useState<Route>(() => parseRoute(window.location.hash))
  useEffect(() => {
    const h = () => setR(parseRoute(window.location.hash))
    window.addEventListener('hashchange', h)
    return () => window.removeEventListener('hashchange', h)
  }, [])
  return r
}

export const navigate = (path: string): void => { window.location.hash = '#' + path }
export const PROTECTED = new Set(['app', 'datasets', 'dataset', 'new', 'experiment', 'account', 'admin'])
