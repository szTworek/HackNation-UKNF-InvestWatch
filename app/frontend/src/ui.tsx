import clsx from 'clsx'
import type { ReactNode } from 'react'
import { AlertTriangle, Inbox, Loader2 } from 'lucide-react'
import type { Module, Severity } from './types'

export const MODULES: Module[] = ['M1', 'M2', 'M3']
export const MODULE_INFO: Record<Module, { name: string; desc: string; color: string }> = {
  M1: { name: 'Third-party promotion', desc: 'Entity advertised by finfluencers / third parties', color: 'var(--m1)' },
  M2: { name: 'Risk-info compliance', desc: "Entity's own materials vs 18 rules (art. 44, Reg. 2017/565)", color: 'var(--m2)' },
  M3: { name: 'Shadow advisory', desc: 'Recommendations by authors outside the KNF registry', color: 'var(--m3)' },
}
export const PLATFORM_INFO: Record<string, { label: string; color: string }> = {
  google_ads: { label: 'Google Ads', color: '#113b6f' },
  meta_ads: { label: 'Meta Ads', color: '#2f5fb3' },
  bing_ads: { label: 'Bing Ads', color: '#618eff' },
  youtube: { label: 'YouTube', color: '#9db8f5' },
  tiktok: { label: 'TikTok', color: '#5b6b86' },
  website: { label: 'Website', color: '#8a96aa' },
}
export const platformLabel = (p: string) => PLATFORM_INFO[p]?.label ?? p
export const CATEGORY_LABEL: Record<string, string> = {
  domy_maklerskie: 'Brokerage house (PL)',
  zagraniczne_bez_oddzialu: 'Foreign firm, cross-border',
  zagraniczne_oddzialy: 'Foreign firm branch',
  banki_maklerskie: 'Bank brokerage',
}
export const KIND_LABEL: Record<string, string> = { text: 'Text changed', risk_warning_changed: 'Risk warning changed', risk_warning_removed: 'Risk warning removed', page_removed: 'Page removed' }
export const kindLabel = (k: string) => KIND_LABEL[k] ?? k
export const SEVERITY_COLOR: Record<Severity, string> = { high: 'var(--high)', medium: 'var(--medium)', low: 'var(--low)' }

