import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import clsx from 'clsx'
import { ArrowLeft, ChevronRight, ExternalLink, FileText, ShieldAlert, ShieldCheck } from 'lucide-react'
import { request, useApi, useDataMode } from '../api'
import { FindingsByDay, HBars, PlatformDonut, daysFromFindings } from '../charts'
import type { Alert, Entity, EntityDetail, Finding, ItemWithFindings, ItemsPage, MonitoredPage, Module } from '../types'
import {
  CATEGORY_LABEL, Card, Empty, ErrorBox, Kpi, Loading, MODULE_INFO, MODULES, MockTag, ModuleBadge, PLATFORM_INFO, Pill, PlatformBadge,
  RiskRing, Select, SeverityBadge, Skeleton, fmtAgo, fmtDate, platformLabel, shortUrl,
  kindLabel,
} from '../ui'
import { AlertList } from './Alerts'
import { DiffView, Drawer, ItemView } from './parts'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'websites', label: 'Websites' },
  { id: 'social', label: 'Social & ads' },
  { id: 'findings', label: 'Findings' },
  { id: 'alerts', label: 'Alerts' },
] as const

export function useEntityItems(id: string) {
  const { mode, probing, version } = useDataMode()
  const [items, setItems] = useState<ItemWithFindings[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    if (probing) return
    let alive = true
    setLoading(true); setError(null)
    ;(async () => {
      const all: ItemWithFindings[] = []
      for (let off = 0, total = 1; off < total; off += 500) {
        const r = await request<ItemsPage>(`/api/entities/${id}/items?limit=500&offset=${off}`)
        all.push(...r.items); total = r.total
        if (!r.items.length) break
      }
      return all
    })().then((a) => { if (alive) setItems(a) }).catch((e: Error) => { if (alive) setError(e.message) }).finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [id, mode, probing, version, tick])
  const findings = useMemo(() => (items ?? []).flatMap((i) => i.findings.filter((f) => f.entity_id === id).map((f) => ({ ...f, item: i }))), [items, id])
  return { findings, error, loading: loading || probing, reload: () => setTick((t) => t + 1) }
}

