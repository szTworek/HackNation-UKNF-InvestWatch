import { Box, Button, Grid, Group, Menu, MultiSelect, Pagination, Paper, Select, SimpleGrid, Slider, Stack, Text, TextInput, Title } from '@mantine/core';
import { useDebouncedCallback, useDebouncedValue } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconChevronDown, IconDownload, IconSearch } from '@tabler/icons-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useBulkStatus, useFindings, useRules, useThresholds, useUpdateStatus } from '../api/hooks';
import type { FindingSummary, FindingsQuery, FlagKey, ModuleId, Platform, RiskLevel, RuleDef, Status } from '../api/types';
import { MODULE_COLOR } from '../app/theme';
import { StatusMenuItems } from '../components/FindingsTable';
import { ModuleTable, type ModuleKey } from '../components/ModuleTable';
import { ErrorState, Loading } from '../components/PageState';
import { Meter, Panel } from '../components/Terminal';
import { fmtInt, fmtProb, todayIso } from '../lib/format';
import {
  ALL_FLAGS,
  FLAG_LABEL,
  INSTRUMENT_LABEL,
  PLATFORMS,
  PLATFORM_LABEL,
  RISK_LABEL,
  RISK_LEVELS,
  STATUSES,
  STATUS_LABEL,
} from '../lib/labels';
import { PAGE_SIZES, toFindingsQuery, useDateRange, useFindingsFilters, useRangeSearch } from '../lib/url';

interface ModuleConfig {
  title: string;
  scope: string;
  color: string;
  base: Partial<FindingsQuery>;
  report: ModuleId;
}

const CONFIG: Record<ModuleKey, ModuleConfig> = {
  '1': {
    title: 'Finfluencerzy i podmioty trzecie',
    scope: 'Reklamy zarejestrowanych firm inwestycyjnych publikowane przez osoby trzecie, w tym finfluencerów. Raport zestawia firmę, reklamującego, treść i URL.',
    color: MODULE_COLOR[1],
    base: { module: [1] },
    report: 1,
  },
  '2': {
    title: 'Informacja o ryzyku',
    scope: 'Materiały marketingowe zarejestrowanych firm inwestycyjnych sprawdzane według 18 kryteriów informacji o ryzyku.',
    color: MODULE_COLOR[2],
    base: { module: [2] },
    report: 2,
  },
  '3': {
    title: 'Shadow advisory',
    scope: 'Podmioty spoza rejestru KNF, które faktycznie świadczą doradztwo inwestycyjne. Raport zestawia podmiot, treść oferty i URL.',
    color: MODULE_COLOR[3],
    base: { module: [3] },
    report: 3,
  },
};

// ---------------------------------------------------------------------------
// Podsumowanie modułu (liczone z rekordów modułu w zakresie dat)
// ---------------------------------------------------------------------------

function top(values: (string | undefined)[], n = 5): { label: string; count: number }[] {
  const m = new Map<string, number>();
  for (const v of values) if (v) m.set(v, (m.get(v) ?? 0) + 1);
  return [...m.entries()].map(([label, count]) => ({ label, count })).sort((a, b) => b.count - a.count).slice(0, n);
}

function TopList({ title, rows, color }: { title: string; rows: { label: string; count: number }[]; color: string }) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <div>
      <Text size="sm" fw={600} mb={8}>
        {title}
      </Text>
      {rows.length === 0 ? (
        <Text size="sm" c="dimmed">
          Brak danych.
        </Text>
      ) : (
        <Stack gap={8}>
          {rows.map((r) => (
            <div key={r.label}>
              <Group justify="space-between" gap="xs" wrap="nowrap" mb={3}>
                <Text size="sm" truncate>
                  {r.label}
                </Text>
                <Text size="sm" fw={600} className="iw-num">
                  {fmtInt(r.count)}
                </Text>
              </Group>
              <Meter value={r.count / max} color={color} h={5} />
            </div>
          ))}
        </Stack>
      )}
    </div>
  );
}

