import { Alert, Badge, Box, Button, Grid, Group, Paper, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { lazy, Suspense, useMemo, useState } from 'react';
import { useEvalSet, useSaveThresholds, useThresholds, useThresholdsPreview } from '../api/hooks';
import type { ModuleId } from '../api/types';
import { ConfusionMatrix, ThresholdSlider } from '../components/Calibration';
import { ErrorState, Loading } from '../components/PageState';
import { fmtInt, fmtPct, fmtProb } from '../lib/format';
import { thresholdLabel } from '../lib/labels';
import { metricsAt, prCurve, presetThresholds, seriesFor, thresholdSweep } from '../lib/metrics';

const PrCurve = lazy(() => import('../components/Charts').then((m) => ({ default: m.PrCurve })));
const ThresholdCurve = lazy(() => import('../components/Charts').then((m) => ({ default: m.ThresholdCurve })));

const PRESETS = [
  { label: 'Wykryj więcej', hint: 'wysoka czułość', beta: 2 },
  { label: 'Zbalansowany', hint: '', beta: 1 },
  { label: 'Mniej fałszywych alarmów', hint: 'wysoka precyzja', beta: 0.5 },
];

/** Rekord trafia do modułu X, gdy pewność LLM dla X >= próg 'module.MX'. */
const MODULES: ModuleId[] = [1, 2, 3];
const KEYS = MODULES.map((m) => `module.M${m}`);

const sameValues = (a: Record<string, number>, b: Record<string, number>) => KEYS.every((k) => Math.abs(a[k] - (b[k] ?? NaN)) < 1e-9);

export function Calibration() {
  const thresholds = useThresholds();
  const evalSet = useEvalSet();
  const save = useSaveThresholds();
  const [draft, setDraft] = useState<Record<string, number> | null>(null);
  const [selected, setSelected] = useState<string>(KEYS[0]);

  const saved = thresholds.data?.values;
  const values = draft ?? saved;
  const dirtyKeys = useMemo(() => (values && saved ? KEYS.filter((k) => Math.abs((values[k] ?? 0) - (saved[k] ?? 0)) > 1e-9) : []), [values, saved]);
  const dirty = dirtyKeys.length > 0;

  const [debounced] = useDebouncedValue(values, 250);
  const preview = useThresholdsPreview(debounced ? Object.fromEntries(KEYS.map((k) => [k, debounced[k] ?? 0.5])) : null);

  const series = useMemo(() => (evalSet.data ? seriesFor(evalSet.data, selected) : null), [evalSet.data, selected]);
  const curve = useMemo(() => (series ? prCurve(series.scores, series.labels) : []), [series]);
  const sweep = useMemo(() => (series ? thresholdSweep(series.scores, series.labels) : []), [series]);
  const t = values?.[selected] ?? 0.5;
  const m = useMemo(() => (series ? metricsAt(series.scores, series.labels, t) : null), [series, t]);
  const positives = useMemo(
    () => Object.fromEntries(KEYS.map((k) => [k, evalSet.data?.filter((it) => it.gold[k] === 1).length ?? 0])),
    [evalSet.data],
  );

  if (thresholds.isError) return <ErrorState error={thresholds.error} onRetry={() => void thresholds.refetch()} />;
  if (evalSet.isError) return <ErrorState error={evalSet.error} onRetry={() => void evalSet.refetch()} />;
  if (!values || !saved || !evalSet.data || !series || !m) return <Loading />;

  const setValue = (key: string, v: number) => setDraft({ ...values, [key]: v });
  const applyPreset = (beta: number) => {
    const next = { ...values, ...presetThresholds(evalSet.data, KEYS, beta) };
    setDraft(sameValues(next, saved) ? null : next);
  };
  const onSave = () =>
    save.mutate(Object.fromEntries(KEYS.map((k) => [k, values[k]])), {
      onSuccess: (res) => {
        setDraft(null);
        notifications.show({ color: 'green', title: 'Progi zapisane', message: `Wersja ${res.version}. Moduły rekordów zostały przeliczone.` });
      },
      onError: (e) => notifications.show({ color: 'red', title: 'Nie zapisano progów', message: e.message }),
    });

  const n = evalSet.data.length;
  const flagged = m.tp + m.fp;

  return (
    <Stack gap="md">
      <Title order={2}>Kalibracja</Title>

      <Alert color="yellow" variant="light" p="xs">
        <Text size="sm">
          Rekord trafia do modułu, gdy pewność modelu językowego dla tego modułu jest co najmniej równa progowi. Zbiór testowy ma tylko{' '}
          {fmtInt(n)} rekordów z ręcznym werdyktem i oceną modelu (pozytywy: {KEYS.map((k) => `${thresholdLabel(k)} ${fmtInt(positives[k])}`).join(', ')}
          ), więc precyzja i pełność są orientacyjne.
        </Text>
      </Alert>

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
              <Badge color="orange" variant="light" tt="none">
                Niezapisane zmiany: {dirtyKeys.length}
              </Badge>
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
              <Stack gap={2}>
                {KEYS.map((k) => (
                  <ThresholdSlider
                    key={k}
                    id={`thr-${k.replace(/\./g, '-')}`}
                    label={thresholdLabel(k)}
                    value={values[k] ?? 0.5}
                    saved={saved[k] ?? 0.5}
                    selected={selected === k}
                    onSelect={() => setSelected(k)}
                    onChange={(v) => setValue(k, v)}
                  />
                ))}
              </Stack>
            </Paper>

            <Paper withBorder p="sm">
              <Text size="sm" fw={600} mb="xs">
                Rekordy w module (wszystkie rekordy)
              </Text>
              <SimpleGrid cols={3} spacing="xs">
                {MODULES.map((mod) => {
                  const before = preview.data?.current[mod];
                  const after = preview.data?.proposed[mod];
                  const ev = preview.data?.eval[mod].proposed;
                  return (
                    <Box key={mod}>
                      <Text size="xs" c="dimmed">
                        {thresholdLabel(`module.M${mod}`)}
                      </Text>
                      <Text fz={20} fw={600} c={before !== undefined && after !== before ? 'orange.8' : undefined}>
                        {before === undefined || after === undefined ? '…' : after === before ? fmtInt(after) : `${fmtInt(before)} → ${fmtInt(after)}`}
                      </Text>
                      {ev && (
                        <Text size="xs" c="dimmed">
                          FP {fmtInt(ev.fp)} · FN {fmtInt(ev.fn)}
                        </Text>
                      )}
                    </Box>
                  );
                })}
              </SimpleGrid>
            </Paper>
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
              Na zbiorze testowym ({fmtInt(series.scores.length)} rekordów) model przy tym progu wskazuje{' '}
              <b>
                {fmtInt(m.tp)} z {fmtInt(m.tp + m.fn)}
              </b>{' '}
              prawdziwych przypadków, pomija <b>{fmtInt(m.fn)}</b> i daje <b>{fmtInt(m.fp)}</b> {m.fp === 1 ? 'fałszywy alarm' : 'fałszywych alarmów'}
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
