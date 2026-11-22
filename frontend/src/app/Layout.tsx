import { Badge } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { IconChevronRight, IconSearch } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useFindings, useOverview } from '../api/hooks';
import { useConnectionState } from '../api/socket';
import { AlertBell, ConnectionIndicator, DateRangeFilter } from '../components/Header';
import { RISK_HEX } from '../components/Terminal';
import { fmtInt, fmtTime } from '../lib/format';
import { PLATFORM_LABEL, RISK_LABEL } from '../lib/labels';
import { useDateRange, useRangeSearch } from '../lib/url';
import { useLiveFeed, useRealtime } from './realtime';

interface NavItem {
  to: string;
  label: string;
  title: string;
  key: string;
  count?: number;
}

const FONT_SIZES = [16, 18, 20];
const FONT_KEY = 'iw-font-size';

function readFontStep(): number {
  try {
    const n = Number(localStorage.getItem(FONT_KEY));
    return n >= 0 && n < FONT_SIZES.length ? n : 0;
  } catch {
    return 0;
  }
}

function crumbsFor(path: string, items: NavItem[]): { label: string; to?: string }[] {
  const item = items.find((n) => path === n.to || path.startsWith(`${n.to}/`));
  const out: { label: string; to?: string }[] = [{ label: 'Strona główna', to: '/' }];
  if (path.startsWith('/findings/')) return [...out, { label: 'Wszystkie wyniki', to: '/findings' }, { label: path.split('/')[2] }];
  if (path.startsWith('/campaigns/')) return [...out, { label: 'Kampanie', to: '/campaigns' }, { label: path.split('/')[2] }];
  if (path.startsWith('/modules/') && item) return [...out, { label: 'Moduły' }, { label: item.title }];
  return item ? [...out, { label: item.title }] : out;
}