function Insights({ moduleKey, items, rules, color }: { moduleKey: ModuleKey; items: FindingSummary[]; rules: RuleDef[]; color: string }) {
  const ruleName = new Map(rules.map((r) => [r.id, r.name]));
  switch (moduleKey) {
    case '1': {
      const noAd = items.filter((i) => i.adDisclosure === 'MISSING').length;
      return (
        <SimpleGrid cols={{ base: 1, md: 3 }} spacing="xl">
          <TopList title="Promowane firmy" rows={top(items.map((i) => i.firm?.name))} color={color} />
          <TopList title="Najaktywniejsi reklamujący" rows={top(items.map((i) => i.advertiser))} color={color} />
          <div>
            <Text size="sm" fw={600} mb={8}>
              Reklamy bez oznaczenia
            </Text>
            <Text fz={32} fw={600} c="red.8" className="iw-num">
              {fmtInt(noAd)}
            </Text>
            <Text size="sm" c="dimmed">
              z {fmtInt(items.length)} materiałów w module
            </Text>
          </div>
        </SimpleGrid>
      );
    }
    case '2':
      return (
        <SimpleGrid cols={{ base: 1, md: 2 }} spacing="xl">
          <TopList title="Najczęściej wskazywane reguły" rows={top(items.flatMap((i) => i.violations.map((v) => ruleName.get(v) ?? v)), 6)} color={color} />
          <TopList title="Firmy z regułami do weryfikacji" rows={top(items.filter((i) => i.violations.length).map((i) => i.firm?.name))} color={color} />
        </SimpleGrid>
      );
    case '3':
      return (
        <SimpleGrid cols={{ base: 1, md: 2 }} spacing="xl">
          <TopList title="Podmioty spoza rejestru" rows={top(items.filter((i) => i.advisor?.register !== 'REGISTERED').map((i) => i.advisor?.name))} color={color} />
          <TopList title="Instrumenty w ofertach" rows={top(items.flatMap((i) => i.instruments.map((x) => INSTRUMENT_LABEL[x])))} color={color} />
        </SimpleGrid>
      );
  }
}

function Kpi({ label, value, color }: { label: string; value?: number; color?: string }) {
  return (
    <Paper p="md">
      <Text size="sm" c="dimmed">
        {label}
      </Text>
      <Text fz={28} fw={600} c={color} className="iw-num" lh={1.3}>
        {value === undefined ? '—' : fmtInt(value)}
      </Text>
    </Paper>
  );
}

// ---------------------------------------------------------------------------

export function ModuleRoute() {
  const { key } = useParams();
  if (key !== '1' && key !== '2' && key !== '3') return <Navigate to="/modules/1" replace />;
  return <ModulePage moduleKey={key} key={key} />;
}

