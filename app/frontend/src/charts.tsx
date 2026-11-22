import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Finding, Module } from './types'
import { MODULE_INFO, MODULES, PLATFORM_INFO, platformLabel, tooltipStyle } from './ui'

export type DayRow = { date: string } & Record<Module, number>

export function daysFromFindings(findings: Finding[], days = 30): DayRow[] {
  const end = findings.reduce((m, f) => (f.created_at > m ? f.created_at : m), '').slice(0, 10) || new Date().toISOString().slice(0, 10)
  const out: DayRow[] = []
  const base = new Date(end + 'T00:00:00Z')
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(base.getTime() - i * 86400000).toISOString().slice(0, 10)
    out.push({ date: d, M1: 0, M2: 0, M3: 0 })
  }
  const idx = new Map(out.map((r, i) => [r.date, i]))
  for (const f of findings) {
    const i = idx.get(f.created_at.slice(0, 10))
    if (i !== undefined) out[i][f.module] += 1
  }
  return out
}

const dayTick = (d: string) => new Date(d + 'T00:00:00Z').toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })

export function FindingsByDay({ data, height = 240, animate = false }: { data: DayRow[]; height?: number; animate?: boolean }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 4, left: -18, bottom: 0 }} barCategoryGap="22%">
        <CartesianGrid vertical={false} />
        <XAxis dataKey="date" tickFormatter={dayTick} tickLine={false} axisLine={false} interval="preserveStartEnd" minTickGap={24} />
        <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={44} />
        <Tooltip {...tooltipStyle} labelFormatter={(d) => dayTick(String(d))} />
        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} formatter={(v: string) => <span style={{ color: 'var(--muted)' }}>{v} · {MODULE_INFO[v as Module].name}</span>} />
        {MODULES.map((m, i) => (
          <Bar key={m} dataKey={m} stackId="a" fill={MODULE_INFO[m].color} radius={i === 2 ? [4, 4, 0, 0] : 0} isAnimationActive={animate} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}

export function PlatformDonut({ data, height = 220, animate = false }: { data: Record<string, number>; height?: number; animate?: boolean }) {
  const rows = Object.entries(data).map(([k, v]) => ({ name: k, value: v })).sort((a, b) => b.value - a.value)
  const total = rows.reduce((s, r) => s + r.value, 0)
  return (
    <div className="flex items-center gap-4">
      <div className="relative" style={{ width: height, height }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={rows} dataKey="value" innerRadius="62%" outerRadius="92%" paddingAngle={2} stroke="none" isAnimationActive={animate}>
              {rows.map((r) => <Cell key={r.name} fill={PLATFORM_INFO[r.name]?.color ?? '#999'} />)}
            </Pie>
            <Tooltip {...tooltipStyle} formatter={(v, n) => [String(v), platformLabel(String(n))]} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
          <div><div className="text-xl font-semibold tabular">{total}</div><div className="text-[11px] text-muted">items</div></div>
        </div>
      </div>
      <ul className="flex-1 space-y-1.5 text-xs">
        {rows.map((r) => (
          <li key={r.name} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: PLATFORM_INFO[r.name]?.color ?? '#999' }} />
            <span className="flex-1">{platformLabel(r.name)}</span>
            <span className="tabular text-muted">{r.value}</span>
            <span className="w-10 text-right tabular text-muted">{total ? Math.round((r.value / total) * 100) : 0}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function HBars({ rows, color, valueLabel }: { rows: { key: string; label: string; value: number; color?: string }[]; color?: string; valueLabel?: (v: number) => string }) {
  const max = Math.max(1, ...rows.map((r) => r.value))
  return (
    <ul className="space-y-2.5">
      {rows.map((r) => (
        <li key={r.key} className="text-xs">
          <div className="mb-1 flex justify-between gap-2"><span className="truncate">{r.label}</span><span className="tabular text-muted">{valueLabel ? valueLabel(r.value) : r.value}</span></div>
          <div className="h-2 rounded-full bg-panel-2">
            <div className="h-2 rounded-full transition-all" style={{ width: `${(r.value / max) * 100}%`, background: r.color ?? color ?? 'var(--accent)' }} />
          </div>
        </li>
      ))}
    </ul>
  )
}
