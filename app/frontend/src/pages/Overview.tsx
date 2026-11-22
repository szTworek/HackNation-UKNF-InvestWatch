import { Link } from 'react-router-dom'
import { Bell, Building2, FileWarning, Globe, Layers, ScanSearch } from 'lucide-react'
import { useApi } from '../api'
import { FindingsByDay, HBars, PlatformDonut } from '../charts'
import type { Alert, Entity, Overview } from '../types'
import { Card, Empty, ErrorBox, Kpi, MODULE_INFO, MODULES, ModuleBadge, Pill, Skeleton, fmtAgo, fmtNum } from '../ui'

export function PageTitle({ title, subtitle, action }: { title: string; subtitle?: string; action?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-[28px] font-bold tracking-tight text-accent sm:text-[32px]">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

function heatColor(v: number) {
  if (!v) return 'var(--panel-2)'
  return `color-mix(in srgb, var(--m1) ${Math.round(8 + v * 85)}%, var(--panel))`
}

export function Heatmap({ rows, entities }: { rows: Overview['heatmap']; entities: Entity[] }) {
  const name = (id: string) => entities.find((e) => e.id === id)?.name ?? id
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-separate border-spacing-1.5 text-xs">
        <thead>
          <tr>
            <th />
            {MODULES.map((m) => <th key={m} className="px-1 pb-1 text-left font-medium text-muted"><ModuleBadge m={m} /> <span className="hidden xl:inline">{MODULE_INFO[m].name}</span></th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.entity_id}>
              <td className="pr-2 font-medium"><Link to={`/entities/${r.entity_id}`} className="hover:text-accent">{name(r.entity_id)}</Link></td>
              {MODULES.map((m) => (
                <td key={m} className="h-11 min-w-20 rounded-sm text-center font-semibold tabular" style={{ background: heatColor(r[m]), color: r[m] >= 0.45 ? "#fff" : undefined }} title={`${name(r.entity_id)} · ${m}: avg score ${r[m]}`}>
                  {r[m] ? Math.round(r[m] * 100) : <span className="font-normal text-muted">—</span>}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-2 flex items-center gap-2 text-[11px] text-muted">
        Avg finding score
        <span className="h-2 w-24 rounded-full" style={{ background: 'linear-gradient(90deg, color-mix(in srgb, var(--m1) 10%, var(--panel)), var(--m1))' }} />
      </div>
    </div>
  )
}

export function AlertFeed({ alerts, entities, limit = 8 }: { alerts: Alert[]; entities: Entity[]; limit?: number }) {
  if (!alerts.length) return <Empty title="No alerts" hint="Alerts appear when a high-severity finding or a risk-warning change is detected." />
  const name = (id: string) => entities.find((e) => e.id === id)?.name ?? id
  return (
    <ul className="divide-y divide-line">
      {alerts.slice(0, limit).map((a) => (
        <li key={a.id}>
          <Link to={alertHref(a)} className="flex items-start gap-3 py-2.5 hover:opacity-80">
            <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ background: a.severity === 'high' ? 'var(--high)' : a.severity === 'medium' ? 'var(--medium)' : 'var(--low)' }} />
            <div className="min-w-0 flex-1">
              <div className="line-clamp-2 text-xs font-medium leading-snug">{a.title}</div>
              <div className="mt-0.5 text-[11px] text-muted">{name(a.entity_id)} · {a.kind === 'page_change' ? 'Website change' : 'Finding'} · {fmtAgo(a.created_at)}</div>
            </div>
            {a.status === 'new' && <span className="rounded bg-accent-soft px-1.5 py-0.5 text-[10px] font-semibold text-accent">NEW</span>}
          </Link>
        </li>
      ))}
    </ul>
  )
}

export function alertHref(a: Alert) {
  if (a.ref.change_id) return `/entities/${a.entity_id}?tab=websites&change=${a.ref.change_id}`
  if (a.ref.finding_id) return `/entities/${a.entity_id}?tab=findings&finding=${a.ref.finding_id}`
  return `/entities/${a.entity_id}`
}

export default function OverviewPage() {
  const ov = useApi<Overview>('/api/metrics/overview?days=30')
  const ents = useApi<Entity[]>('/api/entities')
  const alerts = useApi<Alert[]>('/api/alerts')
  const o = ov.data
  const entities = ents.data ?? []

  return (
    <div>
      <PageTitle title="Market overview" subtitle="Ads, social posts and websites of KNF-registered entities · last 30 days" />
      {ov.error && <div className="mb-4"><ErrorBox error={ov.error} onRetry={ov.reload} /></div>}
      {ents.error && <div className="mb-4"><ErrorBox error={ents.error} onRetry={ents.reload} /></div>}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {o ? (
          <>
            <Kpi label="Entities" value={o.totals.entities} hint="KNF registry brands" icon={<Building2 className="h-4 w-4" />} />
            <Kpi label="Items collected" value={fmtNum(o.totals.items)} hint="ads · posts · videos" icon={<Layers className="h-4 w-4" />} tone="var(--m2)" />
            <Kpi label="Findings" value={fmtNum(o.totals.findings)} hint="M1 · M2 · M3" icon={<ScanSearch className="h-4 w-4" />} tone="var(--m3)" />
            <Kpi label="New alerts" value={o.totals.alerts_new} hint={<Link to="/alerts" className="text-accent">Open alerts →</Link>} icon={<Bell className="h-4 w-4" />} tone="var(--high)" />
            <Kpi label="Pages monitored" value={o.totals.pages} hint="firm websites" icon={<Globe className="h-4 w-4" />} tone="var(--accent-2)" />
            <Kpi label="Page changes" value={o.totals.page_changes_30d} hint="last 30 days" icon={<FileWarning className="h-4 w-4" />} tone="var(--medium)" />
          </>
        ) : Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-[106px]" />)}
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <Card title="Findings per day" subtitle="Stacked by module" className="xl:col-span-2">
          {o ? <FindingsByDay data={o.findings_by_day} height={260} /> : <Skeleton className="h-[260px]" />}
        </Card>
        <Card title="Entity × module risk" subtitle="Average finding score (0–100)">
          {o ? <Heatmap rows={o.heatmap} entities={entities} /> : <Skeleton className="h-[260px]" />}
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
        <Card title="Items by platform">
          {o ? <PlatformDonut data={o.items_by_platform} height={180} /> : <Skeleton className="h-[180px]" />}
        </Card>
        <Card title="Top violated rules" subtitle="Rule hits across all findings">
          {o ? (o.top_rules.length ? <HBars rows={o.top_rules.slice(0, 7).map((r) => ({
            key: r.rule_id, label: `${r.rule_id} · ${r.label}`, value: r.count,
            color: r.rule_id.startsWith('M1') ? 'var(--m1)' : r.rule_id.startsWith('M3') ? 'var(--m3)' : 'var(--m2)',
          }))} /> : <Empty title="No rule hits yet" />) : <Skeleton className="h-[180px]" />}
        </Card>
        <Card title="Latest alerts" action={<Link to="/alerts" className="text-xs font-medium text-accent">View all</Link>} className="lg:col-span-2 xl:col-span-1">
          {alerts.error ? <ErrorBox error={alerts.error} onRetry={alerts.reload} /> : alerts.data ? <AlertFeed alerts={alerts.data} entities={entities} limit={7} /> : <Skeleton className="h-[180px]" />}
        </Card>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {entities.map((e) => (
          <Link key={e.id} to={`/entities/${e.id}`} className="flex items-center justify-between rounded border border-line bg-panel px-4 py-3 text-sm hover:border-accent">
            <span className="font-medium">{e.name}</span>
            <span className="flex items-center gap-2 text-xs text-muted">{e.kpis.findings_open} findings {e.kpis.alerts_new > 0 && <Pill color="var(--high)">{e.kpis.alerts_new} new</Pill>}</span>
          </Link>
        ))}
      </div>
    </div>
  )
}
