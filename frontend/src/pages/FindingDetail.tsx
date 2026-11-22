import { Accordion, Badge, Box, Button, Grid, Group, Modal, Paper, Stack, Tabs, Text, Title, UnstyledButton } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useFinding, useRules, useThresholds, useUpdateStatus } from '../api/hooks';
import type { ContentType, Finding, FlagKey, Instrument, RuleDef, TopicLabel } from '../api/types';
import { ModuleBadges, RiskBadge, StatusBadge } from '../components/Badges';
import { EntityList } from '../components/EntityList';
import { FindingMeta, LinkList } from '../components/FindingPanels';
import { HighlightedText } from '../components/HighlightedText';
import { ErrorState, Loading } from '../components/PageState';
import { ProbBar } from '../components/ProbBar';
import { ModuleReport } from '../components/ModuleReport';
import { RiskGauge } from '../components/RiskGauge';
import { RulesChecklist } from '../components/RulesChecklist';
import { RevisionDiff, StatusChanger, StatusHistory } from '../components/StatusPanel';
import { activeFlags, evidenceSpans, firstEvidence, flagThreshold, snippet, thresholdOf, type ThresholdValues } from '../lib/findings';
import { fmtPct } from '../lib/format';
import {
  ALL_FLAGS,
  CONTENT_TYPES,
  CONTENT_TYPE_LABEL,
  FLAG_COLOR,
  FLAG_LABEL,
  INSTRUMENTS,
  INSTRUMENT_LABEL,
  POSITIVE_FLAGS,
  TOPICS,
  TOPIC_LABEL,
} from '../lib/labels';
type Tab = 'content' | 'video' | 'history';