export function Layout() {
  const { from, to, setRange } = useDateRange();
  const search = useRangeSearch();
  const connection = useConnectionState();
  const rt = useRealtime();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const o = useOverview(useMemo(() => ({ from, to }), [from, to])).data;
  const latest = useFindings({ from, to, sort: 'fetchedAt:desc', page: 1, pageSize: 8 });
  const feed = useLiveFeed(latest.data?.items);
  const health = useQuery({ queryKey: ['health'], queryFn: api.health, staleTime: Infinity });
  const [phrase, setPhrase] = useState('');
  const [fontStep, setFontStep] = useState(readFontStep);

  useEffect(() => {
    document.documentElement.style.fontSize = `${FONT_SIZES[fontStep]}px`;
    try {
      localStorage.setItem(FONT_KEY, String(fontStep));
    } catch {
      // bez zapisu ustawienie działa do odświeżenia strony
    }
  }, [fontStep]);

  const modules: NavItem[] = [
    { to: '/modules/1', label: 'M1 Finfluencerzy', title: 'Finfluencerzy i podmioty trzecie', key: 'F1', count: o?.byModule['1'] },
    { to: '/modules/2', label: 'M2 Ryzyko', title: 'Informacja o ryzyku', key: 'F2', count: o?.byModule['2'] },
    { to: '/modules/3', label: 'M3 Advisory', title: 'Shadow advisory', key: 'F3', count: o?.byModule['3'] },
    { to: '/modules/scam', label: 'Oszustwa', title: 'Oszustwa', key: 'F4', count: o?.scamTotal },
  ];
  const other: NavItem[] = [
    { to: '/findings', label: 'Wyniki', title: 'Wszystkie wyniki', key: 'F6' },
    { to: '/campaigns', label: 'Kampanie', title: 'Kampanie', key: 'F7' },
    { to: '/statistics', label: 'Statystyki', title: 'Statystyki', key: 'F8' },
    { to: '/history', label: 'Historia', title: 'Historia decyzji', key: 'F9' },
    { to: '/calibration', label: 'Kalibracja', title: 'Kalibracja progów', key: 'F10' },
  ];
  const all = [...modules, ...other];
  const crumbs = crumbsFor(pathname, all);

  // skróty klawiszowe (F5 zostaje dla odświeżania przeglądarki)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const item = all.find((n) => n.key === e.key);
      if (!item) return;
      e.preventDefault();
      navigate({ pathname: item.to, search });
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const onSearch = (e: FormEvent) => {
    e.preventDefault();
    const p = new URLSearchParams(search.replace(/^\?/, ''));
    if (phrase.trim()) p.set('q', phrase.trim());
    navigate({ pathname: '/findings', search: `?${p.toString()}` });
  };

  const link = (n: NavItem) => (
    <NavLink key={n.to} to={{ pathname: n.to, search }} title={`${n.title} (${n.key})`} className={({ isActive }) => `iw-nav-link${isActive ? ' active' : ''}`}>
      {n.label}
      {n.count !== undefined && <span className="iw-nav-count">{fmtInt(n.count)}</span>}
    </NavLink>
  );

  return (
    <>
      <Notifications position="bottom-right" limit={4} transitionDuration={250} containerWidth={380} zIndex={400} />
      <div className="iw-topline" />
      <header className="iw-header">
        <div className="iw-container iw-header-row">
          <Link to={{ pathname: '/modules/1', search }} className="iw-brand">
            <span className="iw-brand-name">InvestWatch</span>
            <span className="iw-brand-rule" aria-hidden />
            <span className="iw-brand-desc">
              Monitoring
              <br />
              treści
              <br />
              inwestycyjnych
            </span>
          </Link>
          <form className="iw-search" role="search" onSubmit={onSearch}>
            <input aria-label="Szukaj po frazie" placeholder="Szukaj po frazie..." value={phrase} onChange={(e) => setPhrase(e.currentTarget.value)} />
            <button type="submit" aria-label="Szukaj">
              <IconSearch size={20} stroke={1.5} />
            </button>
          </form>
          <div className="iw-tools">
            <DateRangeFilter from={from} to={to} onChange={setRange} />
            <button type="button" className="iw-tool" aria-label="Zmniejsz tekst" disabled={fontStep === 0} onClick={() => setFontStep((s) => s - 1)}>
              A−
            </button>
            <button type="button" className="iw-tool" aria-label="Powiększ tekst" disabled={fontStep === FONT_SIZES.length - 1} onClick={() => setFontStep((s) => s + 1)}>
              A+
            </button>
            {health.data?.demoReplay && (
              <Badge color="yellow" variant="filled" tt="none" title="Rekordy są prawdziwe, symulowany jest tylko moment ich pojawiania się">
                tryb demo
              </Badge>
            )}
            <ConnectionIndicator state={connection} />
            <AlertBell alerts={rt.alerts} unread={rt.unread} onOpen={rt.markAllRead} onClear={rt.clear} />
          </div>
        </div>
      </header>

      <nav className="iw-nav" aria-label="Menu główne">
        <div className="iw-container iw-nav-row">
          {modules.map(link)}
          <span className="iw-nav-sep" aria-hidden />
          {other.map(link)}
        </div>
      </nav>

      <div className="iw-ticker" aria-label="Najnowsze rekordy">
        <div className="iw-container iw-ticker-row">
          <span className="iw-ticker-label">Nowe rekordy</span>
          <div style={{ overflow: 'hidden', flex: 1 }}>
            {feed.length > 0 && (
              <div className="iw-ticker-track" key={feed[0].id}>
                {feed.map((f) => (
                  <Link key={f.id} to={`/findings/${f.id}${search}`} className="iw-ticker-item">
                    <span style={{ color: 'var(--iw-muted)' }}>{fmtTime(f.at)}</span> {PLATFORM_LABEL[f.platform]}, {f.author}{' '}
                    <span style={{ color: RISK_HEX[f.riskLevel], fontWeight: 600 }}>{RISK_LABEL[f.riskLevel]}</span>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <main className="iw-container iw-main">
        <ol className="iw-crumbs" aria-label="Ścieżka">
          {crumbs.map((c, i) => {
            const last = i === crumbs.length - 1;
            return (
              <li key={c.label}>
                {i > 0 && <IconChevronRight size={15} aria-hidden />}
                {last ? <span aria-current="page">{c.label}</span> : c.to ? <Link to={{ pathname: c.to, search }}>{c.label}</Link> : <span>{c.label}</span>}
              </li>
            );
          })}
        </ol>
        <Outlet />
      </main>
    </>
  );
}
