import { Anchor, Grid, Group, Paper, SegmentedControl, Stack, Table, Text, Title } from '@mantine/core';
import { lazy, Suspense, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useOverview, useTimeseries } from '../api/hooks';
import type { TimeseriesGroupBy } from '../api/types';
import { ErrorState, Loading } from '../components/PageState';
import { fmtInt } from '../lib/format';
import { CONTENT_TYPES, CONTENT_TYPE_LABEL, MODULES, MODULE_LABEL, PLATFORMS, PLATFORM_LABEL } from '../lib/labels';
import { findingsLink, useDateRange, useRangeSearch } from '../lib/url';

const TrendChart = lazy(() => import('../components/Charts').then((m) => ({ default: m.TrendChart })));
const DistributionBars = lazy(() => import('../components/Charts').then((m) => ({ default: m.DistributionBars })));

export function Statistics() {
  const { from, to } = useDateRange();
  const range = useMemo(() => ({ from, to }), [from, to]);
  const search = useRangeSearch();
  const [groupBy, setGroupBy] = useState<TimeseriesGroupBy>('module');
  const [dist, setDist] = useState<'platform' | 'contentType'>('platform');
  const overview = useOverview(range);
  const series = useTimeseries(range, groupBy);

  if (overview.isError) return <ErrorState error={overview.error} onRetry={() => void overview.refetch()} />;
  const o = overview.data;

  return (
    <Stack gap="lg">
      <Title order={2}>Statystyki</Title>

      <Paper p="lg">
        <Group justify="space-between" mb="md">
          <Title order={4}>Incydenty dziennie</Title>
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
        <Suspense fallback={<Loading />}>{series.data ? <TrendChart data={series.data} height={300} /> : <Loading />}</Suspense>
      </Paper>

      <Grid gutter="lg">
        <Grid.Col span={{ base: 12, md: 6, lg: 4 }}>
          <Paper p="lg" h="100%">
            <Title order={4} mb="md">
              Moduły
            </Title>
            <Table verticalSpacing={8}>
              <Table.Tbody>
                {MODULES.map((m) => (
                  <Table.Tr key={m}>
                    <Table.Td>
                      <Anchor component={Link} to={findingsLink(search, { module: String(m) })} size="sm">
                        {MODULE_LABEL[m]}
                      </Anchor>
                    </Table.Td>
                    <Table.Td ta="right" fw={600} className="iw-kpi-value">
                      {o ? fmtInt(o.byModule[String(m) as '1' | '2' | '3']) : '—'}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Paper>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6, lg: 4 }}>
          <Paper p="lg" h="100%">
            <Title order={4} mb="md">
              Najczęściej podszywane marki
            </Title>
            {o && o.topImpersonatedBrands.length ? (
              <Table verticalSpacing={8}>
                <Table.Tbody>
                  {o.topImpersonatedBrands.map((b) => (
                    <Table.Tr key={b.brand}>
                      <Table.Td>
                        <Anchor component={Link} to={findingsLink(search, { q: b.brand, scam: '1' })} size="sm">
                          {b.brand}
                        </Anchor>
                      </Table.Td>
                      <Table.Td ta="right" fw={600} className="iw-kpi-value">
                        {fmtInt(b.count)}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            ) : (
              <Text size="sm" c="dimmed">
                Brak w tym okresie.
              </Text>
            )}
          </Paper>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 4 }}>
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
    </Stack>
  );
}
