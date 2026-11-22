import { useMemo, type ReactNode } from 'react'
import { ExternalLink, ShieldAlert, ShieldCheck, X } from 'lucide-react'
import { useApi } from '../api'
import type { Finding, ItemWithFindings, PageChangeDetail, RuleHit } from '../types'
import { Card, ErrorBox, Loading, MockTag, ModuleBadge, Pill, PlatformBadge, SeverityBadge, fmtDate, shortUrl, kindLabel } from '../ui'

export function Drawer({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; wide?: boolean }) {
  if (!open) return null
  return (
    <div className="no-print fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-[1px]" onClick={onClose} />
      <aside className={`absolute right-0 top-0 flex h-full w-full flex-col bg-bg shadow-2xl ${wide ? 'max-w-6xl' : 'max-w-2xl'}`}>
        <header className="flex items-center gap-3 border-b border-line bg-panel px-5 py-3">
          <div className="min-w-0 flex-1">{title}</div>
          <button onClick={onClose} className="grid h-8 w-8 place-items-center rounded hover:bg-panel-2" aria-label="Close"><X className="h-4 w-4" /></button>
        </header>
        <div className="scroll-thin flex-1 overflow-y-auto p-5">{children}</div>
      </aside>
    </div>
  )
}

const SECTION_LABEL: Record<string, string> = { title: 'Title', ad_body: 'Ad body', link_description: 'Link description', cta: 'Call to action', ocr: 'OCR (image text)', post: 'Post', transcript: 'Transcript', description: 'Description', page: 'Page text' }

export function Highlighted({ text, hits }: { text: string; hits: RuleHit[] }) {
  const parts = useMemo(() => {
    const spans = hits.filter((h): h is RuleHit & { span: [number, number] } => !!h.span && h.span[1] > h.span[0] && h.span[1] <= text.length).sort((a, b) => a.span[0] - b.span[0])
    const out: ReactNode[] = []
    let pos = 0
    spans.forEach((h, i) => {
      const [s, e] = h.span
      if (s < pos) return
      out.push(text.slice(pos, s))
      out.push(<mark key={i} className="hit" title={`${h.rule_id} · ${h.label}`}>{text.slice(s, e)}<sup className="ml-0.5 text-[9px] font-semibold text-high">{h.rule_id}</sup></mark>)
      pos = e
    })
    out.push(text.slice(pos))
    return out
  }, [text, hits])
  return <>{parts}</>
}

