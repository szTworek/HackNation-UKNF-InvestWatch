import { Anchor, Badge, Grid, Group, Paper, SegmentedControl, SimpleGrid, Stack, Table, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { lazy, Suspense, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { SourcePlatform } from '../api/entityTypes';
import { useEntityOverview, useOverview, useTimeseries } from '../api/hooks';
import type { Timeseries, TimeseriesGroupBy } from '../api/types';
import { MockBadge, shortUrl } from '../components/EntityParts';
import { KpiCard } from '../components/KpiCard';
import { ErrorState, Loading } from '../components/PageState';
import { Pipeline } from '../components/Pipeline';
import { fmtDate, fmtInt } from '../lib/format';
import { CONTENT_TYPES, CONTENT_TYPE_LABEL, ENTITY_MODULE_COLOR, MODULES, MODULE_LABEL, PLATFORMS, PLATFORM_LABEL, SOURCE_PLATFORM_LABEL, ruleModule, ruleText } from '../lib/labels';
import { useDateRange } from '../lib/url';

const TrendChart = lazy(() => import('../components/Charts').then((m) => ({ default: m.TrendChart })));
const DistributionBars = lazy(() => import('../components/Charts').then((m) => ({ default: m.DistributionBars })));
const FindingsByDayChart = lazy(() => import('../components/EntityCharts').then((m) => ({ default: m.FindingsByDayChart })));
const EntityHeatmap = lazy(() => import('../components/EntityCharts').then((m) => ({ default: m.EntityHeatmap })));
const LabeledBars = lazy(() => import('../components/EntityCharts').then((m) => ({ default: m.LabeledBars })));

/** Seria oszustw nie jest pokazywana (moduł oszustw usunięty z panelu). */
const withoutScam = (t: Timeseries): Timeseries => ({ ...t, keys: t.keys.filter((k) => k !== 'scam') });

export function Statistics() {
  const { from, to } = useDateRange();
  const range = useMemo(() => ({ from, to }), [from, to]);
  const [groupBy, setGroupBy] = useState<TimeseriesGroupBy>('module');
  const [dist, setDist] = useState<'platform' | 'contentType'>('platform');
  const eo = useEntityOverview();
  const overview = useOverview(range);
  const series = useTimeseries(range, groupBy);
  const health = useQuery({ queryKey: ['health'], queryFn: api.health, staleTime: Infinity });

  const e = eo.data;
  const o = overview.data;

  return (
    <Stack gap="lg">
      <div>
        <Title order={2}>Statystyki</Title>
        <Text c="dimmed" mt={4}>
          Reklamy, posty i strony WWW podmiotów z rejestru KNF{e ? `, stan na ${fmtDate(e.generatedAt)}` : ''}.
        </Text>
      </div>

      {eo.isError ? (
        <ErrorState error={eo.error} onRetry={() => void eo.refetch()} />
      ) : (
        <>
          <SimpleGrid cols={{ base: 2, sm: 4, lg: 7 }}>
            <KpiCard label="Wpisy w rejestrze KNF" value={e ? fmtInt(e.totals.knfEntries) : '—'} hint={e ? `${fmtInt(e.totals.entities)} podmiotów` : undefined} loading={!e} to="/entities" />
            <KpiCard label="Monitorowane podmioty" value={e?.totals.entitiesWithData ?? '—'} hint="z zebranymi danymi" loading={!e} to="/entities" />
            <KpiCard label="Rekordy" value={e ? fmtInt(e.totals.items) : '—'} hint="reklamy, posty, filmy" loading={!e} />
            <KpiCard label="Wyniki" value={e ? fmtInt(e.totals.findings) : '—'} hint="trzy moduły" loading={!e} />
            <KpiCard label="Nowe alerty" value={e?.totals.alertsNew ?? '—'} loading={!e} accent="var(--iw-red)" />
            <KpiCard label="Strony WWW" value={e?.totals.pages ?? '—'} hint="monitorowane" loading={!e} />
            <KpiCard label="Zmiany stron" value={e?.totals.pageChanges30d ?? '—'} hint="wykryte przez monitor" loading={!e} />
          </SimpleGrid>

          <Grid gutter="lg">
            <Grid.Col span={{ base: 12, lg: 8 }}>
              <Paper p="lg" h="100%">
                <Group gap={8} mb="md">
                  <Title order={4}>Wyniki dziennie</Title>
                </Group>
                <Suspense fallback={<Loading />}>{e ? <FindingsByDayChart data={e.findingsByDay} height={280} /> : <Loading />}</Suspense>
              </Paper>
            </Grid.Col>
            <Grid.Col span={{ base: 12, lg: 4 }}>
              <Paper p="lg" h="100%">
                <Group gap={8}>
                  <Title order={4}>Podmiot × moduł</Title>
                </Group>
                <Text size="xs" c="dimmed" mb="sm">
                  Średni wynik klasyfikatora (0–100)
                </Text>
                <Suspense fallback={<Loading />}>{e ? <EntityHeatmap rows={e.heatmap} /> : <Loading />}</Suspense>
              </Paper>
            </Grid.Col>
          </Grid>

          <Grid gutter="lg">
            <Grid.Col span={{ base: 12, md: 6, lg: 4 }}>
              <Paper p="lg" h="100%">
                <Title order={4} mb="md">
                  Rekordy wg źródła
                </Title>
                <Suspense fallback={<Loading />}>
                  {e ? (
                    <DistributionBars
                      data={Object.entries(e.itemsByPlatform).map(([p, v]) => ({
                        label: p === 'website' ? 'Strony WWW (strony)' : (SOURCE_PLATFORM_LABEL[p as SourcePlatform] ?? p),
                        value: v ?? 0,
                      }))}
                    />
                  ) : (
                    <Loading />
                  )}
                </Suspense>
                {e && (
                  <>
                    <Title order={5} mt="lg" mb={2}>
                      Czytelność oznaczeń
                    </Title>
                    <Text size="xs" c="dimmed" mb="sm">
                      Rekordy z obrazem reklamy, stałe progi (R04, R05, R08)
                    </Text>
                    <Suspense fallback={<Loading />}>
                      <DistributionBars
                        data={[
                          { label: 'Oznaczenie czytelne', value: e.legibility.ok },
                          { label: 'Oznaczenie słabo widoczne', value: e.legibility.problem },
                          { label: 'Brak oznaczenia', value: e.legibility.no_disclosure },
                        ]}
                      />
                    </Suspense>
                  </>
                )}
              </Paper>
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 6, lg: 4 }}>
              <Paper p="lg" h="100%">
                <Group gap={8} mb="md">
                  <Title order={4}>Najczęstsze naruszenia</Title>
                </Group>
                <Suspense fallback={<Loading />}>
                  {e ? (
                    <LabeledBars
                      rows={e.topRules.slice(0, 7).map((r) => ({ key: r.ruleId, label: ruleText(r.ruleId, r.label), value: r.count, color: ENTITY_MODULE_COLOR[ruleModule(r.ruleId)] }))}
                    />
                  ) : (
                    <Loading />
                  )}
                </Suspense>
              </Paper>
            </Grid.Col>
            <Grid.Col span={{ base: 12, lg: 4 }}>
              <Paper p="lg" h="100%">
                <Title order={4} mb="md">
                  Zmiany stron WWW
                </Title>
                {!e ? (
                  <Loading />
                ) : !e.recentChanges.length ? (
                  <Text size="sm" c="dimmed">
                    Brak zmian.
                  </Text>
                ) : (
                  <Stack gap="sm">
                    {e.recentChanges.map((c) => (
                      <div key={c.id}>
                        <Group gap={6}>
                          <Anchor component={Link} to={`/entities/${c.entityId}?tab=websites&change=${c.id}`} size="sm" fw={600}>
                            {c.entityName}
                          </Anchor>
                          <Text size="xs" c="dimmed">
                            {fmtDate(c.detectedAt)} · {shortUrl(c.url)}
                          </Text>
                          {c.mock && <MockBadge hint="Zmiana wobec zrzutu zrekonstruowanego syntetycznie" />}
                        </Group>
                        <Text size="sm" lineClamp={2}>
                          {c.summary}
                        </Text>
                      </div>
                    ))}
                  </Stack>
                )}
              </Paper>
            </Grid.Col>
          </Grid>
        </>
      )}

      <Pipeline o={e} />

      <Group gap="sm" mt="md">
        <Title order={3}>Strumień treści</Title>
        <Badge variant="light" color={health.data?.dataMode === 'real' ? 'knf' : 'yellow'}>
          {health.data?.dataMode === 'real' ? 'dane rzeczywiste (ai-service)' : 'atrapa'}
        </Badge>
      </Group>
      <Text c="dimmed" mt={-12}>
        Rekordy z monitoringu mediów w wybranym zakresie dat (filtr w nagłówku). Szczegóły rekordu są dostępne z historii decyzji i paska nowych
        rekordów.
      </Text>
      {overview.isError ? (
        <ErrorState error={overview.error} onRetry={() => void overview.refetch()} />
      ) : (
        <>
          <Paper p="lg">
            <Group justify="space-between" mb="md">
              <Title order={4}>Rekordy strumienia dziennie</Title>
              <SegmentedControl
                size="xs"
                value={groupBy}
                onChange={(v) => setGroupBy(v as TimeseriesGroupBy)}
                data={[
                  { value: 'module', label: 'Moduł' },
                  { value: 'platform', label: 'Platforma' },
                  { value: 'riskLevel', label: 'Ryzyko' },
                ]}
              />
            </Group>
            <Suspense fallback={<Loading />}>{series.data ? <TrendChart data={withoutScam(series.data)} height={280} /> : <Loading />}</Suspense>
          </Paper>
          <Grid gutter="lg">
            <Grid.Col span={{ base: 12, md: 5 }}>
              <Paper p="lg" h="100%">
                <Title order={4} mb="md">
                  Rekordy strumienia wg modułu
                </Title>
                <Table verticalSpacing={8}>
                  <Table.Tbody>
                    {MODULES.map((m) => (
                      <Table.Tr key={m}>
                        <Table.Td>
                          <Text size="sm">{MODULE_LABEL[m]}</Text>
                        </Table.Td>
                        <Table.Td ta="right" fw={600} className="iw-kpi-value">
                          {o ? fmtInt(o.byModule[String(m) as '1' | '2' | '3']) : '—'}
                        </Table.Td>
                      </Table.Tr>
                    ))}
                    <Table.Tr>
                      <Table.Td>
                        <Text size="sm">Wszystkie rekordy</Text>
                      </Table.Td>
                      <Table.Td ta="right" fw={600} className="iw-kpi-value">
                        {o ? fmtInt(o.total) : '—'}
                      </Table.Td>
                    </Table.Tr>
                  </Table.Tbody>
                </Table>
              </Paper>
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 7 }}>
              <Paper p="lg" h="100%">
                <Group justify="space-between" mb="md">
                  <Title order={4}>Rozkład</Title>
                  <SegmentedControl
                    size="xs"
                    value={dist}
                    onChange={(v) => setDist(v as 'platform' | 'contentType')}
                    data={[
                      { value: 'platform', label: 'Platformy' },
                      { value: 'contentType', label: 'Treści' },
                    ]}
                  />
                </Group>
                <Suspense fallback={<Loading />}>
                  {!o ? (
                    <Loading />
                  ) : dist === 'platform' ? (
                    <DistributionBars data={PLATFORMS.map((p) => ({ label: PLATFORM_LABEL[p], value: o.byPlatform[p] }))} />
                  ) : (
                    <DistributionBars data={CONTENT_TYPES.map((c) => ({ label: CONTENT_TYPE_LABEL[c], value: o.byContentType[c] }))} />
                  )}
                </Suspense>
              </Paper>
            </Grid.Col>
          </Grid>
        </>
      )}
    </Stack>
  );
}
