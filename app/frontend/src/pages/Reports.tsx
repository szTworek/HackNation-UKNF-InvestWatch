import { useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Printer } from 'lucide-react'
import { useApi, useDataMode } from '../api'
import { FindingsByDay, HBars, PlatformDonut, daysFromFindings } from '../charts'
import type { Alert, Entity, EntityDetail, MonitoredPage } from '../types'
import { CATEGORY_LABEL, Card, Empty, ErrorBox, Loading, MODULE_INFO, MODULES, ModuleBadge, PlatformBadge, RiskRing, Select, SeverityBadge, fmtDate, kindLabel, shortUrl } from '../ui'
import { useEntityItems } from './Entity'
import { PageTitle } from './Overview'

function Report({ id }: { id: string }) {
  const ent = useApi<EntityDetail>(`/api/entities/${id}`)
  const pages = useApi<MonitoredPage[]>(`/api/entities/${id}/pages`)
  const alerts = useApi<Alert[]>(`/api/alerts?entity_id=${id}`)
  const { findings, loading } = useEntityItems(id)
  const { mode } = useDataMode()
  const trend = useMemo(() => daysFromFindings(findings), [findings])
  const top = useMemo(() => [...findings].sort((a, b) => b.score - a.score).slice(0, 12), [findings])
  const rules = useMemo(() => {
    const m = new Map<string, { label: string; n: number }>()
    findings.forEach((f) => f.rule_hits.forEach((h) => { const x = m.get(h.rule_id) ?? { label: h.label, n: 0 }; x.n++; m.set(h.rule_id, x) }))
    return [...m.entries()].sort((a, b) => b[1].n - a[1].n).slice(0, 6)
  }, [findings])
  const e = ent.data
  if (ent.error) return <ErrorBox error={ent.error} onRetry={ent.reload} />
  if (!e || (loading && !findings.length)) return <Loading label="Building report…" />
  const changes = (pages.data ?? []).flatMap((p) => p.changes.map((c) => ({ ...c, label: p.label, url: p.url }))).sort((a, b) => b.detected_at.localeCompare(a.detected_at))
  const noWarn = (pages.data ?? []).filter((p) => p.last_snapshot && !p.last_snapshot.risk_warning.present)

  return (
    <article className="mx-auto max-w-[960px] space-y-4 rounded-md border border-line bg-panel p-4 sm:p-8 print:max-w-none print:border-0 print:p-0">
      <header className="flex items-start gap-6 border-b border-line pb-5">
        <div className="flex-1">
          <div className="text-[11px] font-semibold uppercase tracking-widest text-accent">InvestWatch · entity report</div>
          <h2 className="mt-1 text-3xl font-semibold tracking-tight">{e.name}</h2>
          <div className="mt-2 space-y-0.5 text-xs text-muted">
            {e.registry_entries.map((r) => <div key={r.name}><b className="text-ink">{r.name}</b> · {CATEGORY_LABEL[r.category] ?? r.category} · {r.country}</div>)}
            <div>Domains: {e.domains.join(', ')}</div>
          </div>
        </div>
        <div className="text-right text-xs text-muted">
          <RiskRing score={e.kpis.risk_score} size={84} />
          <div className="mt-1">risk score</div>
          <div className="mt-3">Generated {fmtDate(new Date().toISOString(), true)}</div>
          <div>Data: {mode === 'live' ? 'live API' : 'fixtures'} · classifier mock-v0</div>
        </div>
      </header>

      <section className="grid grid-cols-2 gap-3 sm:grid-cols-5 print:grid-cols-5">
        {[['Items collected', e.kpis.items], ['Open findings', e.kpis.findings_open], ['New alerts', e.kpis.alerts_new], ['Monitored pages', e.monitored_pages], ['Pages changed 7d', e.kpis.pages_changed_7d]].map(([l, v]) => (
          <div key={l} className="rounded border border-line p-3"><div className="text-2xl font-semibold tabular">{v}</div><div className="text-[11px] text-muted">{l}</div></div>
        ))}
      </section>

      <section className="grid gap-3 sm:grid-cols-3 print:grid-cols-3">
        {MODULES.map((m) => (
          <div key={m} className="rounded border border-line p-3">
            <div className="flex items-center gap-2 text-xs"><ModuleBadge m={m} /><b>{MODULE_INFO[m].name}</b></div>
            <div className="mt-2 flex justify-between text-sm"><span><b className="tabular">{e.modules[m]?.findings ?? 0}</b> findings</span><span className="text-muted">avg {e.modules[m]?.findings ? Math.round(e.modules[m].avg_score * 100) : '—'}</span></div>
          </div>
        ))}
      </section>

      <div className="grid gap-4 md:grid-cols-5 print:grid-cols-5">
        <Card title="Findings, last 30 days" className="md:col-span-3 print:col-span-3"><FindingsByDay data={trend} height={200} animate={false} /></Card>
        <Card title="Platform mix" className="md:col-span-2 print:col-span-2"><PlatformDonut data={e.platforms} height={130} animate={false} /></Card>
      </div>

      <Card title="Most frequent rule hits">
        {rules.length ? <HBars rows={rules.map(([k, v]) => ({ key: k, label: `${k} · ${v.label}`, value: v.n, color: k.startsWith('M1') ? 'var(--m1)' : k.startsWith('M3') ? 'var(--m3)' : 'var(--m2)' }))} /> : <Empty title="No rule hits" />}
      </Card>

      <Card title="Top findings" subtitle="Highest score first" className="print-break">
        <div className="overflow-x-auto"><table className="w-full min-w-[560px] text-left text-xs">
          <thead className="text-[11px] uppercase tracking-wide text-muted"><tr><th className="py-1.5">Sev.</th><th>Mod.</th><th>Rule / evidence</th><th>Source</th><th className="text-right">Score</th></tr></thead>
          <tbody className="divide-y divide-line">
            {top.map((f) => (
              <tr key={f.id} className="align-top">
                <td className="py-2 pr-2"><SeverityBadge s={f.severity} /></td>
                <td className="pr-2"><ModuleBadge m={f.module} /></td>
                <td className="py-2 pr-3"><b className="font-mono">{f.rule_hits[0]?.rule_id}</b> {f.rule_hits[0]?.label}<div className="mt-0.5 line-clamp-2 italic text-muted">“{f.rule_hits[0]?.evidence}”</div></td>
                <td className="whitespace-nowrap pr-2"><PlatformBadge p={f.item.platform} /><div className="text-muted">{f.item.author.slice(0, 26)}</div></td>
                <td className="text-right font-semibold tabular">{f.score.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 print:grid-cols-2">
        <Card title="Website changes">
          {changes.length ? <ul className="space-y-2 text-xs">{changes.map((c) => <li key={c.id}><b>{c.summary}</b><div className="text-muted">{shortUrl(c.url)} · {fmtDate(c.detected_at)} · {c.kinds.map(kindLabel).join(', ')}</div></li>)}</ul> : <Empty title="No changes" />}
          {noWarn.length > 0 && <div className="mt-3 rounded bg-high/10 p-2 text-xs text-high">Pages without a risk warning: {noWarn.map((p) => shortUrl(p.url)).join(', ')}</div>}
        </Card>
        <Card title="Open alerts">
          {(alerts.data ?? []).filter((a) => a.status === 'new').length ? (
            <ul className="space-y-2 text-xs">{(alerts.data ?? []).filter((a) => a.status === 'new').slice(0, 8).map((a) => <li key={a.id} className="flex gap-2"><SeverityBadge s={a.severity} /><span>{a.title}</span></li>)}</ul>
          ) : <Empty title="No open alerts" />}
        </Card>
      </div>
      <footer className="border-t border-line pt-3 text-[10px] text-muted">
        Findings produced by a mocked classifier (keyword rules, model “mock-v0”); not a supervisory decision. Rules R01–R18 follow art. 44 of Delegated Regulation (EU) 2017/565.
      </footer>
    </article>
  )
}

export default function ReportsPage() {
  const { id } = useParams()
  const nav = useNavigate()
  const ents = useApi<Entity[]>('/api/entities')
  const sel = id ?? ents.data?.[0]?.id
  return (
    <div>
      <div className="no-print">
        <PageTitle title="Reports" subtitle="Per-entity printable report — use Export PDF and choose “Save as PDF”"
          action={
            <div className="flex items-center gap-3">
              <Select label="Entity" value={sel ?? ''} onChange={(v) => nav(`/reports/${v}`)} options={(ents.data ?? []).map((e) => ({ value: e.id, label: e.name }))} />
              <button onClick={() => window.print()} className="inline-flex items-center gap-1.5 rounded bg-accent px-3 py-1.5 text-xs font-semibold text-white"><Printer className="h-3.5 w-3.5" /> Export PDF</button>
            </div>
          } />
      </div>
      {ents.error ? <ErrorBox error={ents.error} onRetry={ents.reload} /> : sel ? <Report key={sel} id={sel} /> : <Loading />}
    </div>
  )
}
