import { useEffect, useState } from 'react'
import { BrowserRouter, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import clsx from 'clsx'
import { Bell, Building2, FileText, LayoutDashboard, Menu, Moon, RefreshCw, Sun, Workflow, X } from 'lucide-react'
import { Logo } from './ui'
import { API_URL, bumpData, request, resolveMode, useApi, useDataMode } from './api'
import type { Alert, ScanResult } from './types'
import OverviewPage from './pages/Overview'
import EntitiesPage from './pages/Entities'
import EntityPage from './pages/Entity'
import AlertsPage from './pages/Alerts'
import ReportsPage from './pages/Reports'
import HowItWorksPage from './pages/HowItWorks'

function useTheme() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    try { localStorage.setItem('iw-theme', dark ? 'dark' : 'light') } catch { /* ignore */ }
  }, [dark])
  return [dark, setDark] as const
}

function ModeSwitch() {
  const { pref, mode, probing } = useDataMode()
  const opts = [['auto', 'Auto'], ['live', 'Live'], ['fixtures', 'Fixtures']] as const
  return (
    <div className="flex items-center gap-2">
      <span className="hidden items-center gap-1.5 text-xs text-muted sm:flex" title={mode === 'live' ? API_URL : 'Bundled fixtures built from real sample records'}>
        <span className={clsx('h-2 w-2 rounded-full', probing ? 'animate-pulse bg-low' : mode === 'live' ? 'bg-ok' : 'bg-medium')} />
        {probing ? 'Connecting…' : mode === 'live' ? 'Live API' : 'Fixtures'}
      </span>
      <div className="flex rounded border border-line bg-panel-2 p-0.5 text-[11px]">
        {opts.map(([v, l]) => (
          <button key={v} aria-pressed={pref === v} onClick={() => resolveMode(v)}
            className={clsx('rounded-sm px-2 py-1 font-medium', pref === v ? 'bg-panel text-ink shadow-sm' : 'text-muted hover:text-ink')}>{l}</button>
        ))}
      </div>
    </div>
  )
}

function ScanButton() {
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const run = async () => {
    setBusy(true); setMsg(null)
    try {
      const r = await request<ScanResult>('/api/scan/run', 'POST')
      setMsg(`+${r.items_new} items · +${r.findings_new} findings · +${r.alerts_new} alerts`)
      bumpData()
    } catch (e) { setMsg((e as Error).message) } finally { setBusy(false); setTimeout(() => setMsg(null), 5000) }
  }
  return (
    <div className="relative">
      <button onClick={run} disabled={busy}
        className="flex items-center gap-1.5 rounded bg-accent px-3 py-2 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-60">
        <RefreshCw className={clsx('h-3.5 w-3.5', busy && 'animate-spin')} /> Run scan
      </button>
      {msg && <div className="absolute right-0 top-10 z-30 whitespace-nowrap rounded border border-line bg-panel px-3 py-2 text-xs shadow-lg">{msg}</div>}
    </div>
  )
}

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/entities', label: 'Entities', icon: Building2 },
  { to: '/alerts', label: 'Alerts', icon: Bell },
  { to: '/reports', label: 'Reports', icon: FileText },
  { to: '/how-it-works', label: 'How it works', icon: Workflow },
]

function Shell() {
  const [dark, setDark] = useTheme()
  const [open, setOpen] = useState(false)
  const loc = useLocation()
  useEffect(() => setOpen(false), [loc.pathname])
  const { data: alerts } = useApi<Alert[]>('/api/alerts?status=new')
  const newCount = alerts?.length ?? 0

  const links = (mobile: boolean) => NAV.map(({ to, label, icon: Icon }) => (
    <NavLink key={to} to={to} end={to === '/'}
      className={({ isActive }) => clsx(
        mobile ? 'flex items-center gap-3 border-l-4 px-4 py-3 text-sm font-semibold' : 'relative flex items-center gap-2 border-b-[3px] px-1 py-3.5 text-[13px] font-bold uppercase tracking-wide',
        isActive ? 'border-accent-2 text-accent' : 'border-transparent text-ink hover:text-accent')}>
      {mobile && <Icon className="h-4 w-4" />}
      {label}
      {to === '/alerts' && newCount > 0 && <span className="rounded-sm bg-high px-1.5 py-px text-[10px] font-bold text-white tabular">{newCount}</span>}
    </NavLink>
  ))

  return (
    <div className="flex min-h-full flex-col">
      <header className="no-print sticky top-0 z-30 border-b border-line bg-panel">
        <div className="mx-auto flex max-w-[1400px] items-center gap-4 px-4 py-3 sm:px-6">
          <NavLink to="/" className="flex items-center gap-3">
            <Logo />
            <div className="border-l border-line pl-3 leading-tight">
              <div className="text-[17px] font-extrabold tracking-tight text-accent">InvestWatch</div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Financial ads monitoring</div>
            </div>
          </NavLink>
          <div className="flex-1" />
          <div className="hidden md:block"><ModeSwitch /></div>
          <button onClick={() => setDark(!dark)} className="grid h-8 w-8 place-items-center rounded border border-line text-muted hover:text-accent" aria-label="Toggle theme">
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
          <ScanButton />
          <button className="lg:hidden" onClick={() => setOpen(!open)} aria-label="Menu">{open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}</button>
        </div>
        <nav className="hidden border-t border-line lg:block">
          <div className="mx-auto flex max-w-[1400px] gap-8 px-6">{links(false)}</div>
        </nav>
        {open && (
          <nav className="border-t border-line bg-panel py-2 lg:hidden">
            {links(true)}
            <div className="px-4 py-3 md:hidden"><ModeSwitch /></div>
          </nav>
        )}
      </header>
      <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-8 sm:px-6">
        <Routes>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/entities" element={<EntitiesPage />} />
          <Route path="/entities/:id" element={<EntityPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/reports/:id" element={<ReportsPage />} />
          <Route path="/how-it-works" element={<HowItWorksPage />} />
        </Routes>
      </main>
      <footer className="no-print mt-8 bg-nav text-white/80">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-8 gap-y-2 px-4 py-6 text-xs sm:px-6">
          <span className="flex items-center gap-2 font-bold text-white"><Logo className="h-6 w-6" /> InvestWatch</span>
          <span>PoC for HackNation 2026 · 5 entities from the KNF register of investment firms</span>
          <span>Classifier: mocked LLM (mock-v0)</span>
          <NavLink to="/how-it-works" className="ml-auto underline-offset-2 hover:underline">How it works</NavLink>
        </div>
      </footer>
    </div>
  )
}

export default function App() {
  return <BrowserRouter><Shell /></BrowserRouter>
}
