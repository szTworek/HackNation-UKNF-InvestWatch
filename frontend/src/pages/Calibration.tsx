import { Accordion, Badge, Box, Button, Grid, Group, Paper, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { lazy, Suspense, useMemo, useState } from 'react';
import { useEvalSet, useSaveThresholds, useThresholds, useThresholdsPreview } from '../api/hooks';
import { ConfusionMatrix, ThresholdSlider } from '../components/Calibration';
import { ErrorState, Loading } from '../components/PageState';
import { fmtInt, fmtPct, fmtProb } from '../lib/format';
import { thresholdGroup, thresholdLabel, thresholdOrder, SCAM_THRESHOLD_KEY } from '../lib/labels';
import { metricsAt, prCurve, presetThresholds, seriesFor, thresholdSweep } from '../lib/metrics';

const PrCurve = lazy(() => import('../components/Charts').then((m) => ({ default: m.PrCurve })));
const ThresholdCurve = lazy(() => import('../components/Charts').then((m) => ({ default: m.ThresholdCurve })));

const PRESETS = [
  { label: 'Wykryj więcej', hint: 'wysoka czułość', beta: 2 },
  { label: 'Zbalansowany', hint: '', beta: 1 },
  { label: 'Mniej fałszywych alarmów', hint: 'wysoka precyzja', beta: 0.5 },
];

/** Progi widoczne od razu; reszta w zwiniętych sekcjach. */
const MAIN_KEYS = [SCAM_THRESHOLD_KEY, 'risk.HIGH', 'risk.CRITICAL', 'risk.MEDIUM'];

const sameValues = (a: Record<string, number>, b: Record<string, number>) => Object.keys(a).every((k) => Math.abs(a[k] - (b[k] ?? NaN)) < 1e-9);

export function Calibration() {
  const thresholds = useThresholds();
  const evalSet = useEvalSet();
  const save = useSaveThresholds();
  const [draft, setDraft] = useState<Record<string, number> | null>(null);
  const [selected, setSelected] = useState<string>(SCAM_THRESHOLD_KEY);

  const saved = thresholds.data?.values;
  const values = draft ?? saved;
  const dirtyKeys = useMemo(() => (values && saved ? Object.keys(values).filter((k) => Math.abs(values[k] - saved[k]) > 1e-9) : []), [values, saved]);
  const dirty = dirtyKeys.length > 0;

  const [debounced] = useDebouncedValue(values, 300);
  const preview = useThresholdsPreview(dirty && debounced ? debounced : null);

  const sorted = (g: string) =>
    Object.keys(saved ?? {})
      .filter((k) => thresholdGroup(k) === g)
      .sort((a, b) => thresholdOrder(a) - thresholdOrder(b));

  const series = useMemo(() => (evalSet.data ? seriesFor(evalSet.data, selected) : null), [evalSet.data, selected]);
  const curve = useMemo(() => (series ? prCurve(series.scores, series.labels) : []), [series]);
  const sweep = useMemo(() => (series ? thresholdSweep(series.scores, series.labels) : []), [series]);
  const t = values?.[selected] ?? 0.5;
  const m = useMemo(() => (series ? metricsAt(series.scores, series.labels, t) : null), [series, t]);

  if (thresholds.isError) return <ErrorState error={thresholds.error} onRetry={() => void thresholds.refetch()} />;
  if (evalSet.isError) return <ErrorState error={evalSet.error} onRetry={() => void evalSet.refetch()} />;
  if (!values || !saved || !evalSet.data || !series || !m) return <Loading />;

  const setValue = (key: string, v: number) => setDraft({ ...values, [key]: v });
  const applyPreset = (beta: number) => {
    const next = { ...values, ...presetThresholds(evalSet.data, Object.keys(values), beta) };
    setDraft(sameValues(next, saved) ? null : next);
  };
  const onSave = () =>
    save.mutate(values, {
      onSuccess: (res) => {
        setDraft(null);
        notifications.show({ color: 'green', title: 'Progi zapisane', message: `Wersja ${res.version}. Poziomy ryzyka zostały przeliczone.` });
      },
      onError: (e) => notifications.show({ color: 'red', title: 'Nie zapisano progów', message: e.message }),
    });

  const slider = (k: string) => (
    <ThresholdSlider
      key={k}
      id={`thr-${k.replace(/\./g, '-')}`}
      label={thresholdLabel(k)}
      value={values[k]}
      saved={saved[k]}
      selected={selected === k}
      onSelect={() => setSelected(k)}
      onChange={(v) => setValue(k, v)}
    />
  );

  const highCrit = (r?: Record<string, number>) => (r ? (r.HIGH ?? 0) + (r.CRITICAL ?? 0) : undefined);
  const before = highCrit(preview.data?.current);
  const after = highCrit(preview.data?.proposed);
  const positives = m.tp + m.fn;
  const flagged = m.tp + m.fp;
  const flagKeys = sorted('flags');
  const ctKeys = sorted('contentType');

  return (
    <Stack gap="md">
      <Title order={2}>Kalibracja</Title>

      <Paper withBorder p="sm">
        <Group justify="space-between" gap="sm">
          <Group gap="xs">
            {PRESETS.map((p) => (
              <Button key={p.beta} variant="default" size="xs" onClick={() => applyPreset(p.beta)} title={p.hint || undefined}>
                {p.label}
              </Button>
            ))}
          </Group>
          <Group gap="sm">
            {dirty && (
              <>
                <Badge color="orange" variant="light" tt="none">
                  Niezapisane zmiany: {dirtyKeys.length}
                </Badge>
                <Text size="sm">
                  Wysokie i krytyczne (30 dni):{' '}
                  {before === undefined || after === undefined ? '…' : <b>{`${fmtInt(before)} → ${fmtInt(after)}`}</b>}
                </Text>
              </>
            )}
            <Button variant="default" size="xs" disabled={!dirty} onClick={() => setDraft(null)}>
              Przywróć
            </Button>
            <Button size="xs" disabled={!dirty} loading={save.isPending} onClick={onSave}>
              Zapisz
            </Button>
          </Group>
        </Group>
      </Paper>

      <Grid gutter="md">
        <Grid.Col span={{ base: 12, lg: 5 }}>
          <Stack gap="sm">
            <Paper withBorder p="xs">
              <Stack gap={2}>{MAIN_KEYS.filter((k) => k in values).map(slider)}</Stack>
            </Paper>
            <Accordion variant="contained" multiple>
              <Accordion.Item value="flags">
                <Accordion.Control>
                  <Text size="sm">Progi wykrywanych cech ({flagKeys.length})</Text>
                </Accordion.Control>
                <Accordion.Panel>
                  <Stack gap={2}>{flagKeys.map(slider)}</Stack>
                </Accordion.Panel>
              </Accordion.Item>
              <Accordion.Item value="ct">
                <Accordion.Control>
                  <Text size="sm">Progi typu treści ({ctKeys.length})</Text>
                </Accordion.Control>
                <Accordion.Panel>
                  <Stack gap={2}>{ctKeys.map(slider)}</Stack>
                </Accordion.Panel>
              </Accordion.Item>
            </Accordion>
          </Stack>
        </Grid.Col>

        <Grid.Col span={{ base: 12, lg: 7 }}>
          <Paper withBorder p="md" style={{ position: 'sticky', top: 72 }}>
            <Group justify="space-between" align="flex-start" mb="xs">
              <Title order={5}>{thresholdLabel(selected)}</Title>
              <Text fz={24} fw={600}>
                {fmtProb(t)}
              </Text>
            </Group>
            <Text size="md" mb="md">
              Na zbiorze testowym ({fmtInt(series.scores.length)} ręcznie ocenionych przykładów) model przy tym progu wskazuje{' '}
              <b>{fmtInt(m.tp)} z {fmtInt(positives)}</b> prawdziwych przypadków i daje <b>{fmtInt(m.fp)}</b>{' '}
              {m.fp === 1 ? 'fałszywy alarm' : 'fałszywych alarmów'}
              {flagged ? ` na ${fmtInt(flagged)} zgłoszeń` : ''}.
            </Text>

            <SimpleGrid cols={3} spacing="xs" mb="md">
              <Metric label="Precyzja" value={fmtPct(m.precision)} />
              <Metric label="Pełność (recall)" value={fmtPct(m.recall)} />
              <Metric label="F1" value={fmtProb(m.f1)} />
            </SimpleGrid>

            <ConfusionMatrix c={m} />

            <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md" mt="md">
              <div>
                <Text size="sm" fw={600} mb={4}>
                  Krzywa PR
                </Text>
                <Suspense fallback={<Loading />}>
                  <PrCurve curve={curve} current={m} height={200} />
                </Suspense>
              </div>
              <div>
                <Text size="sm" fw={600} mb={4}>
                  Precyzja i pełność a próg
                </Text>
                <Suspense fallback={<Loading />}>
                  <ThresholdCurve sweep={sweep} threshold={t} precision={m.precision} recall={m.recall} height={176} />
                </Suspense>
              </div>
            </SimpleGrid>
          </Paper>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <Box>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text fz={20} fw={600}>
        {value}
      </Text>
    </Box>
  );
}
