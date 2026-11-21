import { AppShell, Box, Burger, Group, Text } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { Notifications } from '@mantine/notifications';
import { useEffect, useMemo } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useFindings, useOverview } from '../api/hooks';
import { useConnectionState } from '../api/socket';
import { AlertBell, ConnectionIndicator, DateRangeFilter } from '../components/Header';
import { RISK_HEX } from '../components/Terminal';
import { fmtInt, fmtTime } from '../lib/format';
import { PLATFORM_LABEL, RISK_LABEL } from '../lib/labels';
import { useDateRange, useRangeSearch } from '../lib/url';
import { useLiveFeed, useRealtime } from './realtime';
import { MODULE_COLOR } from './theme';

interface NavItem {
  to: string;
  label: string;
  key?: string;
  color?: string;
  count?: number;
}

export function Layout() {
  const { from, to, setRange } = useDateRange();
  const search = useRangeSearch();
  const connection = useConnectionState();
  const rt = useRealtime();
  const navigate = useNavigate();
  const [opened, { toggle, close }] = useDisclosure(false);
  const o = useOverview(useMemo(() => ({ from, to }), [from, to])).data;
  const latest = useFindings({ from, to, sort: 'fetchedAt:desc', page: 1, pageSize: 8 });
  const feed = useLiveFeed(latest.data?.items);

  const groups: { title: string; items: NavItem[] }[] = [
    {
      title: 'Moduły',
      items: [
        { to: '/modules/1', label: 'M1 Finfluencerzy', key: 'F1', color: MODULE_COLOR[1], count: o?.byModule['1'] },
        { to: '/modules/2', label: 'M2 Informacja o ryzyku', key: 'F2', color: MODULE_COLOR[2], count: o?.byModule['2'] },
        { to: '/modules/3', label: 'M3 Shadow advisory', key: 'F3', color: MODULE_COLOR[3], count: o?.byModule['3'] },
        { to: '/modules/scam', label: 'Oszustwa', key: 'F4', color: MODULE_COLOR.scam, count: o?.scamTotal },
      ],
    },
    {
      title: 'Analiza',
      items: [
        { to: '/findings', label: 'Wszystkie wyniki', key: 'F6', count: o?.total },
        { to: '/campaigns', label: 'Kampanie', key: 'F7' },
        { to: '/statistics', label: 'Statystyki', key: 'F8' },
      ],
    },
    {
      title: 'Zespół i ustawienia',
      items: [
        { to: '/history', label: 'Historia decyzji', key: 'F9' },
        { to: '/calibration', label: 'Kalibracja progów', key: 'F10' },
      ],
    },
  ];

  // skróty klawiszowe (F5 zostaje dla odświeżania przeglądarki)
  useEffect(() => {
    const all = groups.flatMap((g) => g.items);
    const onKey = (e: KeyboardEvent) => {
      const item = all.find((n) => n.key === e.key);
      if (!item) return;
      e.preventDefault();
      navigate({ pathname: item.to, search });
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  return (
    <AppShell header={{ height: 56 }} navbar={{ width: 250, breakpoint: 'sm', collapsed: { mobile: !opened } }} padding="md">
      <Notifications position="bottom-right" limit={4} transitionDuration={250} containerWidth={380} zIndex={400} />

      <AppShell.Header style={{ borderBottom: '1px solid var(--iw-border)' }}>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" aria-label="Menu" />
            <Box w={30} h={30} style={{ borderRadius: 6, background: 'var(--iw-primary)', display: 'grid', placeItems: 'center' }} aria-hidden>
              <Text c="white" fw={700} size="sm">
                IW
              </Text>
            </Box>
            <div>
              <Text fw={700} lh={1.1}>
                InvestWatch
              </Text>
              <Text size="xs" c="dimmed" lh={1.1}>
                Monitoring treści inwestycyjnych UKNF
              </Text>
            </div>
          </Group>
          <Group gap="md" wrap="nowrap">
            <DateRangeFilter from={from} to={to} onChange={setRange} />
            <ConnectionIndicator state={connection} />
            <AlertBell alerts={rt.alerts} unread={rt.unread} onOpen={rt.markAllRead} onClear={rt.clear} />
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar style={{ borderRight: '1px solid var(--iw-border)' }}>
        <Box component="nav" aria-label="Nawigacja" py={4}>
          {groups.map((g) => (
            <div key={g.title}>
              <div className="iw-nav-group">{g.title}</div>
              {g.items.map((n) => (
                <NavLink key={n.to} to={{ pathname: n.to, search }} className={({ isActive }) => `iw-nav-link${isActive ? ' active' : ''}`} onClick={close}>
                  {n.color && <span className="iw-nav-swatch" style={{ background: n.color }} aria-hidden />}
                  <span>{n.label}</span>
                  {n.count !== undefined && <span className="iw-nav-count">{fmtInt(n.count)}</span>}
                  {n.key && <span className="iw-nav-key" style={n.count === undefined ? { marginLeft: 'auto' } : undefined}>{n.key}</span>}
                </NavLink>
              ))}
            </div>
          ))}
        </Box>
      </AppShell.Navbar>

      <AppShell.Main>
        <div className="iw-ticker" aria-label="Najnowsze rekordy" style={{ margin: 'calc(var(--mantine-spacing-md) * -1) calc(var(--mantine-spacing-md) * -1) var(--mantine-spacing-md)' }}>
          <span className="iw-ticker-label">Nowe rekordy</span>
          <div style={{ overflow: 'hidden', flex: 1 }}>
            {feed.length > 0 && (
              <div className="iw-ticker-track" key={feed[0].id}>
                {feed.map((f) => (
                  <Link key={f.id} to={`/findings/${f.id}${search}`} className="iw-ticker-item">
                    <span style={{ color: 'var(--iw-muted)' }}>{fmtTime(f.at)}</span> {PLATFORM_LABEL[f.platform]}, {f.author}{' '}
                    <span style={{ color: RISK_HEX[f.riskLevel], fontWeight: 600 }}>{RISK_LABEL[f.riskLevel]}</span>{' '}
                    <span style={{ color: 'var(--iw-muted)' }}>„{f.snippet.slice(0, 60)}”</span>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
        <Box maw={1500} mx="auto">
          <Outlet />
        </Box>
      </AppShell.Main>
    </AppShell>
  );
}
