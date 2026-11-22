import { Anchor, Group, Pagination, Paper, Select, Stack, Table, Text, Title } from '@mantine/core';
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useHistory } from '../api/hooks';
import { RiskBadge, StatusBadge } from '../components/Badges';
import { ErrorState, Loading } from '../components/PageState';
import { PlatformIcon } from '../components/PlatformIcon';
import { fmtDateTime, fmtInt } from '../lib/format';
import { useDateRange, useRangeSearch } from '../lib/url';

const PAGE_SIZE = 50;

/** Dziennik decyzji analityków: kto, kiedy i na jaki status zmienił rekord. */
export function History() {
  const { from, to } = useDateRange();
  const search = useRangeSearch();
  const [user, setUser] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const q = useMemo(() => ({ from, to, user: user ?? undefined, page, pageSize: PAGE_SIZE }), [from, to, user, page]);
  const history = useHistory(q);
  const users = useMemo(() => {
    const set = new Set(history.data?.users ?? []);
    if (user) set.add(user);
    return [...set].sort();
  }, [history.data, user]);

  const total = history.data?.total ?? 0;

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end">
        <Title order={2}>Historia decyzji</Title>
        <Select
          label="Analityk"
          placeholder="Wszyscy"
          size="sm"
          w={220}
          data={users}
          value={user}
          onChange={(v) => {
            setUser(v);
            setPage(1);
          }}
          clearable
        />
      </Group>

      <Paper p={0}>
        {history.isError ? (
          <ErrorState error={history.error} onRetry={() => void history.refetch()} />
        ) : !history.data ? (
          <Loading />
        ) : history.data.items.length === 0 ? (
          <Text size="sm" c="dimmed" p="lg">
            Brak decyzji w tym okresie.
          </Text>
        ) : (
          <Table.ScrollContainer minWidth={900}>
            <Table verticalSpacing={10} horizontalSpacing="md" highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th w={140}>Kiedy</Table.Th>
                  <Table.Th w={130}>Analityk</Table.Th>
                  <Table.Th w={130}>Nowy status</Table.Th>
                  <Table.Th>Rekord</Table.Th>
                  <Table.Th>Komentarz</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {history.data.items.map((r, i) => (
                  <Table.Tr key={`${r.findingId}-${r.at}-${i}`}>
                    <Table.Td>
                      <Text size="sm">{fmtDateTime(r.at)}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{r.user}</Text>
                    </Table.Td>
                    <Table.Td>
                      <StatusBadge status={r.status} />
                    </Table.Td>
                    <Table.Td>
                      <Group gap={8} wrap="nowrap">
                        <PlatformIcon platform={r.platform} size={16} />
                        <div style={{ minWidth: 0 }}>
                          <Group gap={6} wrap="nowrap">
                            <Anchor component={Link} to={`/findings/${r.findingId}${search}`} size="sm" fw={500}>
                              {r.author}
                            </Anchor>
                            <RiskBadge level={r.riskLevel} size="xs" />
                          </Group>
                          <Text size="xs" c="dimmed" lineClamp={1}>
                            {r.snippet}
                          </Text>
                        </div>
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" c={r.comment ? undefined : 'dimmed'}>
                        {r.comment ?? '—'}
                      </Text>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
        {total > PAGE_SIZE && (
          <Group justify="space-between" p="md">
            <Text size="sm" c="dimmed">
              {fmtInt(total)} decyzji
            </Text>
            <Pagination size="sm" total={Math.ceil(total / PAGE_SIZE)} value={page} onChange={setPage} />
          </Group>
        )}
      </Paper>
    </Stack>
  );
}
