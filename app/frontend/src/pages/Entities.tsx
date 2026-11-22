import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell, Globe, Layers, ScanSearch } from 'lucide-react'
import { useApi } from '../api'
import type { Entity } from '../types'
import { CATEGORY_LABEL, Empty, ErrorBox, Pill, RiskRing, Select, Skeleton, riskColor } from '../ui'
import { PageTitle } from './Overview'

function Stat({ icon, label, value, warn }: { icon: React.ReactNode; label: string; value: number; warn?: boolean }) {
  return (
    <div className="rounded bg-panel-2 px-3 py-2">
      <div className="flex items-center gap-1.5 text-[11px] text-muted">{icon}{label}</div>
      <div className="mt-0.5 text-lg font-semibold tabular" style={warn && value > 0 ? { color: 'var(--high)' } : undefined}>{value}</div>
    </div>
  )
}

export function EntityCard({ e }: { e: Entity }) {
  return (
    <Link to={`/entities/${e.id}`} className="group flex flex-col rounded-md border border-line bg-panel p-5 transition hover:border-accent">
      <div className="flex items-start gap-4">
        <div className="min-w-0 flex-1">
          <div className="text-lg font-semibold group-hover:text-accent">{e.name}</div>
          <div className="mt-0.5 truncate text-xs text-muted">{e.domains.join(' · ')}</div>
        </div>
        <div className="text-center">
          <RiskRing score={e.kpis.risk_score} />
          <div className="mt-1 text-[10px] font-medium uppercase tracking-wide" style={{ color: riskColor(e.kpis.risk_score) }}>risk</div>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <Stat icon={<ScanSearch className="h-3 w-3" />} label="Open findings" value={e.kpis.findings_open} />
        <Stat icon={<Bell className="h-3 w-3" />} label="New alerts" value={e.kpis.alerts_new} warn />
        <Stat icon={<Layers className="h-3 w-3" />} label="Items" value={e.kpis.items} />
        <Stat icon={<Globe className="h-3 w-3" />} label="Pages changed 7d" value={e.kpis.pages_changed_7d} warn />
      </div>
      <div className="mt-4 border-t border-line pt-3">
        <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-muted">KNF registry</div>
        {e.registry_entries.length ? (
          <ul className="space-y-1.5">
            {e.registry_entries.map((r) => (
              <li key={r.name} className="flex flex-wrap items-center gap-1.5 text-xs">
                <span className="font-medium">{r.name}</span>
                <Pill color="var(--accent)">{CATEGORY_LABEL[r.category] ?? r.category}</Pill>
                <Pill color="var(--muted)">{r.country}</Pill>
              </li>
            ))}
          </ul>
        ) : <div className="text-xs text-muted">No registry entry matched</div>}
      </div>
    </Link>
  )
}

export default function EntitiesPage() {
  const { data, error, loading, reload } = useApi<Entity[]>('/api/entities')
  const [sort, setSort] = useState('risk')
  const rows = useMemo(() => {
    const r = [...(data ?? [])]
    if (sort === 'risk') r.sort((a, b) => b.kpis.risk_score - a.kpis.risk_score)
    if (sort === 'findings') r.sort((a, b) => b.kpis.findings_open - a.kpis.findings_open)
    if (sort === 'alerts') r.sort((a, b) => b.kpis.alerts_new - a.kpis.alerts_new)
    if (sort === 'name') r.sort((a, b) => a.name.localeCompare(b.name))
    return r
  }, [data, sort])
  return (
    <div>
      <PageTitle title="Entities" subtitle="Brands grouped from KNF registry entries; every item, page and finding hangs on an entity"
        action={<Select label="Sort" value={sort} onChange={setSort} options={[{ value: 'risk', label: 'Risk score' }, { value: 'findings', label: 'Open findings' }, { value: 'alerts', label: 'New alerts' }, { value: 'name', label: 'Name' }]} />} />
      {error && <ErrorBox error={error} onRetry={reload} />}
      {loading && !data ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-80" />)}</div>
      ) : rows.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{rows.map((e) => <EntityCard key={e.id} e={e} />)}</div>
      ) : !error && <Empty title="No entities" hint="The backend has not loaded any KNF entities yet." />}
    </div>
  )
}