export const fmtDate = (s: string | null | undefined, withTime = false) => {
  if (!s) return '—'
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return s
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: withTime ? undefined : 'numeric', ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {}) })
}
export const fmtAgo = (s: string) => {
  const diff = (Date.now() - new Date(s).getTime()) / 1000
  if (diff < 3600) return `${Math.max(1, Math.round(diff / 60))}m ago`
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`
  return `${Math.round(diff / 86400)}d ago`
}
export const fmtNum = (n: number) => n.toLocaleString('en-US')
export const shortUrl = (u: string) => u.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '')

export function Card({ title, subtitle, action, children, className, pad = true }: { title?: ReactNode; subtitle?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; pad?: boolean }) {
  return (
    <section className={clsx('rounded-md border border-line bg-panel  print-page', className)}>
      {(title || action) && (
        <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-3">
          <div>
            {title && <h3 className="section-title text-accent">{title}</h3>}
            {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={clsx(pad && 'p-5')}>{children}</div>
    </section>
  )
}

export function Kpi({ label, value, hint, icon, tone }: { label: string; value: ReactNode; hint?: ReactNode; icon?: ReactNode; tone?: string }) {
  return (
    <div className="rounded-md border border-line bg-panel p-4 print-page">
      <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-muted">
        <span>{label}</span>
        {icon && <span className="grid h-7 w-7 place-items-center rounded" style={{ background: `color-mix(in srgb, ${tone ?? 'var(--accent)'} 14%, transparent)`, color: tone ?? 'var(--accent)' }}>{icon}</span>}
      </div>
      <div className="mt-2 text-[28px] font-bold leading-none tabular text-accent">{value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  )
}

export function Pill({ children, color, className, title }: { children: ReactNode; color?: string; className?: string; title?: string }) {
  return (
    <span title={title} className={clsx('inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium', className)}
      style={color ? { background: `color-mix(in srgb, ${color} 15%, transparent)`, color } : undefined}>
      {children}
    </span>
  )
}

export const SeverityBadge = ({ s }: { s: Severity }) => (
  <Pill color={SEVERITY_COLOR[s]} className="uppercase tracking-wide"><span className="h-1.5 w-1.5 rounded-full" style={{ background: SEVERITY_COLOR[s] }} />{s}</Pill>
)
export const ModuleBadge = ({ m }: { m: Module }) => <Pill color={MODULE_INFO[m].color} title={MODULE_INFO[m].name}>{m}</Pill>
export const PlatformBadge = ({ p }: { p: string }) => (
  <span className="inline-flex items-center gap-1.5 text-xs"><span className="h-2 w-2 rounded-full" style={{ background: PLATFORM_INFO[p]?.color ?? '#999' }} />{platformLabel(p)}</span>
)
export const MockTag = () => <Pill color="var(--medium)" title="Synthetic data, not collected">mock</Pill>

export function riskColor(score: number) {
  return score >= 0.7 ? 'var(--high)' : score >= 0.5 ? 'var(--medium)' : 'var(--accent-2)'
}

export function RiskRing({ score, size = 56 }: { score: number; size?: number }) {
  const r = size / 2 - 5, c = 2 * Math.PI * r
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--grid)" strokeWidth="5" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={riskColor(score)} strokeWidth="5" strokeLinecap="round" strokeDasharray={`${c * score} ${c}`} />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-sm font-semibold tabular">{Math.round(score * 100)}</div>
    </div>
  )
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted"><Loader2 className="h-4 w-4 animate-spin" />{label}</div>
}
export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse rounded bg-panel-2', className)} />
}
export function Empty({ title, hint, icon }: { title: string; hint?: string; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-4 py-12 text-center">
      <div className="grid h-10 w-10 place-items-center rounded-full bg-panel-2 text-muted">{icon ?? <Inbox className="h-5 w-5" />}</div>
      <div className="text-sm font-medium">{title}</div>
      {hint && <div className="max-w-sm text-xs text-muted">{hint}</div>}
    </div>
  )
}
export function ErrorBox({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div className="flex items-center gap-3 rounded border border-high/30 bg-high/10 px-4 py-3 text-sm">
      <AlertTriangle className="h-4 w-4 text-high" />
      <span className="flex-1">{error}</span>
      {onRetry && <button onClick={onRetry} className="text-xs font-medium underline">Retry</button>}
    </div>
  )
}

export function Select({ value, onChange, options, label }: { value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; label: string }) {
  return (
    <label className="flex items-center gap-2 text-xs text-muted">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="rounded border border-line bg-panel px-2.5 py-1.5 text-xs text-ink outline-none focus:border-accent">
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  )
}

export const tooltipStyle = {
  contentStyle: { background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12, color: 'var(--text)', boxShadow: '0 2px 8px rgba(0,0,0,.08)' },
  labelStyle: { color: 'var(--muted)', marginBottom: 4 },
  itemStyle: { padding: 0 },
  cursor: { fill: 'var(--grid)', opacity: 0.6 },
}

export function Logo({ className = 'h-9 w-9' }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} aria-hidden="true">
      <path d="M20 3 L34 8 V19 C34 28 28 34 20 37 C12 34 6 28 6 19 V8 Z" fill="var(--nav)" />
      <path d="M11 20 C14 15 17 13 20 13 C23 13 26 15 29 20 C26 25 23 27 20 27 C17 27 14 25 11 20 Z" fill="none" stroke="#fff" strokeWidth="2" />
      <circle cx="20" cy="20" r="3.4" fill="#618eff" />
    </svg>
  )
}
