import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api, getToken, setToken } from './api'
import { navigate } from './router'
import type { User } from './types'

interface AuthCtx { user: User | null; ready: boolean; signIn: (token: string, u: User) => void; signOut: () => void; setUser: (u: User) => void }
const Ctx = createContext<AuthCtx>({ user: null, ready: false, signIn: () => undefined, signOut: () => undefined, setUser: () => undefined })

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(false)
  useEffect(() => {
    if (!getToken()) { setReady(true); return }
    api<{ user: User }>('/api/me').then(r => setUser(r.user)).catch(() => setToken(null)).finally(() => setReady(true))
  }, [])
  useEffect(() => {
    const h = () => { setToken(null); setUser(null) }
    window.addEventListener('dopt:unauth', h)
    return () => window.removeEventListener('dopt:unauth', h)
  }, [])
  const value: AuthCtx = {
    user, ready, setUser,
    signIn: (t, u) => { setToken(t); setUser(u) },
    signOut: () => { setToken(null); setUser(null); navigate('/') },
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export const useAuth = (): AuthCtx => useContext(Ctx)
