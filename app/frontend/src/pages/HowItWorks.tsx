import type { ReactNode } from 'react'
import { ArrowDown, Bot } from 'lucide-react'
import { API_URL, useApi, useDataMode } from '../api'
import type { Overview } from '../types'
import { MODULE_INFO, MODULES, PLATFORM_INFO, fmtNum } from '../ui'
import { PageTitle } from './Overview'

function Block({ title, sub, color, dashed, children }: { title: ReactNode; sub?: ReactNode; color?: string; dashed?: boolean; children?: ReactNode }) {
  return (
    <div className={`min-w-0 flex-1 basis-40 rounded border bg-panel p-3 ${dashed ? 'border-dashed' : ''}`}
      style={{ borderColor: color ? `color-mix(in srgb, ${color} 55%, transparent)` : 'var(--border)', background: color ? `color-mix(in srgb, ${color} 7%, var(--panel))` : undefined }}>
      <div className="text-sm font-semibold" style={color ? { color } : undefined}>{title}</div>
      {sub && <div className="mt-0.5 text-[11px] leading-snug text-muted">{sub}</div>}
      {children}
    </div>
  )
}

function Layer({ n, name, children }: { n: number; name: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-3 md:flex-row md:items-stretch">
      <div className="flex w-full shrink-0 items-center gap-2 md:w-40 md:flex-col md:items-start md:justify-center">
        <span className="grid h-6 w-6 place-items-center rounded-full bg-accent text-[11px] font-bold text-white">{n}</span>
        <span className="text-xs font-semibold uppercase tracking-wider text-muted">{name}</span>
      </div>
      <div className="flex flex-1 flex-wrap gap-2">{children}</div>
    </div>
  )
}

const Arrow = () => <div className="flex justify-center py-1 md:pl-40"><ArrowDown className="h-4 w-4 text-muted" /></div>

const SOURCES: { p: string; name: string; how: string }[] = [
  { p: 'google_ads', name: 'Google Ads Transparency', how: 'creatives by advertiser domain, OCR on images' },
  { p: 'meta_ads', name: 'Meta Ad Library', how: 'ads by page / keyword, web library' },
  { p: 'bing_ads', name: 'Microsoft Ad Library', how: 'ads by advertiser name' },
  { p: 'youtube', name: 'YouTube', how: 'search + transcripts (whisper)' },
  { p: 'tiktok', name: 'TikTok', how: 'official + finfluencer accounts, transcripts' },
  { p: 'website', name: 'Firm websites', how: 'monitored pages, periodic snapshots' },
]

export default function HowItWorksPage() {
  const { data: o } = useApi<Overview>('/api/metrics/overview?days=30')
  const { mode } = useDataMode()
  const count = (p: string) => o?.items_by_platform[p]
  return (
    <div>
      <PageTitle title="How it works" subtitle="From public ad libraries and websites to alerts for the supervisor — entity from the KNF registry is the axis" />
      <div className="rounded-md border border-line bg-panel p-5 sm:p-6">
        <Layer n={1} name="Sources">
          {SOURCES.map((s) => (
            <Block key={s.p} title={<span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: PLATFORM_INFO[s.p].color }} />{s.name}</span>}
              sub={<>{s.how}{count(s.p) !== undefined && <> · <b className="text-ink tabular">{fmtNum(count(s.p)!)}</b> {s.p === 'website' ? 'pages' : 'items'}</>}</>} />
          ))}
        </Layer>
        <Arrow />
        <Layer n={2} name="Collectors">
          <Block title="Ad & social scrapers" sub="scrapers/ — one collector per source; rate-limit aware, retries" />
          <Block title="Website monitor" sub="monitor/ — snapshot per page, text_sha256; a hash change yields a PageChange (risk warning added / changed / removed)" />
        </Layer>
        <Arrow />
        <Layer n={3} name="Normalize">
          <Block title="Unified record" sub="source, url, author, published_at, text sections (title, ad_body, ocr, transcript…)" />
          <Block title="Entity linking" sub="KNF registry entries grouped by brand · domains · official accounts · alias regex with homonym exclusions (e.g. “Shimano XTB”)" />
        </Layer>
        <Arrow />
        <Layer n={4} name="Classify">
          {MODULES.map((m) => <Block key={m} title={`${m} · ${MODULE_INFO[m].name}`} sub={MODULE_INFO[m].desc} color={MODULE_INFO[m].color} />)}
          <div className="flex w-full items-center gap-3 rounded border-2 border-dashed border-medium bg-medium/10 px-4 py-2.5 text-xs">
            <Bot className="h-5 w-5 shrink-0 text-medium" />
            <div><b>LLM is mocked in this PoC.</b> Findings come from <code className="font-mono">mock-v0</code>: keyword rules that emit the same Finding shape (module, score, severity, rule hits with evidence and text span) a real LLM classifier will return.</div>
          </div>
        </Layer>
        <Arrow />
        <Layer n={5} name="Alerts">
          <Block title="Finding alerts" sub="every high-severity finding" color="var(--high)" />
          <Block title="Website alerts" sub="risk warning removed or changed on a monitored page" color="var(--medium)" />
        </Layer>
        <Arrow />
        <Layer n={6} name="Dashboard">
          <Block title="Overview · Entities · Alerts · Reports" sub="this app — entity-centric views, acknowledge alerts, printable reports" color="var(--accent)" />
        </Layer>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div className="rounded-md border border-line bg-panel p-5 text-sm">
          <h3 className="font-semibold">Data in this demo</h3>
          <ul className="mt-2 space-y-1.5 text-xs text-muted">
            <li><b className="text-ink">Current mode: {mode === 'live' ? `live API (${API_URL})` : 'fixtures'}</b>. Auto mode probes <code>/api/entities</code> and falls back to fixtures.</li>
            <li><b className="text-ink">Real:</b> ad, social and website texts, authors, URLs and dates collected on 21 Nov 2026; KNF registry entries.</li>
            <li><b className="text-ink">Mocked:</b> classifier output (<code>mock-v0</code>), finding timestamps spread over 30 days, and page history before the latest snapshot — marked with a <span className="rounded-full bg-medium/15 px-1.5 text-medium">mock</span> tag.</li>
          </ul>
        </div>
        <div className="rounded-md border border-line bg-panel p-5 text-sm">
          <h3 className="font-semibold">Rules (M2)</h3>
          <p className="mt-2 text-xs text-muted">18 risk-information rules R01–R18 from art. 44 of Delegated Regulation (EU) 2017/565: firm identification, labelling as advertising, risk information next to profit claims, font size and exposure, language consistency, past performance and forecasts, tax treatment, no suggestion of supervisor approval.</p>
        </div>
      </div>
    </div>
  )
}
