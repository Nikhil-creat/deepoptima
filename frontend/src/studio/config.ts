import { useEffect, useState } from 'react'
import { api } from './api'
import type { Limits } from './types'

export interface ServerConfig { email_enabled: boolean; require_verification: boolean; limits?: Limits; version?: string }
let pending: Promise<ServerConfig> | null = null

export function loadServerConfig(): Promise<ServerConfig> {
  if (!pending) {
    pending = api<ServerConfig>('/api/config', { auth: false }).catch(() => { pending = null; return { email_enabled: false, require_verification: false } })
  }
  return pending
}

export function useServerConfig(): ServerConfig | null {
  const [c, setC] = useState<ServerConfig | null>(null)
  useEffect(() => {
    let live = true
    void loadServerConfig().then(x => { if (live) setC(x) })
    return () => { live = false }
  }, [])
  return c
}
