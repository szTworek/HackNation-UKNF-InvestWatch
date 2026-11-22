import { Alert, Button, Grid, Group, Paper, Select, SimpleGrid, Stack, Table, Text, Title } from '@mantine/core';
import { IconPrinter } from '@tabler/icons-react';
import { useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import type { SourcePlatform } from '../api/entityTypes';
import { useEntities, useEntity, useEntityAlerts, useEntityFindings, useEntityPages } from '../api/hooks';
import { DistributionBars } from '../components/Charts';
import { FindingsByDayChart, LabeledBars, daysFromFindings } from '../components/EntityCharts';
import { EntityModuleBadge, RiskMeter, SeverityBadge, pageChanges, shortUrl } from '../components/EntityParts';
import { ErrorState, Loading } from '../components/PageState';
import { fmtDate, fmtDateTime, fmtInt, fmtProb } from '../lib/format';
import { ENTITY_MODULES, ENTITY_MODULE_COLOR, ENTITY_MODULE_LABEL, KNF_CATEGORY_LABEL, SOURCE_PLATFORM_LABEL, ruleModule, ruleText } from '../lib/labels';

function Report({ id }: { id: string }) {
  const ent = useEntity(id);
  const pages = useEntityPages(id);
  const alerts = useEntityAlerts(id);
  const { findings, isLoading } = useEntityFindings(id);
  const trend = useMemo(() => daysFromFindings(findings), [findings]);
  const top = useMemo(() => [...findings].sort((a, b) => b.score - a.score).slice(0, 12), [findings]);
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

  const e = ent.data;
  if (ent.isError) return <ErrorState error={ent.error} onRetry={() => void ent.refetch()} />;
  if (!e || isLoading || pages.isLoading || alerts.isLoading) return <Loading />;
  const changes = pageChanges(pages.data ?? []);
  const noWarn = (pages.data ?? []).filter((p) => p.lastSnapshot && !p.lastSnapshot.riskWarning.present);
  const open = (alerts.data ?? []).filter((a) => a.status === 'new');

  return (
    <Paper p="xl" className="iw-report" maw={1000} mx="auto" w="100%">
      <Stack gap="lg">
        <Group align="flex-start" justify="space-between" pb="md" style={{ borderBottom: '2px solid var(--iw-text)' }}>
          <div>
            <Text size="xs" fw={700} tt="uppercase" c="knf.7">
              InvestWatch · raport podmiotu
            </Text>
            <Title order={2} mt={4}>
              {e.name}
            </Title>
            {e.registryEntries.map((r) => (
              <Text key={r.name} size="sm" c="dimmed">
                <b>{r.name}</b> · {KNF_CATEGORY_LABEL[r.category]} · {r.country}
              </Text>
            ))}
            {e.domains.length > 0 && (
              <Text size="sm" c="dimmed">
                Domeny: {e.domains.join(', ')}
              </Text>
            )}
          </div>
          <div style={{ width: 180 }}>
            <Text size="xs" c="dimmed">
              Ryzyko (0–100)
            </Text>
            {e.kpis && <RiskMeter value={e.kpis.riskScore} />}
            <Text size="xs" c="dimmed" mt="sm">
              Wygenerowano {fmtDateTime(new Date().toISOString())}
            </Text>
            <Text size="xs" c="dimmed">
              Ocena: model ai-service i weryfikacja LLM
            </Text>
          </div>
        </Group>

        {!e.hasData ? (
          <Alert color="gray" title="Brak zebranych danych">
            Podmiot jest tylko w rejestrze KNF; nie jest monitorowany, więc raport nie zawiera wyników.
          </Alert>
        ) : (
          <>
            <SimpleGrid cols={5}>
              {[
                ['Rekordy', e.kpis?.items ?? 0],
                ['Wyniki', e.kpis?.findingsOpen ?? 0],
                ['Nowe alerty', e.kpis?.alertsNew ?? 0],
                ['Strony WWW', e.monitoredPages],
                ['Zmiany stron (7 dni)', e.kpis?.pagesChanged7d ?? 0],
              ].map(([l, v]) => (
                <Paper key={l} p="sm">
                  <Text fz={22} fw={600} className="iw-kpi-value">
                    {fmtInt(Number(v))}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {l}
                  </Text>
                </Paper>
              ))}
            </SimpleGrid>

            <SimpleGrid cols={3}>
              {ENTITY_MODULES.map((m) => (
                <Paper key={m} p="sm" style={{ borderTop: `3px solid ${ENTITY_MODULE_COLOR[m]}` }}>
                  <Group gap={6}>
                    <EntityModuleBadge m={m} />
                    <Text size="sm" fw={600}>
                      {ENTITY_MODULE_LABEL[m]}
                    </Text>
                  </Group>
                  <Group justify="space-between" mt={6}>
                    <Text size="sm">
                      <b>{fmtInt(e.modules[m].findings)}</b> wyników
                    </Text>
                    <Text size="sm" c="dimmed">
                      średnio {e.modules[m].findings ? Math.round(e.modules[m].avgScore * 100) : '—'}
                    </Text>
                  </Group>
                </Paper>
              ))}
            </SimpleGrid>

            <Grid gutter="md">
              <Grid.Col span={7}>
                <Paper p="md" h="100%">
                  <Title order={5} mb="sm">
                    Wyniki w ostatnich 30 dniach
                  </Title>
                  <FindingsByDayChart data={trend} height={210} />
                </Paper>
              </Grid.Col>
              <Grid.Col span={5}>
                <Paper p="md" h="100%">
                  <Title order={5} mb="sm">
                    Rekordy wg platformy
                  </Title>
                  <DistributionBars data={Object.entries(e.platforms).map(([p, v]) => ({ label: SOURCE_PLATFORM_LABEL[p as SourcePlatform] ?? p, value: v ?? 0 }))} />
                </Paper>
              </Grid.Col>
            </Grid>

            <Paper p="md">
              <Title order={5} mb="sm">
                Najczęstsze naruszenia
              </Title>
              <LabeledBars rows={rules.map(([k, v]) => ({ key: k, label: ruleText(k, v.label), value: v.n, color: ENTITY_MODULE_COLOR[ruleModule(k)] }))} />
            </Paper>

            <Paper p="md" className="iw-print-break">
              <Title order={5} mb="sm">
                Najpoważniejsze wyniki
              </Title>
              <Table verticalSpacing={6}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Waga</Table.Th>
                    <Table.Th>Moduł</Table.Th>
                    <Table.Th>Naruszenie i dowód</Table.Th>
                    <Table.Th>Źródło</Table.Th>
                    <Table.Th ta="right">Wynik</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {top.map((f) => (
                    <Table.Tr key={f.id} style={{ verticalAlign: 'top' }}>
                      <Table.Td>
                        <SeverityBadge s={f.severity} />
                      </Table.Td>
                      <Table.Td>
                        <EntityModuleBadge m={f.module} />
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" fw={500}>
                          {f.ruleHits[0] ? ruleText(f.ruleHits[0].ruleId, f.ruleHits[0].label) : ''}
                        </Text>
                        <Text size="xs" c="dimmed" fs="italic" lineClamp={2}>
                          „{f.ruleHits[0]?.evidence}”
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm">{SOURCE_PLATFORM_LABEL[f.item.platform]}</Text>
                        <Text size="xs" c="dimmed" truncate maw={180}>
                          {f.item.author}
                        </Text>
                      </Table.Td>
                      <Table.Td ta="right" fw={600}>
                        {fmtProb(f.score)}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Paper>

            <Grid gutter="md">
              <Grid.Col span={6}>
                <Paper p="md" h="100%">
                  <Title order={5} mb="sm">
                    Zmiany stron WWW
                  </Title>
                  {changes.length ? (
                    <Stack gap={8}>
                      {changes.map((c) => (
                        <div key={c.id}>
                          <Text size="sm" fw={600}>
                            {c.summary}
                          </Text>
                          <Text size="xs" c="dimmed">
                            {shortUrl(c.url)} · {fmtDate(c.detectedAt)}
                            {c.mock ? ' · atrapa' : ''}
                          </Text>
                        </div>
                      ))}
                    </Stack>
                  ) : (
                    <Text size="sm" c="dimmed">
                      Brak zmian.
                    </Text>
                  )}
                  {noWarn.length > 0 && (
                    <Alert color="red" mt="sm" p="xs">
                      <Text size="xs">Strony bez ostrzeżenia o ryzyku: {noWarn.map((p) => shortUrl(p.url)).join(', ')}</Text>
                    </Alert>
                  )}
                </Paper>
              </Grid.Col>
              <Grid.Col span={6}>
                <Paper p="md" h="100%">
                  <Title order={5} mb="sm">
                    Nowe alerty
                  </Title>
                  {open.length ? (
                    <Stack gap={6}>
                      {open.slice(0, 8).map((a) => (
                        <Group key={a.id} gap={8} wrap="nowrap" align="flex-start">
                          <SeverityBadge s={a.severity} />
                          <Text size="sm">{a.title}</Text>
                        </Group>
                      ))}
                      {open.length > 8 && (
                        <Text size="xs" c="dimmed">
                          i jeszcze {open.length - 8}
                        </Text>
                      )}
                    </Stack>
                  ) : (
                    <Text size="sm" c="dimmed">
                      Brak nowych alertów.
                    </Text>
                  )}
                </Paper>
              </Grid.Col>
            </Grid>
          </>
        )}
        <Text size="xs" c="dimmed" pt="sm" style={{ borderTop: '1px solid var(--iw-border)' }}>
          Wyniki pochodzą z modelu ai-service i weryfikacji LLM, wymagają oceny analityka i nie są rozstrzygnięciem nadzorczym. Reguły R01–R18 według
          art. 44 rozporządzenia delegowanego (UE) 2017/565.
        </Text>
      </Stack>
    </Paper>
  );
}

export function Reports() {
  const { id } = useParams();
  const navigate = useNavigate();
  const ents = useEntities();
  const monitored = (ents.data ?? []).filter((e) => e.hasData);
  const sel = id ?? monitored[0]?.id;
  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end" className="iw-no-print">
        <div>
          <Title order={2}>Raporty</Title>
          <Text c="dimmed" mt={4}>
            Raport podmiotu do druku. „Drukuj / PDF” otwiera okno drukowania; wybierz „Zapisz jako PDF”.
          </Text>
        </div>
        <Group gap="sm" align="flex-end">
          <Select
            label="Podmiot"
            value={sel ?? null}
            onChange={(v) => v && navigate(`/reports/${v}`)}
            data={monitored.map((e) => ({ value: e.id, label: e.name }))}
            allowDeselect={false}
            w={220}
          />
          <Button leftSection={<IconPrinter size={16} />} onClick={() => window.print()}>
            Drukuj / PDF
          </Button>
        </Group>
      </Group>
      {ents.isError ? <ErrorState error={ents.error} onRetry={() => void ents.refetch()} /> : sel ? <Report key={sel} id={sel} /> : <Loading />}
    </Stack>
  );
}
