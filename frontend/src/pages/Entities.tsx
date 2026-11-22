import { Anchor, Badge, Group, Pagination, Paper, Select, Stack, Table, Text, TextInput, Title } from '@mantine/core';
import { IconSearch } from '@tabler/icons-react';
import { useMemo } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import type { KnfCategory, KnfEntity } from '../api/entityTypes';
import { useEntities } from '../api/hooks';
import { RiskMeter } from '../components/EntityParts';
import { ErrorState, Loading } from '../components/PageState';
import { fmtInt } from '../lib/format';
import { KNF_CATEGORY_LABEL } from '../lib/labels';

type Sort = 'data' | 'name' | 'risk' | 'findings' | 'country';

const SORTS: { value: Sort; label: string }[] = [
  { value: 'data', label: 'Z danymi najpierw' },
  { value: 'name', label: 'Nazwa A–Z' },
  { value: 'risk', label: 'Ryzyko malejąco' },
  { value: 'findings', label: 'Wyniki malejąco' },
  { value: 'country', label: 'Kraj' },
];

const PAGE = 50;
const collator = new Intl.Collator('pl');

const matches = (e: KnfEntity, q: string) =>
  !q ||
  e.registryEntries.some((r) => r.name.toLowerCase().includes(q) || r.aliases.some((a) => a.toLowerCase().includes(q))) ||
  e.name.toLowerCase().includes(q) ||
  e.domains.some((d) => d.includes(q));

function compare(sort: Sort) {
  const byName = (a: KnfEntity, b: KnfEntity) => collator.compare(a.name, b.name);
  const data = (a: KnfEntity, b: KnfEntity) => Number(b.hasData) - Number(a.hasData);
  switch (sort) {
    case 'name':
      return byName;
    case 'country':
      return (a: KnfEntity, b: KnfEntity) => collator.compare(a.country, b.country) || byName(a, b);
    case 'risk':
      return (a: KnfEntity, b: KnfEntity) => (b.kpis?.riskScore ?? -1) - (a.kpis?.riskScore ?? -1) || byName(a, b);
    case 'findings':
      return (a: KnfEntity, b: KnfEntity) => (b.kpis?.findingsOpen ?? -1) - (a.kpis?.findingsOpen ?? -1) || byName(a, b);
    default:
      return (a: KnfEntity, b: KnfEntity) => data(a, b) || (b.kpis?.findingsOpen ?? 0) - (a.kpis?.findingsOpen ?? 0) || byName(a, b);
  }
}