export function FindingDetail() {
  const { id } = useParams();
  const finding = useFinding(id);
  const thresholds = useThresholds();
  const allRules = useRules();
  const [tab, setTab] = useState<Tab>('content');
  const [activeFlag, setActiveFlag] = useState<FlagKey | null>(null);
  const [statusOpen, setStatusOpen] = useState(false);
  const updateStatus = useUpdateStatus();

  const tv = thresholds.data?.values;
  const f = finding.data;

  if (finding.isError) return <ErrorState error={finding.error} onRetry={() => void finding.refetch()} />;
  if (!f) return <Loading />;

  // kliknięcie wykrytej cechy: przełącz na zakładkę z dowodem i przewiń do fragmentu
  const focusFlag = (flag: FlagKey) => {
    setActiveFlag((cur) => (cur === flag ? null : flag));
    const ev = firstEvidence(f, flag);
    if (!ev || ev.section === 'ocr') return;
    setTab(ev.section === 'transcript' && f.transcript ? 'video' : 'content');
    window.setTimeout(() => document.getElementById(`ev-${ev.section}-${flag}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 150);
  };

  return (
    <Stack gap="lg">

      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <div>
          <Title order={2}>{f.title ?? f.author.handle}</Title>
          <Text size="sm" c="dimmed">
            {f.id}
          </Text>
        </div>
        <Group gap="sm">
          <ModuleBadges modules={f.modules} />
          <RiskBadge level={f.riskLevel} size="lg" />
          <StatusBadge status={f.status} size="lg" />
          <Button onClick={() => setStatusOpen(true)}>Zmień status</Button>
        </Group>
      </Group>

      {allRules.data && <ModuleReport finding={f} rules={allRules.data} thresholds={tv} />}

      <Tabs value={tab} onChange={(v) => setTab((v as Tab) ?? 'content')} keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="content">Treść</Tabs.Tab>
          {f.transcript && <Tabs.Tab value="video">Wideo</Tabs.Tab>}
          <Tabs.Tab value="history">
            Historia ({f.history.length}){f.revisions?.length ? ', treść zmieniona' : ''}
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="content" pt="md">
          <ContentTab finding={f} tv={tv} activeFlag={activeFlag} onFlag={focusFlag} />
        </Tabs.Panel>

        {f.transcript && (
          <Tabs.Panel value="video" pt="md">
            <Paper withBorder p="md">
              <Title order={5} mb="sm">
                Transkrypcja
              </Title>
              <HighlightedText text={f.transcript} spans={evidenceSpans(f, tv, 'transcript')} idPrefix="ev-transcript" activeFlag={activeFlag} />
            </Paper>
          </Tabs.Panel>
        )}

        <Tabs.Panel value="history" pt="md">
          <Stack maw={720} gap="md">
            {f.revisions?.map((r) => (
              <Paper key={r.fetchedAt} p="lg" withBorder>
                <RevisionDiff revision={r} current={f.riskLevel} />
              </Paper>
            ))}
            <Paper p="lg">
              <StatusHistory history={f.history} />
            </Paper>
          </Stack>
        </Tabs.Panel>
      </Tabs>

      <Modal opened={statusOpen} onClose={() => setStatusOpen(false)} title="Zmień status" centered>
        <StatusChanger
          key={f.status}
          status={f.status}
          loading={updateStatus.isPending}
          onSubmit={(status, comment) =>
            updateStatus.mutate(
              { id: f.id, status, comment: comment || undefined },
              {
                onSuccess: () => setStatusOpen(false),
                onError: (e) => notifications.show({ color: 'red', title: 'Nie zapisano statusu', message: e.message }),
              },
            )
          }
        />
      </Modal>
    </Stack>
  );
}

// ---------------------------------------------------------------------------
// Zakładka „Treść”: tekst z dowodami, co wykryto, naruszone reguły, status
// ---------------------------------------------------------------------------

function ContentTab({
  finding: f,
  tv,
  activeFlag,
  onFlag,
}: {
  finding: Finding;
  tv: ThresholdValues | undefined;
  activeFlag: FlagKey | null;
  onFlag: (flag: FlagKey) => void;
}) {
  const rules = useRules();
  const spans = useMemo(() => evidenceSpans(f, tv, 'text'), [f, tv]);
  const risky = activeFlags(f, tv, 'risk');
  const positive = activeFlags(f, tv, 'positive');
  const m1m3 = f.modules.includes(1) || f.modules.includes(3);

  return (
    <Grid gutter="md">
      <Grid.Col span={{ base: 12, lg: 7 }}>
        <Stack gap="md">
          <Paper withBorder p="md">
            <HighlightedText text={f.text} spans={spans} activeFlag={activeFlag} idPrefix="ev-text" />
            {f.transcript && (
              <Text size="xs" c="dimmed" mt="sm">
                Transkrypcja filmu jest w zakładce „Wideo”.
              </Text>
            )}
          </Paper>
          <Paper withBorder p="md">
            <FindingMeta finding={f} />
            {f.outboundLinks.length > 0 && (
              <Stack gap={4} mt="sm">
                <Text size="xs" c="dimmed">
                  Linki wychodzące
                </Text>
                <LinkList finding={f} />
              </Stack>
            )}
          </Paper>

        </Stack>
      </Grid.Col>

      <Grid.Col span={{ base: 12, lg: 5 }}>
        <Stack gap="md">
          <Paper p="md">
            <RiskGauge
              score={f.riskScore}
              level={f.riskLevel}
              medium={thresholdOf(tv, 'risk.MEDIUM', 0.4)}
              high={thresholdOf(tv, 'risk.HIGH', 0.65)}
              critical={thresholdOf(tv, 'risk.CRITICAL', 0.85)}
            />
          </Paper>
          <Paper withBorder p="md">
            <Title order={5} mb="sm">
              Co wykryto
            </Title>
            {risky.length === 0 ? (
              <Text size="sm" c="dimmed">
                Nic powyżej progów.
              </Text>
            ) : (
              <Stack gap={2}>
                {risky.map((h) => (
                  <FlagRow key={h.flag} flag={h.flag} p={h.p} count={f.flags[h.flag].evidence.length} active={activeFlag === h.flag} onClick={() => onFlag(h.flag)} />
                ))}
              </Stack>
            )}
            {positive.length > 0 && (
              <Group gap={6} mt="sm">
                <Text size="xs" c="dimmed">
                  Znaleziono też:
                </Text>
                {positive.map((h) => (
                  <Badge key={h.flag} color="teal" variant="light" size="sm" tt="none" style={{ cursor: 'pointer' }} onClick={() => onFlag(h.flag)}>
                    {FLAG_LABEL[h.flag]}
                  </Badge>
                ))}
              </Group>
            )}
          </Paper>

          {rules.data && <ViolatedRules defs={rules.data} finding={f} />}

          {(m1m3 || f.entities.length > 0) && (
            <Paper withBorder p="md" >
              <Title order={5} mb="sm">
                Podmioty i rejestr KNF
              </Title>
              <EntityList entities={f.entities} />
            </Paper>
          )}

          <Accordion variant="contained" chevronPosition="right">
            <Accordion.Item value="model">
              <Accordion.Control>
                <Text size="sm" fw={500}>
                  Szczegóły modelu
                </Text>
              </Accordion.Control>
              <Accordion.Panel>
                <ModelDetails finding={f} tv={tv} />
              </Accordion.Panel>
            </Accordion.Item>
          </Accordion>
        </Stack>
      </Grid.Col>
    </Grid>
  );
}

function FlagRow({ flag, p, count, active, onClick }: { flag: FlagKey; p: number; count: number; active: boolean; onClick: () => void }) {
  return (
    <UnstyledButton
      onClick={onClick}
      disabled={count === 0}
      px={8}
      py={6}
      style={{ borderRadius: 4, background: active ? '#f1f3f6' : undefined }}
      aria-pressed={active}
    >
      <Group justify="space-between" wrap="nowrap">
        <Group gap={8} wrap="nowrap">
          <Box w={10} h={10} style={{ borderRadius: 2, background: `var(--mantine-color-${FLAG_COLOR[flag]}-5)`, flexShrink: 0 }} aria-hidden />
          <Text size="sm">{FLAG_LABEL[flag]}</Text>
        </Group>
        <Text size="sm" c="dimmed">
          {fmtPct(p)}
        </Text>
      </Group>
    </UnstyledButton>
  );
}

function ViolatedRules({ defs, finding: f }: { defs: RuleDef[]; finding: Finding }) {
  const [full, setFull] = useState(false);
  const byId = new Map(defs.map((d) => [d.id, d]));
  const violations = f.rules.filter((r) => r.status === 'VIOLATION');
  const applicable = f.rules.some((r) => r.status !== 'NOT_APPLICABLE');
  if (!applicable) return null;
  return (
    <Paper withBorder p="md">
      <Title order={5} mb="sm">
        Reguły do weryfikacji
      </Title>
      {violations.length === 0 ? (
        <Text size="sm" c="dimmed">
          Brak reguł do weryfikacji.
        </Text>
      ) : (
        <Stack gap="sm">
          {violations.map((r) => {
            const d = byId.get(r.ruleId);
            const ev = r.evidence[0];
            return (
              <div key={r.ruleId}>
                <Text size="sm" fw={500}>
                  {d?.name ?? r.ruleId}
                </Text>
                <Text size="xs" c="dimmed">
                  {d?.legalBasis}
                </Text>
                {ev && (
                  <Text size="xs" fs="italic" mt={2}>
                    „{snippet(ev.text, 100)}”
                  </Text>
                )}
              </div>
            );
          })}
        </Stack>
      )}
      <Button variant="subtle" size="xs" mt="sm" px={0} onClick={() => setFull((v) => !v)}>
        {full ? 'Ukryj pełną listę' : 'Pełna lista reguł'}
      </Button>
      {full && <RulesChecklist defs={defs} results={f.rules} />}
    </Paper>
  );
}

function ModelDetails({ finding: f, tv }: { finding: Finding; tv: ThresholdValues | undefined }) {
  const flagRows = ALL_FLAGS.map((k) => ({ flag: k, p: f.flags[k]?.p ?? 0 }))
    .filter((r) => r.p >= flagThreshold(tv, r.flag) * 0.6)
    .sort((a, b) => b.p - a.p);
  const group = (title: string, rows: { label: string; p: number; t?: number }[]) => (
    <Stack gap={2} mb="sm">
      <Text size="sm" fw={600}>
        {title}
      </Text>
      {rows
        .filter((r) => r.p >= 0.15)
        .sort((a, b) => b.p - a.p)
        .map((r) => (
          <ProbBar key={r.label} label={r.label} p={r.p} threshold={r.t} color="gray.6" />
        ))}
    </Stack>
  );
  return (
    <>
      <Stack gap={2} mb="sm">
        <Text size="sm" fw={600}>
          Flagi (kreska = próg)
        </Text>
        {flagRows.map((r) => (
          <ProbBar key={r.flag} label={FLAG_LABEL[r.flag]} p={r.p} threshold={flagThreshold(tv, r.flag)} color={POSITIVE_FLAGS.has(r.flag) ? 'teal' : FLAG_COLOR[r.flag]} />
        ))}
      </Stack>
      {group('Temat', TOPICS.map((t: TopicLabel) => ({ label: TOPIC_LABEL[t], p: f.topic[t] })))}
      {group('Typ treści', CONTENT_TYPES.map((c: ContentType) => ({ label: CONTENT_TYPE_LABEL[c], p: f.contentType[c], t: thresholdOf(tv, `contentType.${c}`, 0.4) })))}
      {group('Instrumenty', INSTRUMENTS.map((i: Instrument) => ({ label: INSTRUMENT_LABEL[i], p: f.instruments[i] })))}
    </>
  );
}