export default function EntityPage() {
  const { id = '' } = useParams()
  const [sp, setSp] = useSearchParams()
  const tab = sp.get('tab') ?? 'overview'
  const ent = useApi<EntityDetail>(`/api/entities/${id}`)
  const e = ent.data
  const set = (patch: Record<string, string | null>) => {
    const n = new URLSearchParams(sp)
    Object.entries(patch).forEach(([k, v]) => (v === null ? n.delete(k) : n.set(k, v)))
    setSp(n, { replace: false })
  }
  const item = sp.get('item'), change = sp.get('change'), finding = sp.get('finding')

  if (ent.error) return <ErrorBox error={ent.error} onRetry={ent.reload} />
  return (
    <div>
      <Link to="/entities" className="mb-3 inline-flex items-center gap-1 text-xs text-muted hover:text-ink"><ArrowLeft className="h-3.5 w-3.5" /> All entities</Link>
      {!e ? <Skeleton className="h-36" /> : (
        <div className="flex flex-wrap items-start gap-5 rounded-md border border-line bg-panel p-5">
          <RiskRing score={e.kpis.risk_score} size={76} />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight">{e.name}</h1>
              {e.domains.map((d) => <a key={d} href={`https://${d}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs text-muted hover:text-accent">{d}<ExternalLink className="h-3 w-3" /></a>)}
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {e.registry_entries.map((r) => (
                <span key={r.name} className="inline-flex items-center gap-1.5 rounded border border-line bg-panel-2 px-2 py-1 text-xs">
                  <b>{r.name}</b> <span className="text-muted">· {CATEGORY_LABEL[r.category] ?? r.category} · {r.country}</span>
                </span>
              ))}
            </div>
            <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted">
              {Object.entries(e.social_handles).map(([p, h]) => <span key={p}><PlatformBadge p={p} /> @{h}</span>)}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[['Items', e.kpis.items], ['Open findings', e.kpis.findings_open], ['New alerts', e.kpis.alerts_new], ['Pages', e.monitored_pages]].map(([l, v]) => (
              <div key={l} className="rounded bg-panel-2 px-3 py-2 text-center"><div className="text-lg font-semibold tabular">{v}</div><div className="text-[11px] text-muted">{l}</div></div>
            ))}
          </div>
          <Link to={`/reports/${e.id}`} className="no-print inline-flex items-center gap-1.5 self-center rounded border border-line px-3 py-1.5 text-xs font-medium hover:border-accent hover:text-accent"><FileText className="h-3.5 w-3.5" /> Report</Link>
        </div>
      )}

      <nav role="tablist" className="mt-5 flex gap-1 overflow-x-auto border-b border-line [scrollbar-width:none]">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => set({ tab: t.id, item: null, change: null, finding: null })}
            className={clsx('-mb-px whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-medium', tab === t.id ? 'border-accent text-accent' : 'border-transparent text-muted hover:text-ink')}>{t.label}</button>
        ))}
      </nav>

      <div className="mt-5">
        {tab === 'overview' && e && <OverviewTab e={e} />}
        {tab === 'websites' && <WebsitesTab id={id} onChange={(c) => set({ change: c })} />}
        {tab === 'social' && <SocialTab id={id} onItem={(i) => set({ item: i })} />}
        {tab === 'findings' && <FindingsTab id={id} onItem={(i, f) => set({ item: i, finding: f })} focus={finding} />}
        {tab === 'alerts' && <AlertsTab id={id} />}
      </div>

      <Drawer open={!!item} onClose={() => set({ item: null, finding: null })} title={<div className="text-sm font-semibold">Item detail</div>}>
        {item && <ItemView id={item} focusFinding={finding} />}
      </Drawer>
      <Drawer wide open={!!change} onClose={() => set({ change: null })} title={<div className="text-sm font-semibold">Page change · side-by-side diff</div>}>
        {change && <DiffView id={change} />}
      </Drawer>
      {finding && !item && <FindingOpener id={id} finding={finding} onItem={(i) => set({ item: i })} />}
    </div>
  )
}

function FindingOpener({ id, finding, onItem }: { id: string; finding: string; onItem: (i: string) => void }) {
  const { findings } = useEntityItems(id)
  const itemId = findings.find((x) => x.id === finding)?.item_id
  useEffect(() => { if (itemId) onItem(itemId) }, [itemId]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

function OverviewTab({ e }: { e: EntityDetail }) {
  const { findings, loading } = useEntityItems(e.id)
  const trend = useMemo(() => daysFromFindings(findings), [findings])
  const rules = useMemo(() => {
    const m = new Map<string, { label: string; n: number }>()
    findings.forEach((f) => f.rule_hits.forEach((h) => { const x = m.get(h.rule_id) ?? { label: h.label, n: 0 }; x.n++; m.set(h.rule_id, x) }))
    return [...m.entries()].sort((a, b) => b[1].n - a[1].n).slice(0, 6)
  }, [findings])
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-3">
        {MODULES.map((m) => (
          <div key={m} className="rounded-md border border-line bg-panel p-4">
            <div className="flex items-center gap-2"><ModuleBadge m={m} /><span className="text-sm font-medium">{MODULE_INFO[m].name}</span></div>
            <p className="mt-1 text-xs text-muted">{MODULE_INFO[m].desc}</p>
            <div className="mt-3 flex items-end justify-between">
              <div><div className="text-2xl font-semibold tabular">{e.modules[m]?.findings ?? 0}</div><div className="text-[11px] text-muted">findings</div></div>
              <div className="text-right"><div className="text-lg font-semibold tabular">{e.modules[m]?.findings ? Math.round(e.modules[m].avg_score * 100) : '—'}</div><div className="text-[11px] text-muted">avg score</div></div>
            </div>
            <div className="mt-2 h-1.5 rounded-full bg-panel-2"><div className="h-1.5 rounded-full" style={{ width: `${(e.modules[m]?.avg_score ?? 0) * 100}%`, background: MODULE_INFO[m].color }} /></div>
          </div>
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <Card title="Findings trend" subtitle="Per day, stacked by module" className="xl:col-span-2">
          {loading && !findings.length ? <Skeleton className="h-[240px]" /> : <FindingsByDay data={trend} />}
        </Card>
        <Card title="Platform mix">
          {Object.keys(e.platforms).length ? <PlatformDonut data={e.platforms} height={170} /> : <Empty title="No items yet" />}
        </Card>
      </div>
      <Card title="Most frequent rule hits">
        {rules.length ? <HBars rows={rules.map(([k, v]) => ({ key: k, label: `${k} · ${v.label}`, value: v.n, color: k.startsWith('M1') ? 'var(--m1)' : k.startsWith('M3') ? 'var(--m3)' : 'var(--m2)' }))} /> : <Empty title="No rule hits" />}
      </Card>
    </div>
  )
}

function RiskStatus({ p }: { p: MonitoredPage }) {
  const rw = p.last_snapshot?.risk_warning
  if (!rw) return <Pill color="var(--muted)">not fetched</Pill>
  return rw.present
    ? <span className="inline-flex items-center gap-1.5 text-xs text-ok"><ShieldCheck className="h-4 w-4" />Warning{rw.cfd_loss_pct ? ` · ${rw.cfd_loss_pct}%` : ''}{rw.above_fold ? ' · above fold' : ' · below fold'}</span>
    : <span className="inline-flex items-center gap-1.5 text-xs text-high"><ShieldAlert className="h-4 w-4" />No risk warning</span>
}

function WebsitesTab({ id, onChange }: { id: string; onChange: (c: string) => void }) {
  const { data, error, loading, reload } = useApi<MonitoredPage[]>(`/api/entities/${id}/pages`)
  const changes = useMemo(() => (data ?? []).flatMap((p) => p.changes.map((c) => ({ ...c, page: p }))).sort((a, b) => b.detected_at.localeCompare(a.detected_at)), [data])
  if (error) return <ErrorBox error={error} onRetry={reload} />
  if (loading && !data) return <Loading />
  if (!data?.length) return <Empty title="No monitored pages" hint="The website monitor has no pages configured for this entity yet (data/monitor/pages.json)." />
  return (
    <div className="grid gap-4 xl:grid-cols-5">
      <Card title="Monitored pages" subtitle="Last snapshot and risk-warning status" pad={false} className="xl:col-span-3">
        <ul className="divide-y divide-line">
          {data.map((p) => (
            <li key={p.page_id} className="px-5 py-3">
              <div className="flex flex-wrap items-center gap-2">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{p.label}</div>
                  <a href={p.url} target="_blank" rel="noreferrer" className="truncate text-xs text-muted hover:text-accent">{shortUrl(p.url)}</a>
                </div>
                <RiskStatus p={p} />
              </div>
              <div className="mt-1.5 flex flex-wrap items-center gap-3 text-[11px] text-muted">
                <span>Last fetch {fmtDate(p.last_snapshot?.fetched_at, true)}</span>
                <span>{p.changes.length} change{p.changes.length === 1 ? '' : 's'}</span>
                {p.last_snapshot?.risk_warning.text && <span className="line-clamp-1 max-w-md italic">“{p.last_snapshot.risk_warning.text}”</span>}
              </div>
            </li>
          ))}
        </ul>
      </Card>
      <Card title="Change timeline" subtitle="Click a change to open the side-by-side diff" className="xl:col-span-2">
        {changes.length ? (
          <ol className="relative ml-2 border-l border-line">
            {changes.map((c) => {
              const color = c.kinds.includes('risk_warning_removed') || c.kinds.includes('page_removed') ? 'var(--high)' : c.kinds.includes('risk_warning_changed') ? 'var(--medium)' : 'var(--accent)'
              return (
                <li key={c.id} className="mb-4 ml-4">
                  <span className="absolute -left-[6px] mt-1.5 h-3 w-3 rounded-full ring-4 ring-panel" style={{ background: color }} />
                  <button onClick={() => onChange(c.id)} className="group w-full rounded border border-line p-3 text-left hover:border-accent">
                    <div className="flex items-center gap-2 text-[11px] text-muted">{fmtDate(c.detected_at, true)} · {fmtAgo(c.detected_at)} {c.mock && <MockTag />}<ChevronRight className="ml-auto h-4 w-4 group-hover:text-accent" /></div>
                    <div className="mt-1 text-sm font-medium">{c.summary}</div>
                    <div className="mt-0.5 truncate text-xs text-muted">{c.page.label}</div>
                    <div className="mt-1.5 flex flex-wrap gap-1">{c.kinds.map((k) => <Pill key={k} color={k === 'text' ? 'var(--accent)' : color}>{kindLabel(k)}</Pill>)}</div>
                  </button>
                </li>
              )
            })}
          </ol>
        ) : <Empty title="No changes detected" hint="Snapshots are identical so far." />}
      </Card>
    </div>
  )
}

function snippet(it: ItemWithFindings) {
  return it.text.title || it.text.ad_body || it.text.post || it.text.description || it.text.ocr || Object.values(it.text)[0] || ''
}

function SocialTab({ id, onItem }: { id: string; onItem: (i: string) => void }) {
  const [platform, setPlatform] = useState('')
  const [module, setModule] = useState('')
  const [channel, setChannel] = useState('')
  const [limit, setLimit] = useState(40)
  const qs = new URLSearchParams({ limit: String(limit) })
  if (platform) qs.set('platform', platform)
  if (module) qs.set('module', module)
  if (channel) qs.set('channel', channel)
  const { data, error, loading, reload } = useApi<ItemsPage>(`/api/entities/${id}/items?${qs}`)
  return (
    <Card pad={false}>
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3">
        <Select label="Channel" value={channel} onChange={(v) => { setChannel(v); setLimit(40) }} options={[{ value: '', label: 'All' }, { value: 'ad', label: 'Ads' }, { value: 'social', label: 'Social' }]} />
        <Select label="Platform" value={platform} onChange={(v) => { setPlatform(v); setLimit(40) }} options={[{ value: '', label: 'All' }, ...Object.keys(PLATFORM_INFO).filter((p) => p !== 'website').map((p) => ({ value: p, label: platformLabel(p) }))]} />
        <Select label="Module" value={module} onChange={(v) => { setModule(v); setLimit(40) }} options={[{ value: '', label: 'All' }, ...MODULES.map((m) => ({ value: m, label: `${m} · ${MODULE_INFO[m].name}` }))]} />
        <span className="ml-auto text-xs text-muted tabular">{data ? `${data.items.length} of ${data.total}` : ''}</span>
      </div>
      {error ? <div className="p-5"><ErrorBox error={error} onRetry={reload} /></div> : loading && !data ? <Loading /> : !data?.items.length ? <Empty title="No items match" hint="Change the filters above." /> : (
        <>
          <ul className="divide-y divide-line">
            {data.items.map((it) => {
              const fs = it.findings.filter((f) => f.entity_id === id)
              const worst = fs.reduce<Finding | null>((w, f) => (!w || f.score > w.score ? f : w), null)
              return (
                <li key={it.id}>
                  <button onClick={() => onItem(it.id)} className="flex w-full items-start gap-4 px-5 py-3 text-left hover:bg-panel-2">
                    <div className="w-28 shrink-0 pt-0.5"><PlatformBadge p={it.platform} /><div className="mt-1 text-[11px] text-muted">{fmtDate(it.published_at ?? it.fetched_at)}</div></div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <span className="font-medium">{it.author}</span>
                        {it.author_is_entity ? <Pill color="var(--m2)">official</Pill> : <Pill color="var(--m1)">third party</Pill>}
                        {it.mock && <MockTag />}
                      </div>
                      <div className="mt-0.5 line-clamp-2 text-sm text-muted">{snippet(it)}</div>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <div className="flex gap-1">{[...new Set(fs.map((f) => f.module))].map((m) => <ModuleBadge key={m} m={m as Module} />)}</div>
                      {worst ? <SeverityBadge s={worst.severity} /> : <span className="text-[11px] text-muted">no findings</span>}
                    </div>
                  </button>
                </li>
              )
            })}
          </ul>
          {data.items.length < data.total && (
            <div className="border-t border-line p-3 text-center"><button onClick={() => setLimit(limit + 40)} className="text-xs font-medium text-accent">Load more ({data.total - data.items.length} left)</button></div>
          )}
        </>
      )}
    </Card>
  )
}

function FindingsTab({ id, onItem, focus }: { id: string; onItem: (i: string, f: string) => void; focus: string | null }) {
  const { findings, error, loading, reload } = useEntityItems(id)
  const [module, setModule] = useState('')
  const [sev, setSev] = useState('')
  const rows = useMemo(() => findings.filter((f) => (!module || f.module === module) && (!sev || f.severity === sev)).sort((a, b) => b.score - a.score), [findings, module, sev])
  if (error) return <ErrorBox error={error} onRetry={reload} />
  return (
    <Card pad={false}>
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3">
        <Select label="Module" value={module} onChange={setModule} options={[{ value: '', label: 'All' }, ...MODULES.map((m) => ({ value: m, label: m }))]} />
        <Select label="Severity" value={sev} onChange={setSev} options={[{ value: '', label: 'All' }, { value: 'high', label: 'High' }, { value: 'medium', label: 'Medium' }, { value: 'low', label: 'Low' }]} />
        <span className="ml-auto text-xs text-muted tabular">{rows.length} findings</span>
      </div>
      {loading && !findings.length ? <Loading /> : !rows.length ? <Empty title="No findings" /> : (
        <div className="scroll-thin overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-line text-[11px] uppercase tracking-wide text-muted">
              <tr><th className="px-5 py-2 font-medium">Severity</th><th className="py-2 font-medium">Module</th><th className="py-2 font-medium">Rule hits</th><th className="py-2 font-medium">Source</th><th className="py-2 text-right font-medium">Score</th><th className="px-5 py-2 text-right font-medium">Created</th></tr>
            </thead>
            <tbody className="divide-y divide-line">
              {rows.slice(0, 300).map((f) => (
                <tr key={f.id} onClick={() => onItem(f.item_id, f.id)} className={clsx('cursor-pointer hover:bg-panel-2', focus === f.id && 'bg-accent-soft')}>
                  <td className="px-5 py-2.5"><SeverityBadge s={f.severity} /></td>
                  <td><ModuleBadge m={f.module} /></td>
                  <td className="max-w-md py-2.5"><div className="line-clamp-2">{f.rule_hits.map((h) => <span key={h.rule_id + (h.span?.[0] ?? '')} className="mr-2"><b className="font-mono">{h.rule_id}</b> {h.label}</span>)}</div></td>
                  <td className="whitespace-nowrap"><PlatformBadge p={f.item.platform} /> <span className="text-muted">· {f.item.author.slice(0, 28)}</span></td>
                  <td className="text-right font-semibold tabular">{f.score.toFixed(2)}</td>
                  <td className="whitespace-nowrap px-5 text-right text-muted">{fmtDate(f.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length > 300 && <div className="border-t border-line p-3 text-center text-xs text-muted">Showing top 300 by score</div>}
        </div>
      )}
    </Card>
  )
}

function AlertsTab({ id }: { id: string }) {
  const { data, error, loading, reload } = useApi<Alert[]>(`/api/alerts?entity_id=${id}`)
  const ents = useApi<Entity[]>('/api/entities')
  if (error) return <ErrorBox error={error} onRetry={reload} />
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        {(['new', 'ack', 'closed'] as const).map((s) => <Kpi key={s} label={s === 'new' ? 'New' : s === 'ack' ? 'Acknowledged' : 'Closed'} value={(data ?? []).filter((a) => a.status === s).length} />)}
      </div>
      <Card pad={false}>{loading && !data ? <Loading /> : <AlertList alerts={data ?? []} entities={ents.data ?? []} showEntity={false} />}</Card>
    </div>
  )
}
