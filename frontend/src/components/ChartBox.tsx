import { Box } from '@mantine/core';
import { useElementSize } from '@mantine/hooks';
import type { ReactNode } from 'react';

/** Mierzy szerokość kontenera i renderuje wykres dopiero, gdy jest > 0 (bez ostrzeżeń Recharts o rozmiarze 0). */
export function ChartBox({ height, children }: { height: number; children: (width: number, height: number) => ReactNode }) {
  const { ref, width } = useElementSize();
  return (
    // wykres pozycjonowany absolutnie, żeby jego szerokość nie wpływała na pomiar kontenera (brak pętli resize)
    <Box ref={ref} h={height} w="100%" pos="relative" style={{ minWidth: 0, overflow: 'hidden' }}>
      <Box pos="absolute" top={0} left={0}>
        {width > 0 ? children(Math.floor(width), height) : null}
      </Box>
    </Box>
  );
}

export const CHART_COLORS = {
  blue: '#113b6f',
  teal: '#1e6ac8',
  violet: '#4b5f7c',
  red: '#c00417',
  redDark: '#c00417',
  orange: '#c2500a',
  yellow: '#b98300',
  gray: '#adb5bd',
  grayLight: '#d0d5dc',
  grid: '#e5e7eb',
  axis: '#5f6673',
  indigo: '#3b5998',
  pink: '#e64980',
  dark: '#2b303b',
  cyan: '#15aabf',
  green: '#40c057',
};
