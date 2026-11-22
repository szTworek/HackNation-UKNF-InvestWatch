import { Alert, Anchor, Badge, Button, Drawer, Grid, Group, Paper, Select, SimpleGrid, Stack, Table, Tabs, Text, Title } from '@mantine/core';
import { IconExternalLink, IconInfoCircle, IconPrinter } from '@tabler/icons-react';
import { useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import type { EntityModule, KnfEntityDetail, SourcePlatform } from '../api/entityTypes';
import { useEntities, useEntity, useEntityAlerts, useEntityFindings, useEntityItems, useEntityPages } from '../api/hooks';
import { DistributionBars } from '../components/Charts';
import { EntityModuleBadge, AlertRows, ChangeTimeline, DiffView, ItemView, MockBadge, RiskMeter, RiskWarningStatus, SeverityBadge, pageChanges, shortUrl } from '../components/EntityParts';
import { FindingsByDayChart, LabeledBars, daysFromFindings } from '../components/EntityCharts';
import { KpiCard } from '../components/KpiCard';
import { ErrorState, Loading } from '../components/PageState';
import { fmtDate, fmtDateTime, fmtInt, fmtProb } from '../lib/format';
import {
  CHANNEL_LABEL,
  ENTITY_MODULES,
  ENTITY_MODULE_COLOR,
  ENTITY_MODULE_DESC,
  ENTITY_MODULE_LABEL,
  KNF_CATEGORY_LABEL,
  SEVERITY_LABEL,
  SOURCE_PLATFORM_LABEL,
  ruleModule,
  ruleText,
} from '../lib/labels';

const TABS = [
  { id: 'overview', label: 'Przegląd' },
  { id: 'websites', label: 'Strony WWW' },
  { id: 'social', label: 'Social media i reklamy' },
  { id: 'findings', label: 'Wyniki' },
  { id: 'alerts', label: 'Alerty' },
] as const;

export function RegistryTable({ e }: { e: KnfEntityDetail }) {
  return (
    <Table.ScrollContainer minWidth={640}>
      <Table verticalSpacing={6}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Wpis w rejestrze KNF</Table.Th>
            <Table.Th>Kategoria</Table.Th>
            <Table.Th>Kraj</Table.Th>
            <Table.Th>Nadzór</Table.Th>
            <Table.Th>Data wpisu</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {e.registryEntries.map((r) => (
            <Table.Tr key={r.name}>
              <Table.Td>
                <Text size="sm" fw={600}>
                  {r.sourceUrl ? (
                    <Anchor href={r.sourceUrl} target="_blank" rel="noreferrer" size="sm" fw={600}>
                      {r.name}
                    </Anchor>
                  ) : (
                    r.name
                  )}
                </Text>
                {r.aliases.length > 0 && (
                  <Text size="xs" c="dimmed">
                    dawniej: {r.aliases.join(', ')}
                  </Text>
                )}
                {r.address && (
                  <Text size="xs" c="dimmed" lineClamp={1}>
                    {r.address}
                  </Text>
                )}
              </Table.Td>
              <Table.Td>
                <Text size="sm">{KNF_CATEGORY_LABEL[r.category]}</Text>
              </Table.Td>
              <Table.Td>
                <Text size="sm">{r.country}</Text>
              </Table.Td>
              <Table.Td>
                <Text size="sm">{r.supervisor ?? '—'}</Text>
              </Table.Td>
              <Table.Td>
                <Text size="sm">{r.registeredAt ?? '—'}</Text>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

export function EntityDetail() {
  const { id = '' } = useParams();
  const [sp, setSp] = useSearchParams();
  const tab = sp.get('tab') ?? 'overview';
  const item = sp.get('item');
  const change = sp.get('change');
  const finding = sp.get('finding');
  const q = useEntity(id);
  const e = q.data;
  const monitored = (useEntities().data ?? []).filter((x) => x.hasData);

  const set = (patch: Record<string, string | null>) => {
    const n = new URLSearchParams(sp);
    Object.entries(patch).forEach(([k, v]) => (v === null ? n.delete(k) : n.set(k, v)));
    setSp(n);
  };

  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  if (!e) return <Loading />;

  return (
    <Stack gap="lg">
      <Paper p="lg">
        <Group align="flex-start" justify="space-between" gap="lg">
          <div style={{ minWidth: 0, flex: 1 }}>
            <Group gap="sm">
              <Title order={2}>{e.name}</Title>
              {e.hasData ? <Badge variant="filled">monitorowany</Badge> : <Badge variant="default">tylko rejestr</Badge>}
            </Group>
            <Group gap="md" mt={6}>
              <Text size="sm" c="dimmed">
                {KNF_CATEGORY_LABEL[e.category]} · {e.country}
              </Text>
              {e.domains.map((d) => (
                <Anchor key={d} href={`https://${d}`} target="_blank" rel="noreferrer" size="sm">
                  <Group gap={3}>
                    {d}
                    <IconExternalLink size={13} />
                  </Group>
                </Anchor>
              ))}
            </Group>
            {Object.keys(e.socialHandles).length > 0 && (
              <Group gap="md" mt={4}>
                {Object.entries(e.socialHandles).map(([p, h]) => (
                  <Text key={p} size="xs" c="dimmed">
                    {SOURCE_PLATFORM_LABEL[p as SourcePlatform] ?? p}: <b>{h}</b>
                  </Text>
                ))}
              </Group>
            )}
          </div>
          {e.hasData && e.kpis && (
            <Group gap="sm" align="stretch">
              <Paper p="sm" w={150}>
                <Text size="xs" c="dimmed">
                  Ryzyko (0–100)
                </Text>
                <RiskMeter value={e.kpis.riskScore} />
              </Paper>
              <Button component={Link} to={`/reports/${e.id}`} variant="default" leftSection={<IconPrinter size={16} />}>
                Raport
              </Button>
            </Group>
          )}
        </Group>
        {e.hasData && e.kpis && (
          <SimpleGrid cols={{ base: 2, sm: 5 }} mt="md">
            <KpiCard label="Rekordy" value={fmtInt(e.kpis.items)} hint="reklamy, posty, filmy" valueSize={24} />
            <KpiCard label="Wyniki" value={fmtInt(e.kpis.findingsOpen)} hint="trzy moduły" valueSize={24} />
            <KpiCard label="Nowe alerty" value={fmtInt(e.kpis.alertsNew)} valueSize={24} accent={e.kpis.alertsNew ? 'var(--iw-red)' : undefined} />
            <KpiCard label="Strony WWW" value={fmtInt(e.monitoredPages)} hint="monitorowane" valueSize={24} />
            <KpiCard label="Zmiany stron (7 dni)" value={fmtInt(e.kpis.pagesChanged7d)} valueSize={24} />
          </SimpleGrid>
        )}
      </Paper>

      {!e.hasData ? (
        <>
          <Paper p="lg">
            <Title order={4} mb="sm">
              Dane z rejestru KNF
            </Title>
            <RegistryTable e={e} />
          </Paper>
          <Alert icon={<IconInfoCircle />} title="Brak zebranych danych" color="gray">
            Podmiot jest w rejestrze, ale nie jest jeszcze monitorowany: nie zebrano jego reklam, postów ani stron WWW. Monitoring obejmuje
            obecnie: {monitored.map((x) => x.name).join(', ')}.
          </Alert>
        </>
      ) : (
        <Tabs value={tab} onChange={(v) => set({ tab: v, item: null, change: null, finding: null })} keepMounted={false}>
          <Tabs.List mb="md">
            {TABS.map((t) => (
              <Tabs.Tab key={t.id} value={t.id}>
                {t.label}
              </Tabs.Tab>
            ))}
          </Tabs.List>
          <Tabs.Panel value="overview">
            <OverviewTab e={e} />
          </Tabs.Panel>
          <Tabs.Panel value="websites">
            <WebsitesTab id={e.id} onChange={(c) => set({ change: c })} />
          </Tabs.Panel>
          <Tabs.Panel value="social">
            <SocialTab id={e.id} onItem={(i) => set({ item: i })} />
          </Tabs.Panel>
          <Tabs.Panel value="findings">
            <FindingsTab id={e.id} focus={finding} onItem={(i, f) => set({ item: i, finding: f })} />
          </Tabs.Panel>
          <Tabs.Panel value="alerts">
            <AlertsTab id={e.id} onOpen={(patch) => set(patch)} />
          </Tabs.Panel>
        </Tabs>
      )}

      <Drawer opened={!!item} onClose={() => set({ item: null })} position="right" size="xl" title={<Text fw={700}>Rekord</Text>}>
        {item && <ItemView id={item} focusFinding={finding} />}
      </Drawer>
      <Drawer opened={!!change} onClose={() => set({ change: null })} position="right" size="80rem" title={<Text fw={700}>Zmiana strony: porównanie zrzutów</Text>}>
        {change && <DiffView id={change} />}
      </Drawer>
    </Stack>
  );
}

function OverviewTab({ e }: { e: KnfEntityDetail }) {
  const { findings, isLoading } = useEntityFindings(e.id);
  const trend = useMemo(() => daysFromFindings(findings), [findings]);
  const rules = useMemo(() => {
    const m = new Map<string, { label: string; n: number }>();
    findings.forEach((f) =>
      f.ruleHits.forEach((h) => {
        const x = m.get(h.ruleId) ?? { label: h.label, n: 0 };
        x.n++;
        m.set(h.ruleId, x);
      }),
    );
    return [...m.entries()].sort((a, b) => b[1].n - a[1].n).slice(0, 6);
  }, [findings]);
  return (
    <Stack gap="lg">
      <Group gap={8} mb={-8}>
        <Text size="sm" fw={600}>
          Moduły
        </Text>
        <MockBadge hint="Wyniki z klasyfikatora mock-v0 (reguły słownikowe zamiast LLM)" />
      </Group>
      <SimpleGrid cols={{ base: 1, md: 3 }}>
        {ENTITY_MODULES.map((m) => (
          <Paper key={m} p="md" style={{ borderTop: `3px solid ${ENTITY_MODULE_COLOR[m]}` }}>
            <Group gap={8}>
              <EntityModuleBadge m={m} />
              <Text fw={600} size="sm">
                {ENTITY_MODULE_LABEL[m]}
              </Text>
            </Group>
            <Text size="xs" c="dimmed" mt={4}>
              {ENTITY_MODULE_DESC[m]}
            </Text>
            <Group justify="space-between" mt="sm" align="flex-end">
              <div>
                <Text fz={26} fw={600} className="iw-kpi-value">
                  {fmtInt(e.modules[m].findings)}
                </Text>
                <Text size="xs" c="dimmed">
                  wyników
                </Text>
              </div>
              <div style={{ textAlign: 'right' }}>
                <Text fz={18} fw={600} className="iw-kpi-value">
                  {e.modules[m].findings ? Math.round(e.modules[m].avgScore * 100) : '—'}
                </Text>
                <Text size="xs" c="dimmed">
                  średni wynik
                </Text>
              </div>
            </Group>
          </Paper>
        ))}
      </SimpleGrid>
      <Grid gutter="lg">
        <Grid.Col span={{ base: 12, lg: 8 }}>
          <Paper p="lg" h="100%">
            <Group gap={8} mb="md">
              <Title order={4}>Wyniki dziennie</Title>
              <MockBadge hint="Daty wyników rozłożone syntetycznie na 30 dni" />
            </Group>
            {isLoading ? <Loading /> : <FindingsByDayChart data={trend} height={260} />}
          </Paper>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 4 }}>
          <Paper p="lg" h="100%">
            <Title order={4} mb="md">
              Rekordy wg platformy
            </Title>
            <DistributionBars data={Object.entries(e.platforms).map(([p, v]) => ({ label: SOURCE_PLATFORM_LABEL[p as SourcePlatform] ?? p, value: v ?? 0 }))} />
          </Paper>
        </Grid.Col>
      </Grid>
      <Paper p="lg">
        <Group gap={8} mb="md">
          <Title order={4}>Najczęstsze naruszenia</Title>
          <MockBadge hint="Wyniki z klasyfikatora mock-v0 (reguły słownikowe zamiast LLM)" />
        </Group>
        <LabeledBars rows={rules.map(([k, v]) => ({ key: k, label: ruleText(k, v.label), value: v.n, color: ENTITY_MODULE_COLOR[ruleModule(k)] }))} />
      </Paper>
      <Paper p="lg">
        <Title order={4} mb="sm">
          Wpisy w rejestrze KNF
        </Title>
        <RegistryTable e={e} />
      </Paper>
    </Stack>
  );
}

function WebsitesTab({ id, onChange }: { id: string; onChange: (c: string) => void }) {
  const q = useEntityPages(id);
  const changes = useMemo(() => pageChanges(q.data ?? []), [q.data]);
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  if (!q.data) return <Loading />;
  if (!q.data.length)
    return (
      <Text c="dimmed" size="sm">
        Monitor stron nie ma skonfigurowanych stron tego podmiotu.
      </Text>
    );
  return (
    <Grid gutter="lg">
      <Grid.Col span={{ base: 12, lg: 7 }}>
        <Paper>
          <div className="iw-panel-head">
            <span className="iw-panel-title">Monitorowane strony</span>
            <Text size="xs" c="dimmed">
              ostatni zrzut i ostrzeżenie o ryzyku
            </Text>
          </div>
          <Table verticalSpacing={8}>
            <Table.Tbody>
              {q.data.map((p) => (
                <Table.Tr key={p.pageId}>
                  <Table.Td>
                    <Text size="sm" fw={600}>
                      {p.label}
                    </Text>
                    <Anchor href={p.url} target="_blank" rel="noreferrer" size="xs">
                      {shortUrl(p.url)}
                    </Anchor>
                    {p.lastSnapshot?.riskWarning.text && (
                      <Text size="xs" c="dimmed" fs="italic" lineClamp={1} maw={520}>
                        „{p.lastSnapshot.riskWarning.text}”
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <RiskWarningStatus snap={p.lastSnapshot} />
                    <Text size="xs" c="dimmed" mt={2}>
                      zrzut {fmtDateTime(p.lastSnapshot?.fetchedAt)} · zmian: {p.changes.length}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Paper>
      </Grid.Col>
      <Grid.Col span={{ base: 12, lg: 5 }}>
        <Paper p="lg">
          <Title order={4}>Oś czasu zmian</Title>
          <Text size="xs" c="dimmed" mb="md">
            Kliknij zmianę, żeby porównać zrzuty obok siebie.
          </Text>
          <ChangeTimeline changes={changes} onOpen={onChange} />
        </Paper>
      </Grid.Col>
    </Grid>
  );
}

const snippet = (t: Record<string, string>) => t.title || t.ad_body || t.post || t.description || t.ocr || Object.values(t)[0] || '';

function SocialTab({ id, onItem }: { id: string; onItem: (i: string) => void }) {
  const [channel, setChannel] = useState<string | null>(null);
  const [platform, setPlatform] = useState<string | null>(null);
  const [module, setModule] = useState<string | null>(null);
  const [limit, setLimit] = useState(40);
  const q = useEntityItems(id, { channel: channel ?? undefined, platform: platform ?? undefined, module: module ?? undefined, limit });
  const reset = <T,>(fn: (v: T) => void) => (v: T) => {
    fn(v);
    setLimit(40);
  };
  return (
    <Paper>
      <Group p="md" gap="sm" align="flex-end" style={{ borderBottom: '1px solid var(--iw-border)' }}>
        <Select label="Kanał" placeholder="Wszystkie" clearable value={channel} onChange={reset(setChannel)} data={[{ value: 'ad', label: CHANNEL_LABEL.ad }, { value: 'social', label: CHANNEL_LABEL.social }]} w={170} />
        <Select
          label="Platforma"
          placeholder="Wszystkie"
          clearable
          value={platform}
          onChange={reset(setPlatform)}
          data={(['google_ads', 'meta_ads', 'bing_ads', 'youtube', 'tiktok'] as SourcePlatform[]).map((p) => ({ value: p, label: SOURCE_PLATFORM_LABEL[p] }))}
          w={170}
        />
        <Select label="Moduł" placeholder="Wszystkie" clearable value={module} onChange={reset(setModule)} data={ENTITY_MODULES.map((m) => ({ value: m, label: ENTITY_MODULE_LABEL[m] }))} w={260} />
        <Text size="sm" c="dimmed" ml="auto">
          {q.data ? `${q.data.items.length} z ${fmtInt(q.data.total)}` : ''}
        </Text>
      </Group>
      {q.isError ? (
        <ErrorState error={q.error} onRetry={() => void q.refetch()} />
      ) : !q.data ? (
        <Loading />
      ) : !q.data.items.length ? (
        <Text c="dimmed" size="sm" p="md">
          Brak rekordów dla tych filtrów.
        </Text>
      ) : (
        <>
          <Table highlightOnHover verticalSpacing={8}>
            <Table.Tbody>
              {q.data.items.map((it) => {
                const fs = it.findings.filter((f) => f.entityId === id);
                const worst = fs.reduce<(typeof fs)[number] | null>((w, f) => (!w || f.score > w.score ? f : w), null);
                return (
                  <Table.Tr key={it.id} className="iw-row-link" onClick={() => onItem(it.id)}>
                    <Table.Td w={130}>
                      <Text size="sm" fw={500}>
                        {SOURCE_PLATFORM_LABEL[it.platform]}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {fmtDate(it.publishedAt ?? it.fetchedAt)}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Group gap={6}>
                        <Text size="sm" fw={600}>
                          {it.author}
                        </Text>
                        <Badge size="xs" variant="light" color={it.authorIsEntity ? 'knf' : 'orange'}>
                          {it.authorIsEntity ? 'konto oficjalne' : 'osoba trzecia'}
                        </Badge>
                        {it.mock && <MockBadge />}
                      </Group>
                      <Text size="sm" c="dimmed" lineClamp={2}>
                        {snippet(it.text)}
                      </Text>
                    </Table.Td>
                    <Table.Td w={150}>
                      <Group gap={4} justify="flex-end">
                        {[...new Set(fs.map((f) => f.module))].map((m) => (
                          <EntityModuleBadge key={m} m={m as EntityModule} />
                        ))}
                        {worst ? (
                          <SeverityBadge s={worst.severity} />
                        ) : (
                          <Text size="xs" c="dimmed">
                            bez wyników
                          </Text>
                        )}
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
          {q.data.items.length < q.data.total && (
            <Group justify="center" p="sm">
              <Button variant="subtle" size="xs" onClick={() => setLimit(limit + 40)} loading={q.isFetching}>
                Pokaż więcej (zostało {q.data.total - q.data.items.length})
              </Button>
            </Group>
          )}
        </>
      )}
    </Paper>
  );
}

function FindingsTab({ id, focus, onItem }: { id: string; focus: string | null; onItem: (i: string, f: string) => void }) {
  const q = useEntityFindings(id);
  const [module, setModule] = useState<string | null>(null);
  const [sev, setSev] = useState<string | null>(null);
  const rows = useMemo(
    () => q.findings.filter((f) => (!module || f.module === module) && (!sev || f.severity === sev)).sort((a, b) => b.score - a.score),
    [q.findings, module, sev],
  );
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  return (
    <Paper>
      <Group p="md" gap="sm" align="flex-end" style={{ borderBottom: '1px solid var(--iw-border)' }}>
        <Select label="Moduł" placeholder="Wszystkie" clearable value={module} onChange={setModule} data={ENTITY_MODULES.map((m) => ({ value: m, label: ENTITY_MODULE_LABEL[m] }))} w={260} />
        <Select
          label="Waga"
          placeholder="Wszystkie"
          clearable
          value={sev}
          onChange={setSev}
          data={(['high', 'medium', 'low'] as const).map((s) => ({ value: s, label: SEVERITY_LABEL[s] }))}
          w={160}
        />
        <Group gap={6} ml="auto">
          <MockBadge hint="Klasyfikator mock-v0: reguły słownikowe zamiast LLM" />
          <Text size="sm" c="dimmed">
            {fmtInt(rows.length)} wyników
          </Text>
        </Group>
      </Group>
      {q.isLoading ? (
        <Loading />
      ) : !rows.length ? (
        <Text c="dimmed" size="sm" p="md">
          Brak wyników dla tych filtrów.
        </Text>
      ) : (
        <Table.ScrollContainer minWidth={820}>
          <Table highlightOnHover verticalSpacing={8}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Waga</Table.Th>
                <Table.Th>Moduł</Table.Th>
                <Table.Th>Naruszenia</Table.Th>
                <Table.Th>Źródło</Table.Th>
                <Table.Th ta="right">Wynik</Table.Th>
                <Table.Th ta="right">Data</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {rows.slice(0, 300).map((f) => (
                <Table.Tr key={f.id} className="iw-row-link" onClick={() => onItem(f.itemId, f.id)} bg={focus === f.id ? 'var(--mantine-color-knf-0)' : undefined}>
                  <Table.Td>
                    <SeverityBadge s={f.severity} />
                  </Table.Td>
                  <Table.Td>
                    <EntityModuleBadge m={f.module} />
                  </Table.Td>
                  <Table.Td maw={460}>
                    <Text size="sm" lineClamp={2}>
                      {f.ruleHits.map((h) => ruleText(h.ruleId, h.label)).join('; ')}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{SOURCE_PLATFORM_LABEL[f.item.platform]}</Text>
                    <Text size="xs" c="dimmed" truncate maw={200}>
                      {f.item.author}
                    </Text>
                  </Table.Td>
                  <Table.Td ta="right" fw={600}>
                    {fmtProb(f.score)}
                  </Table.Td>
                  <Table.Td ta="right">
                    <Text size="sm" c="dimmed">
                      {fmtDate(f.createdAt)}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {rows.length > 300 && (
        <Text size="xs" c="dimmed" ta="center" p="sm">
          Pokazano 300 wyników o najwyższym wyniku.
        </Text>
      )}
    </Paper>
  );
}

function AlertsTab({ id, onOpen }: { id: string; onOpen: (patch: Record<string, string | null>) => void }) {
  const q = useEntityAlerts(id);
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const alerts = q.data ?? [];
  return (
    <Stack gap="lg">
      <SimpleGrid cols={3}>
        <KpiCard label="Nowe" value={alerts.filter((a) => a.status === 'new').length} loading={q.isLoading} />
        <KpiCard label="Przyjęte" value={alerts.filter((a) => a.status === 'ack').length} loading={q.isLoading} />
        <KpiCard label="Zamknięte" value={alerts.filter((a) => a.status === 'closed').length} loading={q.isLoading} />
      </SimpleGrid>
      <Paper p="md">
        {q.isLoading ? (
          <Loading />
        ) : (
          <AlertRows
            alerts={alerts}
            onOpen={(a) => {
              if (a.ref.changeId) onOpen({ tab: 'websites', change: a.ref.changeId });
              else if (a.ref.findingId) onOpen({ tab: 'findings', finding: a.ref.findingId, item: a.ref.itemId });
            }}
          />
        )}
      </Paper>
    </Stack>
  );
}