export function Entities() {
  const q = useEntities();
  const navigate = useNavigate();
  const [sp, setSp] = useSearchParams();
  const phrase = sp.get('q') ?? '';
  const category = sp.get('category');
  const country = sp.get('country');
  const sort = (sp.get('sort') as Sort | null) ?? 'data';
  const page = Math.max(1, Number(sp.get('page')) || 1);
  const setPage = (p: number) => {
    const n = new URLSearchParams(sp);
    if (p > 1) n.set('page', String(p));
    else n.delete('page');
    setSp(n, { replace: true });
  };

  const set = (key: string, value: string | null) => {
    const n = new URLSearchParams(sp);
    if (value) n.set(key, value);
    else n.delete(key);
    n.delete('page');
    setSp(n, { replace: true });
  };

  const all = useMemo(() => q.data ?? [], [q.data]);
  const countries = useMemo(() => [...new Set(all.flatMap((e) => e.registryEntries.map((r) => r.country)))].sort(collator.compare), [all]);
  const rows = useMemo(() => {
    const ql = phrase.trim().toLowerCase();
    return all
      .filter(
        (e) =>
          matches(e, ql) &&
          (!category || e.registryEntries.some((r) => r.category === category)) &&
          (!country || e.registryEntries.some((r) => r.country === country)),
      )
      .sort(compare(sort));
  }, [all, phrase, category, country, sort]);

  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const withData = all.filter((e) => e.hasData).length;
  const entries = all.reduce((n, e) => n + e.registryEntries.length, 0);
  const pageRows = rows.slice((page - 1) * PAGE, page * PAGE);

  return (
    <Stack gap="lg">
      <div>
        <Title order={2}>Podmioty</Title>
        <Text c="dimmed" mt={4}>
          Rejestr firm inwestycyjnych KNF: {fmtInt(entries)} wpisów. Wpisy jednej marki są zgrupowane w podmiot. Monitorowane
          (z zebranymi reklamami, postami i stronami): {withData}.
        </Text>
      </div>

      <Paper p="md">
        <Group gap="sm" align="flex-end">
          <TextInput
            label="Szukaj"
            placeholder="Nazwa, dawna nazwa albo domena"
            leftSection={<IconSearch size={16} />}
            value={phrase}
            onChange={(e) => set('q', e.currentTarget.value)}
            style={{ flex: '1 1 260px' }}
          />
          <Select
            label="Kategoria"
            placeholder="Wszystkie"
            clearable
            value={category}
            onChange={(v) => set('category', v)}
            data={(Object.keys(KNF_CATEGORY_LABEL) as KnfCategory[]).map((c) => ({ value: c, label: KNF_CATEGORY_LABEL[c] }))}
            w={280}
          />
          <Select label="Kraj" placeholder="Wszystkie" clearable searchable value={country} onChange={(v) => set('country', v)} data={countries} w={180} />
          <Select label="Sortowanie" value={sort} onChange={(v) => set('sort', v === 'data' ? null : v)} data={SORTS} allowDeselect={false} w={200} />
        </Group>
      </Paper>

      <Paper>
        {q.isLoading ? (
          <Loading />
        ) : !rows.length ? (
          <Text c="dimmed" size="sm" p="md">
            Brak podmiotów dla tych filtrów.
          </Text>
        ) : (
          <Table.ScrollContainer minWidth={900}>
            <Table highlightOnHover verticalSpacing={8}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Podmiot</Table.Th>
                  <Table.Th>Kategoria</Table.Th>
                  <Table.Th>Kraj</Table.Th>
                  <Table.Th>Monitoring</Table.Th>
                  <Table.Th ta="right">Rekordy</Table.Th>
                  <Table.Th ta="right">Wyniki</Table.Th>
                  <Table.Th ta="right">Nowe alerty</Table.Th>
                  <Table.Th w={140}>Ryzyko</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {pageRows.map((e) => (
                  <Table.Tr key={e.id} className="iw-row-link" onClick={() => navigate(`/entities/${e.id}`)} bg={e.hasData ? 'var(--iw-soft)' : undefined}>
                    <Table.Td>
                      <Anchor component={Link} to={`/entities/${e.id}`} fw={e.hasData ? 700 : 500} size="sm" onClick={(ev) => ev.stopPropagation()}>
                        {e.name}
                      </Anchor>
                      {e.hasData && (
                        <Text size="xs" c="dimmed">
                          {e.registryEntries.map((r) => r.name).join(' · ')}
                        </Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{KNF_CATEGORY_LABEL[e.category]}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{[...new Set(e.registryEntries.map((r) => r.country))].join(', ')}</Text>
                    </Table.Td>
                    <Table.Td>
                      {e.hasData ? (
                        <Badge variant="filled" size="sm">
                          monitorowany
                        </Badge>
                      ) : (
                        <Text size="xs" c="dimmed">
                          tylko rejestr
                        </Text>
                      )}
                    </Table.Td>
                    <Table.Td ta="right">{e.kpis ? fmtInt(e.kpis.items) : '—'}</Table.Td>
                    <Table.Td ta="right">{e.kpis ? fmtInt(e.kpis.findingsOpen) : '—'}</Table.Td>
                    <Table.Td ta="right">{e.kpis ? fmtInt(e.kpis.alertsNew) : '—'}</Table.Td>
                    <Table.Td>{e.kpis ? <RiskMeter value={e.kpis.riskScore} /> : <Text size="xs" c="dimmed">—</Text>}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
        <Group justify="space-between" p="sm">
          <Text size="sm" c="dimmed">
            {fmtInt(rows.length)} podmiotów
          </Text>
          {rows.length > PAGE && <Pagination value={page} onChange={setPage} total={Math.ceil(rows.length / PAGE)} size="sm" />}
        </Group>
      </Paper>
    </Stack>
  );
}