export function ItemView({ id, focusFinding }: { id: string; focusFinding?: string | null }) {
  const { data: it, error, loading } = useApi<ItemWithFindings>(`/api/items/${id}`)
  if (loading && !it) return <Loading />
  if (error || !it) return <ErrorBox error={error ?? 'Item not found'} />
  const allHits = it.findings.flatMap((f) => f.rule_hits)
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <PlatformBadge p={it.platform} />
        <Pill color="var(--muted)">{it.channel}</Pill>
        {it.author_is_entity ? <Pill color="var(--m2)">official account</Pill> : <Pill color="var(--m1)">third party</Pill>}
        {it.mock && <MockTag />}
        <span className="text-muted">published {fmtDate(it.published_at)} · fetched {fmtDate(it.fetched_at, true)}</span>
        <a href={it.source_url} target="_blank" rel="noreferrer" className="ml-auto inline-flex items-center gap-1 text-accent">Source <ExternalLink className="h-3 w-3" /></a>
      </div>

      {it.findings.length > 0 && (
        <Card title="Findings" subtitle={`Classifier ${it.findings[0].model} — mocked LLM, keyword rules`}>
          <ul className="space-y-3">
            {it.findings.map((f) => <FindingBlock key={f.id} f={f} focus={f.id === focusFinding} />)}
          </ul>
        </Card>
      )}

      <Card title="Collected text" subtitle="Rule-hit evidence highlighted in place">
        <div className="space-y-4">
          {Object.entries(it.text).map(([sec, t]) => (
            <div key={sec}>
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{SECTION_LABEL[sec] ?? sec}</div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed"><Highlighted text={t} hits={allHits.filter((h) => h.section === sec)} /></p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

function FindingBlock({ f, focus }: { f: Finding; focus?: boolean }) {
  return (
    <li className={`rounded border p-3 ${focus ? 'border-accent ring-2 ring-accent/30' : 'border-line'}`}>
      <div className="flex flex-wrap items-center gap-2">
        <ModuleBadge m={f.module} /><SeverityBadge s={f.severity} />
        <span className="text-xs text-muted">score <b className="tabular text-ink">{f.score.toFixed(2)}</b></span>
        <span className="ml-auto text-[11px] text-muted">{fmtDate(f.created_at, true)}</span>
      </div>
      <ul className="mt-2 space-y-1.5">
        {f.rule_hits.map((h, i) => (
          <li key={i} className="text-xs">
            <span className="font-mono font-semibold text-high">{h.rule_id}</span> <span className="font-medium">{h.label}</span>
            <div className="mt-0.5 rounded bg-panel-2 px-2.5 py-1.5 italic text-muted">“{h.evidence}” <span className="not-italic">— {SECTION_LABEL[h.section] ?? h.section}</span></div>
          </li>
        ))}
      </ul>
    </li>
  )
}

type Row = { kind: 'same' | 'del' | 'add' | 'mod'; a?: string; b?: string; ai?: number; bi?: number }

function diffLines(a: string[], b: string[]): Row[] {
  const n = a.length, m = b.length
  const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1))
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
  const raw: Row[] = []
  let i = 0, j = 0
  while (i < n || j < m) {
    if (i < n && j < m && a[i] === b[j]) { raw.push({ kind: 'same', a: a[i], b: b[j], ai: i++, bi: j++ }) }
    else if (j < m && (i >= n || dp[i][j + 1] >= dp[i + 1][j])) raw.push({ kind: 'add', b: b[j], bi: j++ })
    else raw.push({ kind: 'del', a: a[i], ai: i++ })
  }
  // pair adjacent del+add into modified rows
  const out: Row[] = []
  for (let k = 0; k < raw.length; k++) {
    const r = raw[k], nx = raw[k + 1]
    if (r.kind === 'del' && nx?.kind === 'add') { out.push({ kind: 'mod', a: r.a, ai: r.ai, b: nx.b, bi: nx.bi }); k++ }
    else if (r.kind === 'add' && nx?.kind === 'del') { out.push({ kind: 'mod', a: nx.a, ai: nx.ai, b: r.b, bi: r.bi }); k++ }
    else out.push(r)
  }
  return out
}

function wordDiff(a: string, b: string, side: 'a' | 'b') {
  const wa = a.split(/(\s+)/), wb = b.split(/(\s+)/)
  const setOther = new Set(side === 'a' ? wb : wa)
  return (side === 'a' ? wa : wb).map((w, i) => setOther.has(w) ? <span key={i}>{w}</span>
    : <span key={i} className={side === 'a' ? 'rounded bg-high/30' : 'rounded bg-ok/30'}>{w}</span>)
}

export function DiffView({ id }: { id: string }) {
  const { data: c, error, loading } = useApi<PageChangeDetail>(`/api/changes/${id}`)
  const rows = useMemo(() => c ? diffLines(c.from.text.split('\n'), c.to.text.split('\n')) : [], [c])
  const visible = useMemo(() => {
    const keep = new Set<number>()
    rows.forEach((r, i) => { if (r.kind !== 'same') for (let k = i - 2; k <= i + 2; k++) keep.add(k) })
    const out: (Row | { kind: 'gap'; count: number })[] = []
    let gap = 0
    rows.forEach((r, i) => {
      if (keep.has(i)) { if (gap) out.push({ kind: 'gap', count: gap }); gap = 0; out.push(r) } else gap++
    })
    if (gap) out.push({ kind: 'gap', count: gap })
    return out
  }, [rows])
  if (loading && !c) return <Loading />
  if (error || !c) return <ErrorBox error={error ?? 'Change not found'} />
  const rw = (s: PageChangeDetail['from']) => s.risk_warning
  const RW = ({ s, label }: { s: PageChangeDetail['from']; label: string }) => (
    <div className="rounded border border-line bg-panel p-3 text-xs">
      <div className="mb-1 flex items-center gap-2 font-semibold">{label} {s.mock && <MockTag />}<span className="ml-auto font-normal text-muted">{fmtDate(s.fetched_at, true)}</span></div>
      <div className="flex items-center gap-2">
        {rw(s).present ? <ShieldCheck className="h-4 w-4 text-ok" /> : <ShieldAlert className="h-4 w-4 text-high" />}
        <span>{rw(s).present ? `Risk warning present${rw(s).cfd_loss_pct ? ` · ${rw(s).cfd_loss_pct}% lose money` : ''}${rw(s).above_fold ? ' · above the fold' : ''}` : 'No risk warning'}</span>
      </div>
      <div className="mt-1 font-mono text-[10px] text-muted">sha256 {s.text_sha256.slice(0, 16)}…</div>
    </div>
  )
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {c.kinds.map((k) => <Pill key={k} color={k === 'risk_warning_removed' || k === 'page_removed' ? 'var(--high)' : k === 'risk_warning_changed' ? 'var(--medium)' : 'var(--accent)'}>{kindLabel(k)}</Pill>)}
        {c.mock && <MockTag />}
        <span className="text-sm font-medium">{c.summary}</span>
        <a href={c.to.url} target="_blank" rel="noreferrer" className="ml-auto inline-flex items-center gap-1 text-xs text-accent">{shortUrl(c.to.url)} <ExternalLink className="h-3 w-3" /></a>
      </div>
      <div className="grid gap-3 md:grid-cols-2"><RW s={c.from} label="Before" /><RW s={c.to} label="After" /></div>
      <div className="overflow-hidden rounded border border-line bg-panel font-mono text-[12px] leading-relaxed">
        <div className="grid grid-cols-2 border-b border-line bg-panel-2 text-[11px] font-semibold text-muted">
          <div className="px-3 py-1.5">Before · {fmtDate(c.from.fetched_at)}</div><div className="border-l border-line px-3 py-1.5">After · {fmtDate(c.to.fetched_at)}</div>
        </div>
        {visible.map((r, i) => r.kind === 'gap' ? (
          <div key={i} className="border-y border-line bg-panel-2/60 px-3 py-0.5 text-center text-[10px] text-muted">⋯ {r.count} unchanged lines</div>
        ) : (
          <div key={i} className="grid grid-cols-2">
            <div className={`flex gap-2 px-3 py-0.5 ${r.kind === 'del' || r.kind === 'mod' ? 'bg-high/10' : ''}`}>
              <span className="w-8 shrink-0 select-none text-right text-muted/60">{r.ai !== undefined ? r.ai + 1 : ''}</span>
              <span className="min-w-0 whitespace-pre-wrap break-words">{r.kind === 'mod' ? wordDiff(r.a!, r.b!, 'a') : r.a}</span>
            </div>
            <div className={`flex gap-2 border-l border-line px-3 py-0.5 ${r.kind === 'add' || r.kind === 'mod' ? 'bg-ok/10' : ''}`}>
              <span className="w-8 shrink-0 select-none text-right text-muted/60">{r.bi !== undefined ? r.bi + 1 : ''}</span>
              <span className="min-w-0 whitespace-pre-wrap break-words">{r.kind === 'mod' ? wordDiff(r.a!, r.b!, 'b') : r.b}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
