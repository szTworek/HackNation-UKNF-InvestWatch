import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, FileWarning, ScanSearch } from 'lucide-react'
import { bumpData, request, useApi } from '../api'
import type { Alert, Entity, Severity } from '../types'
import { Card, Empty, ErrorBox, Kpi, Pill, Select, SeverityBadge, Skeleton, fmtAgo, fmtDate } from '../ui'
import { PageTitle, alertHref } from './Overview'

export function AlertList({ alerts, entities, showEntity = true }: { alerts: Alert[]; entities: Entity[]; showEntity?: boolean }) {
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<Record<string, string>>({})
  const [local, setLocal] = useState<Record<string, Alert['status']>>({})
  const ack = async (a: Alert) => {
    setBusy(a.id)
    try {
      const r = await request<Alert>(`/api/alerts/${a.id}/ack`, 'POST')
      setLocal((s) => ({ ...s, [a.id]: r.status }))
      bumpData()
    } catch (e) { setErr((s) => ({ ...s, [a.id]: (e as Error).message })) } finally { setBusy(null) }
  }
  const name = (id: string) => entities.find((e) => e.id === id)?.name ?? id
  if (!alerts.length) return <Empty title="No alerts match" hint="Try clearing filters." />
  return (
    <ul className="divide-y divide-line">
      {alerts.map((a) => {
        const status = local[a.id] ?? a.status
        return (
          <li key={a.id} className={`flex flex-wrap items-center gap-3 px-5 py-3 ${status !== 'new' ? 'opacity-60' : ''}`}>
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded bg-panel-2 text-muted">
              {a.kind === 'page_change' ? <FileWarning className="h-4 w-4" /> : <ScanSearch className="h-4 w-4" />}
            </span>
            <div className="min-w-0 flex-1 basis-64">
              <Link to={alertHref(a)} className="text-sm font-medium hover:text-accent">{a.title}</Link>
              <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted">
                {showEntity && <Link to={`/entities/${a.entity_id}`} className="font-medium text-ink hover:text-accent">{name(a.entity_id)}</Link>}
                <span>{a.kind === 'page_change' ? 'Website change' : 'Finding'}</span>
                <span title={fmtDate(a.created_at, true)}>{fmtAgo(a.created_at)}</span>
              </div>
            </div>
            <SeverityBadge s={a.severity} />
            {status === 'new' ? (
              <button onClick={() => ack(a)} disabled={busy === a.id}
                className="no-print inline-flex items-center gap-1 rounded border border-line px-2.5 py-1 text-xs font-medium hover:border-accent hover:text-accent disabled:opacity-50">
                <Check className="h-3.5 w-3.5" /> {err[a.id] ? 'Retry' : 'Acknowledge'}
              </button>
            ) : <Pill color="var(--muted)" className="min-w-[86px] justify-center">{status === 'ack' ? 'Acknowledged' : 'Closed'}</Pill>}
          </li>
        )
      })}
    </ul>
  )
}

export default function AlertsPage() {
  const [sev, setSev] = useState('')
  const [ent, setEnt] = useState('')
  const [kind, setKind] = useState('')
  const [status, setStatus] = useState('new')
  const qs = new URLSearchParams()
  if (sev) qs.set('severity', sev)
  if (ent) qs.set('entity_id', ent)
  if (status) qs.set('status', status)
  const { data, error, loading, reload } = useApi<Alert[]>(`/api/alerts?${qs}`)
  const all = useApi<Alert[]>('/api/alerts')
  const ents = useApi<Entity[]>('/api/entities')
  const rows = useMemo(() => (data ?? []).filter((a) => !kind || a.kind === kind), [data, kind])
  const counts = useMemo(() => {
    const n = (all.data ?? []).filter((a) => a.status === 'new')
    return { total: n.length, ...Object.fromEntries((['high', 'medium', 'low'] as Severity[]).map((s) => [s, n.filter((a) => a.severity === s).length])) } as Record<string, number>
  }, [all.data])

  return (
    <div>
      <PageTitle title="Alerts center" subtitle="Raised from high-severity findings and risk-warning changes on monitored websites" />
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi label="New alerts" value={counts.total} />
        <Kpi label="High" value={counts.high} tone="var(--high)" icon={<span className="h-2 w-2 rounded-full bg-high" />} />
        <Kpi label="Medium" value={counts.medium} tone="var(--medium)" icon={<span className="h-2 w-2 rounded-full bg-medium" />} />
        <Kpi label="Low" value={counts.low} tone="var(--low)" icon={<span className="h-2 w-2 rounded-full bg-low" />} />
      </div>
      <Card pad={false}>
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3">
          <Select label="Status" value={status} onChange={setStatus} options={[{ value: 'new', label: 'New' }, { value: 'ack', label: 'Acknowledged' }, { value: 'closed', label: 'Closed' }, { value: '', label: 'All' }]} />
          <Select label="Severity" value={sev} onChange={setSev} options={[{ value: '', label: 'All' }, { value: 'high', label: 'High' }, { value: 'medium', label: 'Medium' }, { value: 'low', label: 'Low' }]} />
          <Select label="Entity" value={ent} onChange={setEnt} options={[{ value: '', label: 'All' }, ...(ents.data ?? []).map((e) => ({ value: e.id, label: e.name }))]} />
          <Select label="Kind" value={kind} onChange={setKind} options={[{ value: '', label: 'All' }, { value: 'finding', label: 'Finding' }, { value: 'page_change', label: 'Website change' }]} />
          <span className="ml-auto text-xs text-muted tabular">{rows.length} alerts</span>
        </div>
        {error ? <div className="p-5"><ErrorBox error={error} onRetry={reload} /></div>
          : loading && !data ? <div className="space-y-2 p-5">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
          : <AlertList key={qs.toString() + kind} alerts={rows} entities={ents.data ?? []} />}
      </Card>
    </div>
  )
}
