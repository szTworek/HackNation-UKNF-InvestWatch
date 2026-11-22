import { useCallback, useEffect, useState, useSyncExternalStore } from 'react'
import type { Alert, Entity, Finding, Item, MonitoredPage, Overview, PageChange, PageSnapshot } from './types'

export const API_URL = (import.meta.env.VITE_API_URL as string | undefined) || 'http://localhost:8000'

export type DataMode = 'live' | 'fixtures'
type Pref = 'auto' | DataMode

interface Fixtures {
  generated_at: string
  entities: (Entity & { modules: unknown; platforms: unknown })[]
  items: Item[]
  findings: Finding[]
  pages: { page_id: string; entity_id: string; url: string; label: string }[]
  snapshots: PageSnapshot[]
  changes: PageChange[]
  alerts: Alert[]
  overview: Overview
}

// ---------- mode store ----------
const readPref = (): Pref => {
  try { return (localStorage.getItem('iw-mode') as Pref) || 'auto' } catch { return 'auto' }
}
let state: { pref: Pref; mode: DataMode; probing: boolean; version: number } = { pref: readPref(), mode: 'fixtures', probing: true, version: 0 }
const subs = new Set<() => void>()
const emit = (patch: Partial<typeof state>) => { state = { ...state, ...patch }; subs.forEach((f) => f()) }

async function probe(): Promise<boolean> {
  try {
    const ctl = new AbortController()
    const t = setTimeout(() => ctl.abort(), 1500)
    const r = await fetch(`${API_URL}/api/entities`, { signal: ctl.signal })
    clearTimeout(t)
    return r.ok
  } catch { return false }
}

export async function resolveMode(pref: Pref = state.pref) {
  try { localStorage.setItem('iw-mode', pref) } catch { /* ignore */ }
  if (pref !== 'auto') { emit({ pref, mode: pref, probing: false, version: state.version + 1 }); return }
  emit({ pref, probing: true })
  const ok = await probe()
  emit({ mode: ok ? 'live' : 'fixtures', probing: false, version: state.version + 1 })
}
resolveMode()

export function useDataMode() {
  return useSyncExternalStore((f) => { subs.add(f); return () => subs.delete(f) }, () => state)
}
export const bumpData = () => emit({ version: state.version + 1 })

// ---------- fixtures router ----------
let fxPromise: Promise<Fixtures> | null = null
const fixtures = () => (fxPromise ??= import('./mocks/fixtures.json').then((m) => structuredClone(m.default) as unknown as Fixtures))

function withFindings(fx: Fixtures, it: Item) {
  return { ...it, findings: fx.findings.filter((f) => f.item_id === it.id) }
}

async function fixtureGet(path: string, method: string): Promise<unknown> {
  const fx = await fixtures()
  const url = new URL(path, 'http://x')
  const p = url.pathname.replace(/^\/api/, '').split('/').filter(Boolean)
  const q = url.searchParams
  const notFound = () => { throw new Error(`Not found: ${path}`) }

  if (method === 'POST') {
    if (p[0] === 'alerts' && p[2] === 'ack') {
      const a = fx.alerts.find((x) => x.id === p[1]) ?? notFound()
      a.status = 'ack'
      fx.overview.totals.alerts_new = fx.alerts.filter((x) => x.status === 'new').length
      const e = fx.entities.find((x) => x.id === a.entity_id)
      if (e) e.kpis.alerts_new = fx.alerts.filter((x) => x.status === 'new' && x.entity_id === e.id).length
      return a
    }
    if (p[0] === 'scan') return { items_new: 0, findings_new: 0, alerts_new: 0 }
    return notFound()
  }
  if (p[0] === 'entities') {
    if (!p[1]) return fx.entities.map(({ modules: _m, platforms: _p, ...e }) => e)
    const e = fx.entities.find((x) => x.id === p[1]) ?? notFound()
    if (!p[2]) return e
    if (p[2] === 'items') {
      let items = fx.items.filter((i) => i.entity_ids.includes(e.id))
      const ch = q.get('channel'), pl = q.get('platform'), mod = q.get('module')
      if (ch) items = items.filter((i) => i.channel === ch)
      if (pl) items = items.filter((i) => i.platform === pl)
      let rows = items.map((i) => withFindings(fx, i))
      if (mod) rows = rows.filter((i) => i.findings.some((f) => f.module === mod))
      const off = Number(q.get('offset') || 0), lim = Number(q.get('limit') || 50)
      return { total: rows.length, items: rows.slice(off, off + lim) }
    }
    if (p[2] === 'pages') {
      return fx.pages.filter((pg) => pg.entity_id === e.id).map((pg) => ({
        page_id: pg.page_id, url: pg.url, label: pg.label,
        last_snapshot: fx.snapshots.filter((s) => s.page_id === pg.page_id).sort((a, b) => b.fetched_at.localeCompare(a.fetched_at))[0] ?? null,
        changes: fx.changes.filter((c) => c.page_id === pg.page_id),
      })) satisfies MonitoredPage[]
    }
  }
  if (p[0] === 'items' && p[1]) return withFindings(fx, fx.items.find((i) => i.id === p[1]) ?? notFound())
  if (p[0] === 'changes' && p[1]) {
    const c = fx.changes.find((x) => x.id === p[1]) ?? notFound()
    return { ...c, from: fx.snapshots.find((s) => s.id === c.from_snapshot), to: fx.snapshots.find((s) => s.id === c.to_snapshot) }
  }
  if (p[0] === 'alerts') {
    let a = fx.alerts
    for (const k of ['status', 'entity_id', 'severity'] as const) { const v = q.get(k); if (v) a = a.filter((x) => x[k] === v) }
    return a
  }
  if (p[0] === 'metrics' && p[1] === 'overview') return fx.overview
  return notFound()
}

// ---------- public API ----------
export async function request<T>(path: string, method = 'GET'): Promise<T> {
  if (state.mode === 'fixtures') return (await fixtureGet(path, method)) as T
  const r = await fetch(`${API_URL}${path}`, { method })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} — ${path}`)
  return r.json() as Promise<T>
}

export function useApi<T>(path: string | null) {
  const { mode, probing, version } = useDataMode()
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    if (probing || !path) return
    let alive = true
    setLoading(true)
    setError(null)
    request<T>(path)
      .then((d) => { if (alive) setData(d) })
      .catch((e: Error) => { if (alive) { setError(e.message); setData(null) } })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [path, mode, probing, version, tick])
  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, error, loading: loading || probing, reload, setData }
}
