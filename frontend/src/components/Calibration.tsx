import { Box, Group, NumberInput, Slider, Text, UnstyledButton } from '@mantine/core';
import type { Confusion } from '../lib/metrics';
import { fmtInt, fmtProb } from '../lib/format';

/** Macierz pomyłek: wiersze = etykieta gold, kolumny = decyzja modelu przy progu. */
export function ConfusionMatrix({ c }: { c: Confusion }) {
  const cell = (label: string, value: number, bg: string) => (
    <Box p="sm" bg={bg} style={{ borderRadius: 4 }}>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text fz={22} fw={600}>
        {fmtInt(value)}
      </Text>
    </Box>
  );
  return (
    <Box>
      <Box style={{ display: 'grid', gridTemplateColumns: '110px 1fr 1fr', gap: 6 }}>
        <span />
        <Text size="xs" c="dimmed" ta="center">
          Model: ≥ próg
        </Text>
        <Text size="xs" c="dimmed" ta="center">
          Model: &lt; próg
        </Text>
        <Text size="xs" c="dimmed" style={{ alignSelf: 'center' }}>
          Gold: pozytyw
        </Text>
        {cell('Trafienia (TP)', c.tp, 'var(--mantine-color-green-light)')}
        {cell('Pominięte (FN)', c.fn, 'var(--mantine-color-red-light)')}
        <Text size="xs" c="dimmed" style={{ alignSelf: 'center' }}>
          Gold: negatyw
        </Text>
        {cell('Fałszywe alarmy (FP)', c.fp, 'var(--mantine-color-orange-light)')}
        {cell('Poprawnie odrzucone (TN)', c.tn, '#f4f5f7')}
      </Box>
    </Box>
  );
}

interface SliderProps {
  id: string;
  label: string;
  value: number;
  saved: number;
  selected: boolean;
  onChange: (v: number) => void;
  onSelect: () => void;
}

export function ThresholdSlider({ id, label, value, saved, selected, onChange, onSelect }: SliderProps) {
  const changed = Math.abs(value - saved) > 1e-9;
  return (
    <UnstyledButton
      component="div"
      onClick={onSelect}
      onFocusCapture={onSelect}
      px="xs"
      py={6}
      w="100%"
      style={{
        borderRadius: 4,
        background: selected ? '#ebf3fc' : undefined,
        borderLeft: `3px solid ${selected ? 'var(--iw-primary)' : 'transparent'}`,
      }}
    >
      <Group wrap="nowrap" gap="sm">
        <Box w={210} style={{ flexShrink: 0 }}>
          <Text component="label" htmlFor={id} size="sm" fw={selected ? 500 : 400} display="block" truncate>
            {label}
          </Text>
          {changed && (
            <Text size="xs" c="orange.8">
              zapisany: {fmtProb(saved)}
            </Text>
          )}
        </Box>
        <Slider
          flex={1}
          min={0}
          max={1}
          step={0.01}
          value={value}
          onChange={onChange}
          label={fmtProb}
          aria-label={label}
          color={changed ? 'orange' : 'office'}
          size="sm"
        />
        <NumberInput
          id={id}
          w={72}
          size="xs"
          min={0}
          max={1}
          step={0.01}
          decimalScale={2}
          decimalSeparator=","
          hideControls
          value={value}
          onChange={(v) => {
            const n = typeof v === 'number' ? v : Number(String(v).replace(',', '.'));
            if (Number.isFinite(n) && n >= 0 && n <= 1) onChange(Math.round(n * 100) / 100);
          }}
        />
      </Group>
    </UnstyledButton>
  );
}
