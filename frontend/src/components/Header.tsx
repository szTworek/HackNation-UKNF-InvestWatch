import { Box, Button, Group, Indicator, Popover, ScrollArea, Stack, Text, Tooltip, UnstyledButton } from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { IconBell, IconCalendar } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { ConnectionState } from '../api/socket';
import { ALERT_COLOR, useAlerts } from '../app/realtime';
import { daysAgoIso, fmtDateTime, todayIso } from '../lib/format';
import { RISK_LABEL } from '../lib/labels';

// ---------------------------------------------------------------------------
// Połączenie WebSocket
// ---------------------------------------------------------------------------

const CONN: Record<ConnectionState, { label: string; color: string }> = {
  connected: { label: 'Połączono', color: 'var(--mantine-color-green-6)' },
  reconnecting: { label: 'Ponawianie połączenia', color: 'var(--mantine-color-yellow-6)' },
  disconnected: { label: 'Rozłączono', color: 'var(--mantine-color-red-6)' },
};

export function ConnectionIndicator({ state }: { state: ConnectionState }) {
  const c = CONN[state];
  // po połączeniu wystarczy kropka z podpowiedzią; tekst tylko, gdy coś jest nie tak
  return (
    <Tooltip label={`Alerty na żywo: ${c.label.toLowerCase()}`} withArrow>
      <Group gap={6} wrap="nowrap" role="status" aria-live="polite" aria-label={`Alerty na żywo: ${c.label}`}>
        <Box w={8} h={8} style={{ borderRadius: '50%', background: c.color }} aria-hidden />
        {state !== 'connected' && (
          <Text size="xs" c="dimmed">
            {c.label}
          </Text>
        )}
      </Group>
    </Tooltip>
  );
}

// ---------------------------------------------------------------------------
// Ocena LLM w tle (GET /load + zdarzenie load:progress)
// ---------------------------------------------------------------------------

export function LoadIndicator() {
  const p = useQuery({ queryKey: ['load'], queryFn: api.load, retry: false, staleTime: Infinity }).data;
  if (!p || (!p.running && p.pending === 0)) return null;
  return (
    <Text size="xs" c="dimmed" role="status" style={{ whiteSpace: 'nowrap' }}>
      {p.running ? `Ocena w tle: ${p.done}/${p.total}` : `Czeka na ocenę: ${p.pending}`}
    </Text>
  );
}

// ---------------------------------------------------------------------------
// Alerty wysokiego ryzyka (zdarzenie finding:high_risk)
// ---------------------------------------------------------------------------

export function AlertBell() {
  const { alerts, unread, markRead, markAllRead } = useAlerts();
  const [opened, setOpened] = useState(false);
  const navigate = useNavigate();
  return (
    <Popover opened={opened} onChange={setOpened} position="bottom-end" width={380} shadow="md" withinPortal>
      <Popover.Target>
        <Indicator label={unread} size={16} color="red" disabled={unread === 0} offset={6}>
          <button type="button" className="iw-tool" aria-label={`Alerty wysokiego ryzyka, nieprzeczytane: ${unread}`} onClick={() => setOpened((o) => !o)}>
            <IconBell size={20} stroke={1.6} style={{ verticalAlign: 'middle' }} />
          </button>
        </Indicator>
      </Popover.Target>
      <Popover.Dropdown p={0}>
        <Group justify="space-between" px="sm" py={8} style={{ borderBottom: '1px solid var(--iw-border)' }}>
          <Text size="sm" fw={600}>
            Alerty wysokiego ryzyka
          </Text>
          <Button variant="subtle" size="compact-xs" disabled={unread === 0} onClick={markAllRead}>
            Oznacz wszystkie jako przeczytane
          </Button>
        </Group>
        {alerts.length === 0 ? (
          <Text size="sm" c="dimmed" p="sm">
            Brak alertów od otwarcia strony.
          </Text>
        ) : (
          <ScrollArea.Autosize mah={420}>
            <Stack gap={0}>
              {alerts.map((a) => (
                <UnstyledButton
                  key={a.id}
                  px="sm"
                  py={8}
                  style={{ borderBottom: '1px solid var(--iw-border-soft)', background: a.read ? undefined : 'var(--iw-soft)' }}
                  onClick={() => {
                    markRead(a.id);
                    setOpened(false);
                    navigate(`/findings/${a.id}`);
                  }}
                >
                  <Group gap={8} wrap="nowrap" align="flex-start">
                    <Box mt={6} w={8} h={8} style={{ borderRadius: 2, flexShrink: 0, background: `var(--mantine-color-${ALERT_COLOR[a.riskLevel] ?? 'orange'}-6)` }} aria-hidden />
                    <div style={{ minWidth: 0 }}>
                      <Text size="sm" fw={a.read ? 400 : 600} truncate>
                        {a.entity}
                      </Text>
                      <Text size="xs" lineClamp={2}>
                        {a.title}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {RISK_LABEL[a.riskLevel]} · {fmtDateTime(a.receivedAt)}
                      </Text>
                    </div>
                  </Group>
                </UnstyledButton>
              ))}
            </Stack>
          </ScrollArea.Autosize>
        )}
      </Popover.Dropdown>
    </Popover>
  );
}

// ---------------------------------------------------------------------------
// Zakres dat
// ---------------------------------------------------------------------------

export function DateRangeFilter({ from, to, onChange }: { from: string; to: string; onChange: (from: string, to: string) => void }) {
  return (
    <Group gap={8} wrap="nowrap">
      <Text component="label" htmlFor="global-date-range" size="sm" c="dimmed" visibleFrom="md">
        Zakres dat
      </Text>
      <DatePickerInput
        id="global-date-range"
        type="range"
        size="xs"
        w={210}
        value={[from, to]}
        maxDate={todayIso()}
        valueFormat="DD.MM.YYYY"
        leftSection={<IconCalendar size={14} />}
        allowSingleDateInRange
        presets={[
          { value: [todayIso(), todayIso()], label: 'Dziś' },
          { value: [daysAgoIso(6), todayIso()], label: 'Ostatnie 7 dni' },
          { value: [daysAgoIso(29), todayIso()], label: 'Ostatnie 30 dni' },
          { value: [daysAgoIso(89), todayIso()], label: 'Ostatnie 90 dni' },
        ]}
        onChange={([a, b]) => {
          if (a && b) onChange(a, b);
        }}
      />
    </Group>
  );
}
