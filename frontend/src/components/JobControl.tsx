import { Alert, Badge, Button, Checkbox, Divider, Group, Popover, Progress, Select, Stack, Switch, Text } from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { api, type JobStatus } from '../api/client';
import { fmtDateTime } from '../lib/format';

const PHASE: Record<string, string> = {
  idle: 'Bezczynny',
  starting: 'Start',
  scraping: 'Zbieranie',
  transcription: 'Transkrypcja',
  language: 'Filtr języka',
  llm: 'Ocena LLM',
};

function Last({ s }: { s: JobStatus }) {
  const last = s.last;
  if (!last) return <Text size="xs" c="dimmed">Jeszcze nie było przebiegu.</Text>;
  const st = last.stats;
  return (
    <Stack gap={4}>
      <Text size="xs" c="dimmed">
        Ostatni przebieg: {fmtDateTime(last.finishedAt)} ({last.trigger === 'auto' ? 'auto' : 'ręczny'})
      </Text>
      <Text size="xs">
        Pobrano {st.fetched ?? 0}, nowe {st.new ?? 0}, polskie {st.polish ?? 0}, ocenione {st.classified ?? 0}
      </Text>
      {last.errors.map((e) => (
        <Text key={e} size="xs" c="red">{e}</Text>
      ))}
    </Stack>
  );
}

/** Uruchamianie kolektorów i harmonogram. Meta tylko ręcznie (regulamin dopuszcza automatyzację wyłącznie przez API). */
export function JobControl() {
  const qc = useQueryClient();
  const [opened, setOpened] = useState(false);
  const [includeMeta, setIncludeMeta] = useState(false);
  const status = useQuery({
    queryKey: ['jobs'],
    queryFn: api.jobs,
    retry: false,
    refetchInterval: (q) => (q.state.data?.run.running ? 2000 : 10000),
  });
  const run = useMutation({ mutationFn: () => api.runJob(includeMeta), onSuccess: (d) => qc.setQueryData(['jobs'], d) });
  const schedule = useMutation({ mutationFn: api.setJobSchedule, onSuccess: (d) => qc.setQueryData(['jobs'], d) });

  // nowe rekordy pojawiają się w listach bez odświeżania strony
  const collected = status.data?.collected;
  const seen = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (collected === undefined) return;
    if (seen.current !== undefined && collected !== seen.current) {
      const t = setTimeout(() => qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'jobs' }), 6000);
      seen.current = collected;
      return () => clearTimeout(t);
    }
    seen.current = collected;
  }, [collected, qc]);

  const s = status.data;
  const running = s?.run.running ?? false;
  const pct = s && s.run.total ? Math.round((100 * s.run.done) / s.run.total) : 0;
  return (
    <Popover opened={opened} onChange={setOpened} width={340} position="bottom-end" shadow="md" withArrow>
      <Popover.Target>
        <Button size="compact-sm" variant={running ? 'filled' : 'light'} loading={false} onClick={() => setOpened((o) => !o)}>
          {running ? `Zbieranie… ${pct}%` : 'Zbieranie danych'}
          {s?.schedule.enabled && !running ? ' · auto' : ''}
        </Button>
      </Popover.Target>
      <Popover.Dropdown>
        {status.isError || !s ? (
          <Alert color="orange" p="xs">
            <Text size="xs">Usługa zbierania danych jest niedostępna. Uruchom: docker compose up -d scrape-worker</Text>
          </Alert>
        ) : (
          <Stack gap="xs">
            <Group justify="space-between">
              <Text size="sm" fw={600}>Zbieranie danych</Text>
              <Badge size="sm" variant="light" color={running ? 'blue' : 'gray'}>{PHASE[s.run.phase] ?? s.run.phase}</Badge>
            </Group>
            {running && (
              <>
                <Progress value={pct} size="sm" animated aria-label="Postęp przebiegu" />
                <Text size="xs" c="dimmed">{s.run.current}</Text>
              </>
            )}
            <Button size="xs" disabled={running} loading={run.isPending} onClick={() => run.mutate()}>
              {running ? 'Przebieg trwa' : 'Uruchom teraz'}
            </Button>
            <Checkbox
              size="xs"
              checked={includeMeta}
              disabled={running}
              onChange={(e) => setIncludeMeta(e.currentTarget.checked)}
              label="Uwzględnij Metę (tylko ręcznie)"
            />
            <Divider />
            <Group justify="space-between" wrap="nowrap">
              <Switch
                size="sm"
                label="Auto"
                checked={s.schedule.enabled}
                disabled={schedule.isPending}
                onChange={(e) => schedule.mutate({ enabled: e.currentTarget.checked })}
              />
              <Select
                size="xs"
                w={130}
                aria-label="Częstotliwość"
                allowDeselect={false}
                comboboxProps={{ withinPortal: false }}
                value={String(s.schedule.intervalMin)}
                data={s.intervals.map((m) => ({ value: String(m), label: m < 60 ? `co ${m} min` : `co ${m / 60} h` }))}
                onChange={(v) => v && schedule.mutate({ intervalMin: Number(v) })}
              />
            </Group>
            {s.schedule.enabled && s.schedule.nextRunAt && (
              <Text size="xs" c="dimmed">Następny przebieg: {fmtDateTime(s.schedule.nextRunAt)}</Text>
            )}
            <Text size="xs" c="dimmed">Auto: {s.sources.join(', ')}. Tylko ręcznie: {s.manualOnly.join(', ')}.</Text>
            <Divider />
            <Last s={s} />
            <Text size="xs" c="dimmed">Zebrane przez joby: {s.collected}, czeka na LLM: {s.pending}</Text>
            {run.isError && <Text size="xs" c="red">{(run.error as Error).message}</Text>}
          </Stack>
        )}
      </Popover.Dropdown>
    </Popover>
  );
}
