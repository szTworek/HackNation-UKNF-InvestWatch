import { Notifications } from '@mantine/notifications';
import { IconChevronRight, IconSearch } from '@tabler/icons-react';
import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useEntities, useOverview } from '../api/hooks';
import { useConnectionState } from '../api/socket';
import { AlertBell, ConnectionIndicator, DateRangeFilter, LoadIndicator } from '../components/Header';
import { JobControl } from '../components/JobControl';
import { fmtInt } from '../lib/format';
import { useDateRange, useRangeSearch } from '../lib/url';

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

function crumbsFor(path: string, items: NavItem[], entityName?: string): { label: string; to?: string }[] {
  const item = items.find((n) => path === n.to || path.startsWith(`${n.to}/`));
  const out: { label: string; to?: string }[] = [{ label: 'Strona główna', to: '/' }];
  if (path.startsWith('/modules/') && item) return [...out, { label: 'Moduły' }, { label: item.title }];
  if (path.startsWith('/findings/')) return [...out, { label: 'Rekord' }, { label: path.split('/')[2] }];
  if (path.startsWith('/entities/')) return [...out, { label: 'Podmioty', to: '/entities' }, { label: entityName ?? path.split('/')[2] }];
  if (path.startsWith('/reports/')) return [...out, { label: 'Raporty', to: '/reports' }, { label: entityName ?? path.split('/')[2] }];
  return item ? [...out, { label: item.title }] : out;
}

export function Layout() {
  const { from, to, setRange } = useDateRange();
  const search = useRangeSearch();
  const connection = useConnectionState();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const entities = useEntities();
  const o = useOverview(useMemo(() => ({ from, to }), [from, to])).data;
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
    { to: '/statistics', label: 'Statystyki', title: 'Statystyki', key: 'F4' },
    { to: '/entities', label: 'Podmioty', title: 'Podmioty z rejestru KNF', key: 'F6', count: entities.data?.length },
    { to: '/reports', label: 'Raporty', title: 'Raporty podmiotów', key: 'F7' },
  ];
  const moduleTabs: NavItem[] = [
    { to: '/modules/1', label: 'Finfluencerzy', title: 'Finfluencerzy i podmioty trzecie', key: 'F1', count: o?.byModule['1'] },
    { to: '/modules/2', label: 'Informacja o ryzyku', title: 'Informacja o ryzyku', key: 'F2', count: o?.byModule['2'] },
    { to: '/modules/3', label: 'Shadow advisory', title: 'Shadow advisory', key: 'F3', count: o?.byModule['3'] },
  ];
  const other: NavItem[] = [
    { to: '/history', label: 'Historia', title: 'Historia decyzji', key: 'F9' },
    { to: '/calibration', label: 'Kalibracja', title: 'Kalibracja progów', key: 'F10' },
  ];
  const all = [...moduleTabs, ...modules, ...other];
  const entityId = pathname.match(/^\/(?:entities|reports)\/([^/]+)/)?.[1];
  const crumbs = crumbsFor(pathname, all, entities.data?.find((e) => e.id === entityId)?.name);

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
    p.delete('q');
    if (phrase.trim()) p.set('q', phrase.trim());
    navigate({ pathname: '/entities', search: `?${p.toString()}` });
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
          <Link to={{ pathname: '/statistics', search }} className="iw-brand">
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
            <input aria-label="Szukaj podmiotu" placeholder="Szukaj podmiotu..." value={phrase} onChange={(e) => setPhrase(e.currentTarget.value)} />
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
            <JobControl />
            <LoadIndicator />
            <AlertBell />
            <ConnectionIndicator state={connection} />
          </div>
        </div>
      </header>

      <nav className="iw-nav" aria-label="Menu główne">
        <div className="iw-container iw-nav-row">
          {moduleTabs.map(link)}
          <span className="iw-nav-sep" aria-hidden />
          {modules.map(link)}
          <span className="iw-nav-sep" aria-hidden />
          {other.map(link)}
        </div>
      </nav>

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
