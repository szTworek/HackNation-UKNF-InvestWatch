import { Box, Group, Stack, Text } from '@mantine/core';
import type { RiskLevel } from '../api/types';
import { fmtPct } from '../lib/format';
import { RISK_LABEL } from '../lib/labels';

const COLORS: Record<RiskLevel, string> = { LOW: '#8a939e', MEDIUM: '#d39e00', HIGH: '#e8590c', CRITICAL: '#c4314b' };

interface Props {
  score: number; // 0..1
  level: RiskLevel;
  /** progi poziomów z panelu kalibracji */
  medium: number;
  high: number;
  critical: number;
}

const R = 80;
const CX = 100;
const CY = 96;

/** punkt na łuku dla wartości 0..1 (od lewej do prawej) */
function point(v: number, r = R) {
  const a = Math.PI * (1 - v);
  return { x: CX + r * Math.cos(a), y: CY - r * Math.sin(a) };
}

function arc(from: number, to: number) {
  const a = point(from);
  const b = point(to);
  return `M ${a.x.toFixed(2)} ${a.y.toFixed(2)} A ${R} ${R} 0 0 1 ${b.x.toFixed(2)} ${b.y.toFixed(2)}`;
}

/** Półokrągły wskaźnik ryzyka: strefy wg progów, wskazówka na wyniku rekordu. */
export function RiskGauge({ score, level, medium, high, critical }: Props) {
  const zones: [number, number, RiskLevel][] = [
    [0, medium, 'LOW'],
    [medium, high, 'MEDIUM'],
    [high, critical, 'HIGH'],
    [critical, 1, 'CRITICAL'],
  ];
  const tip = point(Math.min(1, Math.max(0, score)), R - 14);
  return (
    <Group gap="lg" wrap="nowrap" align="center">
      <Box w={200} style={{ flexShrink: 0 }}>
        <svg viewBox="0 0 200 110" width="200" height="110" role="img" aria-label={`Ryzyko ${RISK_LABEL[level].toLowerCase()}, wynik ${fmtPct(score)}`}>
          {zones.map(([a, b, lv]) => (
            <path key={lv} d={arc(a, b)} stroke={COLORS[lv]} strokeWidth={16} fill="none" opacity={lv === level ? 1 : 0.28} />
          ))}
          <line x1={CX} y1={CY} x2={tip.x} y2={tip.y} stroke="#1f2933" strokeWidth={3} strokeLinecap="round" />
          <circle cx={CX} cy={CY} r={6} fill="#1f2933" />
        </svg>
      </Box>
      <Stack gap={0}>
        <Text size="xs" c="dimmed" fw={500}>
          Ocena ryzyka
        </Text>
        <Text fz={30} fw={700} c={COLORS[level]} lh={1.15}>
          {RISK_LABEL[level]}
        </Text>
        <Text size="sm" c="dimmed" ff="monospace">
          {fmtPct(score)}
        </Text>
      </Stack>
    </Group>
  );
}
