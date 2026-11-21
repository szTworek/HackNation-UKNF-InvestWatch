import { Anchor, Stack, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useQueryClient } from '@tanstack/react-query';
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { qk } from '../api/hooks';
import { useSocketEvent } from '../api/socket';
import type { Campaign, Finding, FindingSummary, Thresholds } from '../api/types';
import type { AlertItem } from '../components/Header';
import { activeFlags } from '../lib/findings';
import { FLAG_LABEL, PLATFORM_LABEL } from '../lib/labels';

/** Wiersz strumienia nowych rekordów. */
export interface FeedItem {
  id: string;
  at: string;
  platform: Finding['platform'];
  author: string;
  snippet: string;
  riskLevel: Finding['riskLevel'];
  scamP: number;
}

interface RealtimeCtx {
  /** ostatnie rekordy z socketu, najnowszy pierwszy */
  feed: FeedItem[];
  alerts: AlertItem[];
  unread: number;
  markAllRead: () => void;
  clear: () => void;
  /** nowe rekordy od ostatniego odświeżenia listy wyników */
  pendingNew: number;
  resetPending: () => void;
}

const Ctx = createContext<RealtimeCtx | null>(null);

const MAX_ALERTS = 50;

function describe(f: Finding, thresholds: Thresholds | undefined): string {
  const top = activeFlags(f, thresholds?.values)[0];
  return [`${f.author.handle}, ${PLATFORM_LABEL[f.platform]}`, top ? FLAG_LABEL[top.flag] : null].filter(Boolean).join('. ');
}

function toastBody(text: string, findingId: string) {
  return (
    <Stack gap={2}>
      <Text size="sm">{text}</Text>
      <Anchor component={Link} to={`/findings/${findingId}`} size="sm">
        Szczegóły
      </Anchor>
    </Stack>
  );
}

/** Subskrypcje socketu: toasty, dzwonek, licznik nowych rekordów i odświeżanie cache po zmianach. */
export function RealtimeProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [pendingNew, setPendingNew] = useState(0);
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const alerted = useRef(new Set<string>());

  const push = useCallback((a: AlertItem) => {
    setAlerts((prev) => [a, ...prev].slice(0, MAX_ALERTS));
  }, []);

  const thresholds = () => qc.getQueryData<Thresholds>(qk.thresholds);

  useSocketEvent('finding:new', (f: Finding) => {
    setPendingNew((n) => n + 1);
    const body = (f.kind === 'transcript' && f.transcript ? f.transcript : f.text).replace(/\s+/g, ' ');
    const item: FeedItem = { id: f.id, at: f.fetchedAt, platform: f.platform, author: f.author.handle, snippet: body.slice(0, 90), riskLevel: f.riskLevel, scamP: f.scam.p };
    setFeed((prev) => [item, ...prev].slice(0, 8));
    void qc.invalidateQueries({ queryKey: ['overview'] });
    void qc.invalidateQueries({ queryKey: ['timeseries'] });
  });

  useSocketEvent('campaign:new_member', ({ campaign, finding }: { campaign: Campaign; finding: Finding }) => {
    alerted.current.add(finding.id);
    const message = `${campaign.name}. ${describe(finding, thresholds())}`;
    notifications.show({
      title: 'Nowy element znanej kampanii',
      message: toastBody(message, finding.id),
      color: 'red',
      autoClose: 9000,
      withBorder: true,
    });
    push({ key: `c-${finding.id}`, findingId: finding.id, title: 'Nowy element kampanii', message, at: new Date().toISOString(), read: false, priority: 'campaign' });
    void qc.invalidateQueries({ queryKey: ['campaigns'] });
    void qc.invalidateQueries({ queryKey: qk.campaign(campaign.id) });
  });

  useSocketEvent('finding:high_risk', (f: Finding) => {
    if (alerted.current.has(f.id)) return;
    alerted.current.add(f.id);
    const title = f.riskLevel === 'CRITICAL' ? 'Krytyczne ryzyko' : 'Wysokie ryzyko';
    const message = describe(f, thresholds());
    notifications.show({ title, message: toastBody(message, f.id), color: f.riskLevel === 'CRITICAL' ? 'red' : 'orange', autoClose: 6000, withBorder: true });
    push({ key: `h-${f.id}`, findingId: f.id, title, message, at: new Date().toISOString(), read: false, priority: 'high_risk' });
  });

  useSocketEvent('finding:updated', (f: Finding) => {
    qc.setQueryData(qk.finding(f.id), f);
    void qc.invalidateQueries({ queryKey: ['findings'] });
    void qc.invalidateQueries({ queryKey: ['overview'] });
  });

  useSocketEvent('thresholds:updated', (t: Thresholds) => {
    qc.setQueryData(qk.thresholds, t);
    for (const key of ['findings', 'finding', 'overview', 'timeseries', 'campaigns', 'campaign', 'graph', 'indicator', 'thresholdsPreview']) {
      void qc.invalidateQueries({ queryKey: [key] });
    }
  });

  const value = useMemo<RealtimeCtx>(
    () => ({
      feed,
      alerts,
      unread: alerts.filter((a) => !a.read).length,
      markAllRead: () => setAlerts((prev) => (prev.some((a) => !a.read) ? prev.map((a) => ({ ...a, read: true })) : prev)),
      clear: () => setAlerts([]),
      pendingNew,
      resetPending: () => setPendingNew(0),
    }),
    [alerts, pendingNew, feed],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/** Strumień do tickera: rekordy z socketu, a zanim przyjdą – najnowsze z API. */
export function useLiveFeed(initial: FindingSummaryLike[] | undefined, limit = 8): FeedItem[] {
  const { feed } = useRealtime();
  return useMemo(() => {
    const seen = new Set(feed.map((f) => f.id));
    const base = (initial ?? [])
      .filter((s) => !seen.has(s.id))
      .map((s) => ({ id: s.id, at: s.fetchedAt, platform: s.platform, author: s.author.handle, snippet: s.snippet, riskLevel: s.riskLevel, scamP: s.scamP }));
    return [...feed, ...base].slice(0, limit);
  }, [feed, initial, limit]);
}

type FindingSummaryLike = Pick<FindingSummary, 'id' | 'fetchedAt' | 'platform' | 'author' | 'snippet' | 'riskLevel' | 'scamP'>;

export function useRealtime(): RealtimeCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useRealtime poza RealtimeProvider');
  return ctx;
}
