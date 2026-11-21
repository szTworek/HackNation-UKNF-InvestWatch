import { ActionIcon, Anchor, Box, Button, Group, Indicator, Popover, ScrollArea, Stack, Text, Tooltip } from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { IconBell, IconCalendar } from '@tabler/icons-react';
import { Link } from 'react-router-dom';
import type { ConnectionState } from '../api/socket';
import { daysAgoIso, fmtRelative, todayIso } from '../lib/format';

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

// ---------------------------------------------------------------------------
// Dzwonek alertów
// ---------------------------------------------------------------------------

export interface AlertItem {
  key: string;
  findingId: string;
  title: string;
  message: string;
  at: string;
  read: boolean;
  priority: 'campaign' | 'high_risk';
}

interface BellProps {
  alerts: AlertItem[];
  unread: number;
  onOpen: () => void;
  onClear: () => void;
}

export function AlertBell({ alerts, unread, onOpen, onClear }: BellProps) {
  return (
    <Popover width={360} position="bottom-end" shadow="md" onOpen={onOpen} withinPortal>
      <Popover.Target>
        <Indicator label={unread > 99 ? '99+' : unread} size={16} color="red" disabled={unread === 0} offset={4}>
          <ActionIcon variant="subtle" color="gray" size="lg" aria-label={`Alerty, nieprzeczytane: ${unread}`}>
            <IconBell size={20} />
          </ActionIcon>
        </Indicator>
      </Popover.Target>
      <Popover.Dropdown p={0}>
        <Group justify="space-between" px="sm" py={8} style={{ borderBottom: '1px solid var(--iw-border)' }}>
          <Text size="sm" fw={600}>
            Alerty
          </Text>
          {alerts.length > 0 && (
            <Button variant="subtle" size="compact-xs" onClick={onClear}>
              Wyczyść
            </Button>
          )}
        </Group>
        {alerts.length === 0 ? (
          <Text size="sm" c="dimmed" p="sm">
            Brak alertów.
          </Text>
        ) : (
          <ScrollArea.Autosize mah={420}>
            <Stack gap={0}>
              {alerts.map((a) => (
                <Anchor
                  key={a.key}
                  component={Link}
                  to={`/findings/${a.findingId}`}
                  underline="never"
                  c="inherit"
                  px="sm"
                  py={8}
                  style={{
                    borderBottom: '1px solid var(--iw-border)',
                    boxShadow: a.priority === 'campaign' ? 'inset 3px 0 0 var(--mantine-color-red-7)' : undefined,
                    background: a.read ? undefined : '#ebf3fc',
                  }}
                >
                  <Group justify="space-between" wrap="nowrap" gap="xs">
                    <Text size="sm" fw={500} truncate>
                      {a.title}
                    </Text>
                    <Text size="xs" c="dimmed" style={{ flexShrink: 0 }}>
                      {fmtRelative(a.at)}
                    </Text>
                  </Group>
                  <Text size="xs" c="dimmed" lineClamp={2}>
                    {a.message}
                  </Text>
                </Anchor>
              ))}
            </Stack>
          </ScrollArea.Autosize>
        )}
      </Popover.Dropdown>
    </Popover>
  );
}
