import { Anchor, Badge, Button, Grid, Group, Modal, Paper, SimpleGrid, Stack, Text, Textarea, Title } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconArrowLeft } from '@tabler/icons-react';
import { lazy, Suspense, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useBulkStatus, useCampaign, useThresholds } from '../api/hooks';
import type { GraphNode, Indicator, IndicatorType } from '../api/types';
import { CampaignStatusBadge } from '../components/Badges';
import { FindingList } from '../components/FindingsTable';
import { KpiCard } from '../components/KpiCard';
import { ErrorState, Loading } from '../components/PageState';
import { PlatformIcon } from '../components/PlatformIcon';
import { scamThreshold } from '../lib/findings';
import { fmtDateTime, fmtInt, fmtPct } from '../lib/format';
import { INDICATOR_LABEL } from '../lib/labels';
import { useRangeSearch } from '../lib/url';
import { IndicatorDrawer } from './IndicatorDrawer';

const CytoscapeGraph = lazy(() => import('../components/CytoscapeGraph').then((m) => ({ default: m.CytoscapeGraph })));
const CampaignTimeline = lazy(() => import('../components/Charts').then((m) => ({ default: m.CampaignTimeline })));

export function CampaignDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const search = useRangeSearch();
  const q = useCampaign(id);
  const thresholds = useThresholds();
  const bulk = useBulkStatus();
  const [indicator, setIndicator] = useState<Indicator | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [comment, setComment] = useState('Kampania oznaczona jako scam.');

  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  if (!q.data) return <Loading />;
  const { campaign: c, graph, members } = q.data;
  const unconfirmed = members.filter((m) => m.status !== 'CONFIRMED');

  const onNode = (n: GraphNode) => {
    if (n.kind === 'finding') navigate(`/findings/${n.id}${search}`);
    else if (!n.id.startsWith('agg:')) {
      const sep = n.id.indexOf(':');
      setIndicator({ type: n.id.slice(0, sep) as IndicatorType, value: n.id.slice(sep + 1) });
    }
  };

  const markScam = () =>
    bulk.mutate(
      { ids: unconfirmed.map((m) => m.id), status: 'CONFIRMED', comment: comment.trim() || undefined },
      {
        onSuccess: (res) => {
          setConfirmOpen(false);
          notifications.show({ color: 'green', title: 'Kampania oznaczona', message: `Potwierdzono ${res.items.length} rekordów.` });
        },
        onError: (e) => notifications.show({ color: 'red', title: 'Nie zapisano', message: e.message }),
      },
    );

  return (
    <Stack gap="md">
      <Anchor component={Link} to={`/campaigns${search}`} size="sm">
        <Group gap={4}>
          <IconArrowLeft size={14} /> Kampanie
        </Group>
      </Anchor>

      <Group justify="space-between" align="flex-start">
        <Stack gap={4}>
          <Title order={2}>{c.name}</Title>
          <Group gap="xs">
            <Text size="sm" c="dimmed" ff="monospace">
              {c.id}
            </Text>
            <CampaignStatusBadge status={c.status} />
            <Group gap={4}>
              {c.platforms.map((p) => (
                <PlatformIcon key={p} platform={p} size={16} />
              ))}
            </Group>
          </Group>
        </Stack>
        <Button color="red" onClick={() => setConfirmOpen(true)} disabled={unconfirmed.length === 0}>
          Oznacz kampanię jako scam
        </Button>
      </Group>

      <SimpleGrid cols={{ base: 1, sm: 2, md: 4 }} spacing="sm">
        <KpiCard label="Elementów" value={fmtInt(c.size)} />
        <KpiCard label="Z cechami oszustwa" value={fmtPct(c.scamShare)} />
        <KpiCard label="Pierwsze wystąpienie" value={fmtDateTime(c.firstSeen)} valueSize={18} />
        <KpiCard label="Ostatnie wystąpienie" value={fmtDateTime(c.lastSeen)} valueSize={18} />
      </SimpleGrid>

      <Grid gutter="md">
        <Grid.Col span={{ base: 12, lg: 8 }}>
          <Paper withBorder p="md">
            <Title order={5} mb="sm">
              Graf kampanii
            </Title>
            <Suspense fallback={<Loading />}>
              <CytoscapeGraph graph={graph} onNodeClick={onNode} height={520} />
            </Suspense>
          </Paper>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 4 }}>
          <Stack gap="md">
            <Paper withBorder p="md">
              <Title order={5} mb="sm">
                Wspólne wskaźniki
              </Title>
              <Stack gap={6}>
                {c.topIndicators.map((i) => (
                  <Group key={`${i.type}:${i.value}`} gap="xs" wrap="nowrap">
                    <Badge variant="light" color="gray" tt="none" w={110} style={{ flexShrink: 0 }}>
                      {INDICATOR_LABEL[i.type]}
                    </Badge>
                    <Anchor component="button" type="button" size="sm" onClick={() => setIndicator(i)} style={{ wordBreak: 'break-all', textAlign: 'left' }}>
                      {i.value}
                    </Anchor>
                  </Group>
                ))}
              </Stack>
            </Paper>
            <Paper withBorder p="md">
              <Title order={5} mb="sm">
                Nowe elementy dziennie
              </Title>
              <Suspense fallback={<Loading />}>
                <CampaignTimeline dates={members.map((m) => m.fetchedAt)} />
              </Suspense>
            </Paper>
          </Stack>
        </Grid.Col>
      </Grid>

      <Paper withBorder p="md">
        <Title order={5} mb="sm">
          Elementy kampanii
        </Title>
        <FindingList items={members} scamThreshold={scamThreshold(thresholds.data?.values)} onOpen={(fid) => navigate(`/findings/${fid}${search}`)} />
      </Paper>

      <Modal opened={confirmOpen} onClose={() => setConfirmOpen(false)} title="Oznaczyć kampanię jako scam?">
        <Stack gap="sm">
          <Text size="sm">
            {fmtInt(unconfirmed.length)} rekordów dostanie status „Potwierdzony”. Można go później zmienić dla każdego rekordu osobno.
          </Text>
          <Textarea label="Komentarz" autosize minRows={2} value={comment} onChange={(e) => setComment(e.currentTarget.value)} />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setConfirmOpen(false)}>
              Anuluj
            </Button>
            <Button color="red" loading={bulk.isPending} onClick={markScam}>
              Oznacz
            </Button>
          </Group>
        </Stack>
      </Modal>

      <IndicatorDrawer indicator={indicator} onClose={() => setIndicator(null)} />
    </Stack>
  );
}
