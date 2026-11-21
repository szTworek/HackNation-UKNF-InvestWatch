import { Group, MultiSelect, NumberInput, Paper, Stack, Table, Text, Title } from '@mantine/core';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCampaigns } from '../api/hooks';
import type { CampaignStatus } from '../api/types';
import { CampaignStatusBadge } from '../components/Badges';
import { Sparkline } from '../components/Sparkline';
import { ErrorState, Loading } from '../components/PageState';
import { PlatformIcon } from '../components/PlatformIcon';
import { fmtDate, fmtInt, fmtPct } from '../lib/format';
import { CAMPAIGN_STATUS_LABEL } from '../lib/labels';
import { useDateRange, useRangeSearch } from '../lib/url';

const STATUSES: CampaignStatus[] = ['ACTIVE', 'MONITORED', 'CLOSED'];

export function Campaigns() {
  const navigate = useNavigate();
  const search = useRangeSearch();
  const { from, to } = useDateRange();
  const [status, setStatus] = useState<CampaignStatus[]>([]);
  const [minSize, setMinSize] = useState<number>(0);
  const query = useMemo(() => ({ from, to, status, minSize, sort: 'size:desc' }), [from, to, status, minSize]);
  const campaigns = useCampaigns(query);

  return (
    <Stack gap="md">
      <Title order={2}>Kampanie</Title>
      <Paper withBorder p="sm">
        <Group gap="sm" align="flex-end">
          <MultiSelect
            label="Status"
            size="xs"
            w={240}
            data={STATUSES.map((s) => ({ value: s, label: CAMPAIGN_STATUS_LABEL[s] }))}
            value={status}
            onChange={(v) => setStatus(v as CampaignStatus[])}
            clearable
          />
          <NumberInput
            label="Minimalny rozmiar"
            size="xs"
            w={140}
            min={0}
            value={minSize}
            onChange={(v) => setMinSize(typeof v === 'number' ? v : 0)}
          />
        </Group>
      </Paper>

      <Paper withBorder>
        {campaigns.isError ? (
          <ErrorState error={campaigns.error} onRetry={() => void campaigns.refetch()} />
        ) : !campaigns.data ? (
          <Loading />
        ) : campaigns.data.items.length === 0 ? (
          <Text size="sm" c="dimmed" p="md">
            Brak kampanii w tym zakresie dat.
          </Text>
        ) : (
          <Table.ScrollContainer minWidth={980}>
            <Table highlightOnHover verticalSpacing={8} fz="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Nazwa</Table.Th>
                  <Table.Th w={80} ta="right">
                    Elementów
                  </Table.Th>
                  <Table.Th w={130} ta="right">
                    Z cechami oszustwa
                  </Table.Th>
                  <Table.Th w={130}>Platformy</Table.Th>
                  <Table.Th w={110}>Pierwsze</Table.Th>
                  <Table.Th w={110}>Ostatnie</Table.Th>
                  <Table.Th w={120}>Ostatnie dni</Table.Th>
                  <Table.Th w={110}>Status</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {campaigns.data.items.map((c) => (
                  <Table.Tr key={c.id} onClick={() => navigate(`/campaigns/${c.id}${search}`)} style={{ cursor: 'pointer' }}>
                    <Table.Td>
                      <Text size="sm" fw={500}>
                        {c.name}
                      </Text>
                    </Table.Td>
                    <Table.Td ta="right" ff="monospace">
                      {fmtInt(c.size)}
                    </Table.Td>
                    <Table.Td ta="right" ff="monospace" c={c.scamShare >= 0.5 ? 'red.7' : undefined}>
                      {fmtPct(c.scamShare)}
                    </Table.Td>
                    <Table.Td>
                      <Group gap={4}>
                        {c.platforms.map((p) => (
                          <PlatformIcon key={p} platform={p} size={16} />
                        ))}
                      </Group>
                    </Table.Td>
                    <Table.Td>{fmtDate(c.firstSeen)}</Table.Td>
                    <Table.Td>{fmtDate(c.lastSeen)}</Table.Td>
                    <Table.Td>
                      <Sparkline values={c.trend} color={c.scamShare >= 0.5 ? '#e03131' : '#868e96'} />
                    </Table.Td>
                    <Table.Td>
                      <CampaignStatusBadge status={c.status} />
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
      </Paper>
    </Stack>
  );
}
