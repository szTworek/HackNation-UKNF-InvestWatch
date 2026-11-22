import { Box, Group, Text, Tooltip } from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { IconCalendar } from '@tabler/icons-react';
import type { ConnectionState } from '../api/socket';
import { daysAgoIso, todayIso } from '../lib/format';

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
