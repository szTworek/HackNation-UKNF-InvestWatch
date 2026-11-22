import { Anchor, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useQueryClient } from '@tanstack/react-query';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { qk } from '../api/hooks';
import { useSocketEvent } from '../api/socket';
import type { Finding, LoadProgress, RiskLevel, Thresholds } from '../api/types';
import { snippet } from '../lib/findings';
import { RISK_LABEL } from '../lib/labels';

/** Alert z gniazda `finding:high_risk` (HIGH i CRITICAL); odczytanie tylko lokalnie, w tej karcie. */
export interface LiveAlert {
  id: string;
  receivedAt: string;
  entity: string;
  title: string;
  riskLevel: RiskLevel;
  read: boolean;
}

interface AlertsState {
  alerts: LiveAlert[];
  unread: number;
  markRead: (id: string) => void;
  markAllRead: () => void;
}

const MAX_ALERTS = 50;
const REFRESH_MS = 5000;
const LIVE_KEYS = ['findings', 'overview', 'timeseries', 'entities', 'entity', 'entityOverview', 'entityItems', 'entityAlerts', 'item'];

export const ALERT_COLOR: Partial<Record<RiskLevel, string>> = { CRITICAL: 'red', HIGH: 'orange' };

const AlertsContext = createContext<AlertsState>({ alerts: [], unread: 0, markRead: () => undefined, markAllRead: () => undefined });

export function useAlerts(): AlertsState {
  return useContext(AlertsContext);
}

function toAlert(f: Finding): LiveAlert {
  return {
    id: f.id,
    receivedAt: new Date().toISOString(),
    entity: f.entities[0]?.name ?? f.author.displayName ?? f.author.handle,
    title: f.title ?? snippet(f.text, 90),
    riskLevel: f.riskLevel,
    read: false,
  };
}

/** Subskrypcje socketu: alerty wysokiego ryzyka, odświeżanie cache po zmianie statusu rekordu i progów. */
export function RealtimeProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [alerts, setAlerts] = useState<LiveAlert[]>([]);

  // nowe rekordy z oceny w tle: odświeżenie list i statystyk najwyżej raz na 5 s
  const lastRefresh = useRef(0);
  const refreshTimer = useRef<number | undefined>(undefined);
  const refreshLive = useCallback(() => {
    if (refreshTimer.current !== undefined) return;
    const run = () => {
      refreshTimer.current = undefined;
      lastRefresh.current = Date.now();
      for (const key of LIVE_KEYS) void qc.invalidateQueries({ queryKey: [key] });
    };
    refreshTimer.current = window.setTimeout(run, Math.max(0, lastRefresh.current + REFRESH_MS - Date.now()));
  }, [qc]);
  useEffect(() => () => window.clearTimeout(refreshTimer.current), []);

  useSocketEvent('finding:new', () => refreshLive());

  useSocketEvent('load:progress', (p: LoadProgress) => {
    qc.setQueryData(['load'], p);
  });

  useSocketEvent('finding:high_risk', (f: Finding) => {
    const a = toAlert(f);
    qc.setQueryData(qk.finding(f.id), f);
    void qc.invalidateQueries({ queryKey: ['findings'] });
    void qc.invalidateQueries({ queryKey: ['overview'] });
    setAlerts((prev) => [a, ...prev.filter((x) => x.id !== a.id)].slice(0, MAX_ALERTS));
    notifications.show({
      id: `alert-${a.id}`,
      color: ALERT_COLOR[a.riskLevel] ?? 'orange',
      title: `Ryzyko ${RISK_LABEL[a.riskLevel].toLowerCase()}: ${a.entity}`,
      autoClose: a.riskLevel === 'CRITICAL' ? false : 10_000,
      message: (
        <>
          <Text size="sm" lineClamp={2}>
            {a.title}
          </Text>
          <Anchor component={Link} to={`/findings/${a.id}`} size="sm" onClick={() => notifications.hide(`alert-${a.id}`)}>
            Otwórz rekord
          </Anchor>
        </>
      ),
    });
  });

  useSocketEvent('finding:updated', (f: Finding) => {
    qc.setQueryData(qk.finding(f.id), f);
    void qc.invalidateQueries({ queryKey: ['findings'] });
    void qc.invalidateQueries({ queryKey: ['overview'] });
  });

  useSocketEvent('thresholds:updated', (t: Thresholds) => {
    qc.setQueryData(qk.thresholds, t);
    for (const key of ['findings', 'finding', 'overview', 'timeseries', 'graph', 'indicator', 'thresholdsPreview']) {
      void qc.invalidateQueries({ queryKey: [key] });
    }
  });

  const markRead = useCallback((id: string) => setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, read: true } : a))), []);
  const markAllRead = useCallback(() => setAlerts((prev) => prev.map((a) => ({ ...a, read: true }))), []);
  const value = useMemo(() => ({ alerts, unread: alerts.filter((a) => !a.read).length, markRead, markAllRead }), [alerts, markRead, markAllRead]);

  return <AlertsContext.Provider value={value}>{children}</AlertsContext.Provider>;
}