export function ModulePage({ moduleKey }: { moduleKey: ModuleKey }) {
  const cfg = CONFIG[moduleKey];
  const navigate = useNavigate();
  const rangeSearch = useRangeSearch();
  const { from, to } = useDateRange();
  const { filters, update, reset } = useFindingsFilters();
  // próg pewności modułu: podgląd listy bez zapisu (zapis w Kalibracji)
  const savedThreshold = useThresholds().data?.values[`module.M${moduleKey}`] ?? 0.5;
  const [threshold, setThreshold] = useState<number | null>(null);
  const [debouncedThreshold] = useDebouncedValue(threshold, 200);
  const confidence = debouncedThreshold !== null && Math.abs(debouncedThreshold - savedThreshold) > 1e-9 ? debouncedThreshold : undefined;
  const base = useMemo(() => ({ ...cfg.base, confidence }), [cfg.base, confidence]);
  const query = useMemo(() => ({ ...toFindingsQuery(filters, { from, to }), ...base }), [filters, from, to, base]);
  const findings = useFindings(query);
  // podsumowanie: wszystkie rekordy modułu w zakresie dat (lekkie wiersze)
  const all = useFindings({ from, to, ...base, page: 1, pageSize: 200, sort: 'fetchedAt:desc' });
  const atSaved = useFindings({ from, to, ...cfg.base, page: 1, pageSize: 1 });
  // liczniki z pola total, niezależne od limitu strony
  const countBase = { from, to, ...base, page: 1, pageSize: 1 };
  const newToday = useFindings({ ...countBase, from: todayIso(), to: todayIso() });
  const highRisk = useFindings({ ...countBase, riskLevel: ['HIGH', 'CRITICAL'] });
  const waiting = useFindings({ ...countBase, status: ['NEW'] });
  const rules = useRules();
  const updateStatus = useUpdateStatus();
  const bulk = useBulkStatus();

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [q, setQ] = useState(filters.q);
  useEffect(() => setQ(filters.q), [filters.q]);
  const pushQ = useDebouncedCallback((v: string) => update({ q: v }), 350);
  const moreActive = filters.status.length + filters.flag.length;
  const [more, setMore] = useState(moreActive > 0);

  const items = useMemo(() => findings.data?.items ?? [], [findings.data]);
  const total = findings.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / filters.pageSize));
  const moduleItems = all.data?.items ?? [];

  const prevIds = useRef<Set<string> | null>(null);
  const [freshIds, setFreshIds] = useState<Set<string>>(new Set());
  useEffect(() => {
    const ids = new Set(items.map((i) => i.id));
    if (prevIds.current) setFreshIds(new Set([...ids].filter((id) => !prevIds.current?.has(id))));
    prevIds.current = ids;
  }, [items]);

  const changeStatus = (id: string, status: Status) =>
    updateStatus.mutate({ id, status }, { onError: (e) => notifications.show({ color: 'red', title: 'Nie zapisano statusu', message: e.message }) });

  const bulkStatus = (status: Status) =>
    bulk.mutate(
      { ids: [...selected], status },
      {
        onSuccess: (res) => {
          notifications.show({ color: 'green', title: 'Status zmieniony', message: `${res.items.length} rekordów: ${STATUS_LABEL[status]}` });
          setSelected(new Set());
        },
        onError: (e) => notifications.show({ color: 'red', title: 'Nie zapisano statusu', message: e.message }),
      },
    );

  const hasFilters = !!filters.q || filters.platform.length + filters.module.length + filters.riskLevel.length + filters.status.length + filters.flag.length > 0;

  return (
    <Stack gap="md">
      {/* nagłówek modułu */}
      <Box pb="lg" style={{ borderBottom: '1px solid var(--iw-border)' }}>
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <div>
            <Title order={2}>
              {cfg.title}
            </Title>
            <Text mt={6} maw={820} c="var(--iw-muted)">
              {cfg.scope}
            </Text>
          </div>
          <Button component="a" href={api.reportUrl(cfg.report, query)} download variant="default" bg="var(--iw-soft)" bd="0" leftSection={<IconDownload size={16} />}>
            Raport CSV
          </Button>
        </Group>
      </Box>

      <SimpleGrid cols={{ base: 2, md: 4 }} spacing="md">
        <Kpi label="Rekordów w zakresie dat" value={all.data?.total} />
        <Kpi label="Nowe dziś" value={newToday.data?.total} />
        <Kpi label="Wysokie i krytyczne" value={highRisk.data?.total} color="#c2500a" />
        <Kpi label="Czeka na decyzję" value={waiting.data?.total} color={cfg.color} />
      </SimpleGrid>


      <Paper p="sm">
        <Group gap="md" wrap="nowrap">
          <Text size="sm" fw={600} style={{ flexShrink: 0 }}>
            Próg pewności modelu
          </Text>
          <Slider
            flex={1}
            maw={420}
            min={0}
            max={1}
            step={0.01}
            value={threshold ?? savedThreshold}
            onChange={setThreshold}
            label={fmtProb}
            aria-label="Próg pewności modelu"
            color={confidence === undefined ? cfg.color : 'orange'}
            size="sm"
          />
          <Text size="sm" fw={600} w={40} className="iw-num">
            {fmtProb(threshold ?? savedThreshold)}
          </Text>
          <Text size="sm" c="dimmed">
            {confidence === undefined
              ? `Zapisany próg. Rekordów w module: ${fmtInt(atSaved.data?.total ?? 0)}.`
              : `Podgląd: ${fmtInt(atSaved.data?.total ?? 0)} → ${fmtInt(all.data?.total ?? 0)} rekordów (zapisany próg ${fmtProb(savedThreshold)}).`}
          </Text>
          {confidence !== undefined && (
            <Group gap="xs" style={{ flexShrink: 0 }}>
              <Button variant="default" size="xs" onClick={() => setThreshold(null)}>
                Przywróć
              </Button>
              <Button component={Link} to="/calibration" variant="light" size="xs">
                Zapisz w kalibracji
              </Button>
            </Group>
          )}
        </Group>
      </Paper>

      <Panel
        title={`Rekordy (${fmtInt(total)})`}
        flush
        right={
          <Group gap="xs">
            {selected.size > 0 && (
              <Menu position="bottom-end">
                <Menu.Target>
                  <Button size="xs" variant="light" rightSection={<IconChevronDown size={12} />} loading={bulk.isPending}>
                    Zmień status zaznaczonych ({selected.size})
                  </Button>
                </Menu.Target>
                <Menu.Dropdown>
                  <StatusMenuItems onSelect={bulkStatus} />
                </Menu.Dropdown>
              </Menu>
            )}
          </Group>
        }
      >
        <Box p="sm" style={{ borderBottom: '1px solid var(--iw-border-soft)' }}>
          <Grid gutter="xs" align="flex-end">
            <Grid.Col span="content">
              <TextInput
                aria-label="Szukaj"
                placeholder="Szukaj w treści, autorze, URL"
                leftSection={<IconSearch size={14} />}
                value={q}
                onChange={(e) => {
                  setQ(e.currentTarget.value);
                  pushQ(e.currentTarget.value);
                }}
                w={240}
                size="xs"
              />
            </Grid.Col>
            <Grid.Col span="content">
              <MultiSelect label="Źródło" size="xs" w={160} data={PLATFORMS.map((p) => ({ value: p, label: PLATFORM_LABEL[p] }))} value={filters.platform} onChange={(v) => update({ platform: v as Platform[] })} clearable />
            </Grid.Col>
            <Grid.Col span="content">
              <MultiSelect label="Ryzyko" size="xs" w={160} data={RISK_LEVELS.map((r) => ({ value: r, label: RISK_LABEL[r] }))} value={filters.riskLevel} onChange={(v) => update({ riskLevel: v as RiskLevel[] })} clearable />
            </Grid.Col>
            <Grid.Col span="content">
              <MultiSelect label="Status" size="xs" w={170} data={STATUSES.map((s) => ({ value: s, label: STATUS_LABEL[s] }))} value={filters.status} onChange={(v) => update({ status: v as Status[] })} clearable />
            </Grid.Col>
            <Grid.Col span="content">
              <Button variant="subtle" size="xs" onClick={() => setMore((v) => !v)}>
                {more ? 'Mniej filtrów' : `Więcej filtrów${moreActive ? ` (${moreActive})` : ''}`}
              </Button>
              {hasFilters && (
                <Button variant="subtle" color="gray" size="xs" onClick={reset}>
                  Wyczyść
                </Button>
              )}
            </Grid.Col>
          </Grid>
          {more && (
            <Group mt="xs">
              <MultiSelect label="Wykryta cecha" size="xs" w={260} data={ALL_FLAGS.map((f) => ({ value: f, label: FLAG_LABEL[f] }))} value={filters.flag} onChange={(v) => update({ flag: v as FlagKey[] })} searchable clearable />
            </Group>
          )}
        </Box>

        {findings.isError ? (
          <ErrorState error={findings.error} onRetry={() => void findings.refetch()} />
        ) : !findings.data || !rules.data ? (
          <Loading />
        ) : items.length === 0 ? (
          <Text size="sm" c="dimmed" p="md">
            Brak rekordów dla tych filtrów.
          </Text>
        ) : (
          <ModuleTable
            moduleKey={moduleKey}
            items={items}
            rules={rules.data}
            selected={selected}
            freshIds={freshIds}
            sort={filters.sort}
            onSort={(sort) => update({ sort })}
            onToggle={(id) =>
              setSelected((prev) => {
                const next = new Set(prev);
                if (next.has(id)) next.delete(id);
                else next.add(id);
                return next;
              })
            }
            onToggleAll={(checked) =>
              setSelected((prev) => {
                const next = new Set(prev);
                for (const f of items) {
                  if (checked) next.add(f.id);
                  else next.delete(f.id);
                }
                return next;
              })
            }
            onOpen={(id) => navigate(`/findings/${id}${rangeSearch}`)}
            onStatus={changeStatus}
          />
        )}

        <Group justify="space-between" p="sm" style={{ borderTop: '1px solid var(--iw-border-soft)' }}>
          <Select aria-label="Wierszy na stronie" size="xs" w={80} data={PAGE_SIZES.map(String)} value={String(filters.pageSize)} onChange={(v) => v && update({ pageSize: Number(v) })} allowDeselect={false} />
          <Pagination size="sm" total={pages} value={Math.min(filters.page, pages)} onChange={(page) => update({ page })} />
        </Group>
      </Panel>

      <Panel title={all.data && all.data.total > moduleItems.length ? `Podsumowanie: ostatnie ${fmtInt(moduleItems.length)} z ${fmtInt(all.data.total)}` : 'Podsumowanie modułu'}>
        {all.data && rules.data ? <Insights moduleKey={moduleKey} items={moduleItems} rules={rules.data} color={cfg.color} /> : <Loading />}
      </Panel>
    </Stack>
  );
}