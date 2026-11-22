import { Group, Text } from '@mantine/core';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Legend,
  Line,
  LineChart,
  ReferenceDot,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { Timeseries, TimeseriesGroupBy } from '../api/types';
import type { PrPoint, SweepPoint } from '../lib/metrics';
import { fmtPct, fmtProb, fmtShortDate } from '../lib/format';
import { PLATFORM_LABEL, RISK_LABEL } from '../lib/labels';
import { CHART_COLORS as C, ChartBox } from './ChartBox';

const axisProps = {
  stroke: C.axis,
  tick: { fontSize: 11, fill: C.axis },
  tickLine: false,
  axisLine: { stroke: C.grayLight },
} as const;

// ---------------------------------------------------------------------------
// Trend incydentów
// ---------------------------------------------------------------------------

const SERIES: Record<TimeseriesGroupBy, Record<string, { label: string; color: string }>> = {
  module: {
    '1': { label: 'Finfluencerzy', color: C.blue },
    '2': { label: 'Informacja o ryzyku', color: C.teal },
    '3': { label: 'Shadow advisory', color: C.violet },
    scam: { label: 'Oszustwa', color: C.red },
  },
  platform: {
    facebook: { label: PLATFORM_LABEL.facebook, color: C.indigo },
    instagram: { label: PLATFORM_LABEL.instagram, color: C.pink },
    tiktok: { label: PLATFORM_LABEL.tiktok, color: C.dark },
    youtube: { label: PLATFORM_LABEL.youtube, color: C.red },
    x: { label: PLATFORM_LABEL.x, color: C.axis },
    web: { label: PLATFORM_LABEL.web, color: C.cyan },
    other: { label: PLATFORM_LABEL.other, color: C.grayLight },
  },
  riskLevel: {
    LOW: { label: RISK_LABEL.LOW, color: C.grayLight },
    MEDIUM: { label: RISK_LABEL.MEDIUM, color: C.yellow },
    HIGH: { label: RISK_LABEL.HIGH, color: C.orange },
    CRITICAL: { label: RISK_LABEL.CRITICAL, color: C.redDark },
  },
};

/** Liczba incydentów per dzień, słupki skumulowane wg grupowania. */
export function TrendChart({ data, height = 280 }: { data: Timeseries; height?: number }) {
  const series = SERIES[data.groupBy];
  const rows = data.points.map((p) => ({ date: p.date, ...p.counts }));
  const keys = data.keys.filter((k) => rows.some((r) => (r as Record<string, number | string>)[k]));
  return (
    <ChartBox height={height}>
      {(w, h) => (
        <BarChart width={w} height={h} data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid vertical={false} stroke={C.grid} />
          <XAxis dataKey="date" tickFormatter={fmtShortDate} minTickGap={16} {...axisProps} />
          <YAxis allowDecimals={false} {...axisProps} axisLine={false} />
          <Tooltip labelFormatter={(l) => fmtShortDate(String(l))} cursor={{ fill: 'rgba(15,108,189,0.06)' }} />
          <Legend iconType="square" iconSize={10} wrapperStyle={{ fontSize: 12 }} />
          {keys.map((k) => (
            <Bar
              key={k}
              dataKey={k}
              name={series[k]?.label ?? k}
              stackId="s"
              fill={series[k]?.color ?? C.gray}
              isAnimationActive={false}
              maxBarSize={28}
            />
          ))}
        </BarChart>
      )}
    </ChartBox>
  );
}

// ---------------------------------------------------------------------------
// Rozkład (poziome słupki z wartością na końcu)
// ---------------------------------------------------------------------------

export function DistributionBars({ data, color = C.blue }: { data: { label: string; value: number }[]; color?: string }) {
  const rows = data.filter((d) => d.value > 0).sort((a, b) => b.value - a.value);
  if (!rows.length) return <Text size="sm" c="dimmed">Brak danych w tym zakresie dat.</Text>;
  const height = rows.length * 30 + 8;
  return (
    <ChartBox height={height}>
      {(w, h) => (
        <BarChart width={w} height={h} data={rows} layout="vertical" margin={{ top: 0, right: 40, bottom: 0, left: 0 }}>
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="label" width={190} {...axisProps} axisLine={false} tick={{ fontSize: 12, fill: '#3d4752' }} />
          <Bar dataKey="value" fill={color} isAnimationActive={false} barSize={16} radius={[0, 2, 2, 0]}>
            <LabelList dataKey="value" position="right" style={{ fontSize: 12, fill: '#3d4752' }} />
          </Bar>
        </BarChart>
      )}
    </ChartBox>
  );
}

// ---------------------------------------------------------------------------
// Kalibracja
// ---------------------------------------------------------------------------

export function PrCurve({ curve, current, height = 240 }: { curve: PrPoint[]; current: { precision: number; recall: number }; height?: number }) {
  return (
    <ChartBox height={height}>
      {(w, h) => (
        <LineChart width={w} height={h} data={curve} margin={{ top: 8, right: 12, bottom: 18, left: -12 }}>
          <CartesianGrid stroke={C.grid} />
          <XAxis
            type="number"
            dataKey="recall"
            domain={[0, 1]}
            ticks={[0, 0.25, 0.5, 0.75, 1]}
            tickFormatter={(v: number) => fmtPct(v)}
            label={{ value: 'Pełność (recall)', position: 'insideBottom', offset: -10, fontSize: 11, fill: C.axis }}
            {...axisProps}
          />
          <YAxis
            type="number"
            domain={[0, 1]}
            ticks={[0, 0.25, 0.5, 0.75, 1]}
            tickFormatter={(v: number) => fmtPct(v)}
            {...axisProps}
          />
          <Tooltip
            formatter={(v) => fmtPct(Number(v))}
            labelFormatter={(l) => `Pełność ${fmtPct(Number(l))}`}
          />
          <Line type="stepAfter" dataKey="precision" name="Precyzja" stroke={C.blue} strokeWidth={2} dot={false} isAnimationActive={false} />
          <ReferenceDot x={current.recall} y={current.precision} r={6} fill={C.orange} stroke="#fff" strokeWidth={2} ifOverflow="visible" />
        </LineChart>
      )}
    </ChartBox>
  );
}

export function ThresholdCurve({
  sweep,
  threshold,
  precision,
  recall,
  height = 240,
}: {
  sweep: SweepPoint[];
  threshold: number;
  precision: number;
  recall: number;
  height?: number;
}) {
  return (
    <>
      <Group gap="md" mb={4}>
        <Text size="sm" fw={500} c={C.blue}>
          Precyzja {fmtPct(precision)}
        </Text>
        <Text size="sm" fw={500} c={C.orange}>
          Pełność {fmtPct(recall)}
        </Text>
      </Group>
      <ChartBox height={height}>
        {(w, h) => (
          <LineChart width={w} height={h} data={sweep} margin={{ top: 8, right: 12, bottom: 18, left: -12 }}>
            <CartesianGrid stroke={C.grid} />
            <XAxis
              type="number"
              dataKey="threshold"
              domain={[0, 1]}
              ticks={[0, 0.25, 0.5, 0.75, 1]}
              tickFormatter={(v: number) => fmtProb(v)}
              label={{ value: 'Próg', position: 'insideBottom', offset: -10, fontSize: 11, fill: C.axis }}
              {...axisProps}
            />
            <YAxis type="number" domain={[0, 1]} ticks={[0, 0.5, 1]} tickFormatter={(v: number) => fmtPct(v)} {...axisProps} />
            <Tooltip formatter={(v) => fmtPct(Number(v))} labelFormatter={(l) => `Próg ${fmtProb(Number(l))}`} />
            <Line type="monotone" dataKey="precision" name="Precyzja" stroke={C.blue} strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="recall" name="Pełność" stroke={C.orange} strokeWidth={2} dot={false} isAnimationActive={false} />
            <ReferenceLine x={threshold} stroke={C.dark} strokeDasharray="4 3" ifOverflow="visible" />
          </LineChart>
        )}
      </ChartBox>
    </>
  );
}

// ---------------------------------------------------------------------------
// Kampanie
// ---------------------------------------------------------------------------

/** Liczba nowych elementów kampanii per dzień. */
export function CampaignTimeline({ dates, height = 160 }: { dates: string[]; height?: number }) {
  const counts = new Map<string, number>();
  for (const iso of dates) {
    const d = iso.slice(0, 10);
    counts.set(d, (counts.get(d) ?? 0) + 1);
  }
  const keys = [...counts.keys()].sort();
  if (!keys.length) return null;
  const rows: { date: string; n: number }[] = [];
  const start = new Date(`${keys[0]}T00:00:00`);
  const end = new Date(`${keys[keys.length - 1]}T00:00:00`);
  for (const d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    const k = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    rows.push({ date: k, n: counts.get(k) ?? 0 });
  }
  return (
    <ChartBox height={height}>
      {(w, h) => (
        <BarChart width={w} height={h} data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -24 }}>
          <CartesianGrid vertical={false} stroke={C.grid} />
          <XAxis dataKey="date" tickFormatter={fmtShortDate} minTickGap={12} {...axisProps} />
          <YAxis allowDecimals={false} {...axisProps} axisLine={false} />
          <Tooltip labelFormatter={(l) => fmtShortDate(String(l))} formatter={(v) => [String(v), 'Nowe elementy']} />
          <Bar dataKey="n" fill={C.red} isAnimationActive={false} maxBarSize={20} />
        </BarChart>
      )}
    </ChartBox>
  );
}

/** Prawdopodobieństwo syntetycznego głosu per segment nagrania. */
export function VoiceChart({
  segments,
  activeT,
  height = 140,
}: {
  segments: { startS: number; endS: number; score: number }[];
  activeT: number | null;
  height?: number;
}) {
  const rows = segments.map((s) => ({ t: s.startS, score: s.score }));
  return (
    <ChartBox height={height}>
      {(w, h) => (
        <AreaChart width={w} height={h} data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
          <CartesianGrid vertical={false} stroke={C.grid} />
          <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tickFormatter={(v: number) => `${v} s`} {...axisProps} />
          <YAxis domain={[0, 1]} ticks={[0, 0.5, 1]} tickFormatter={(v: number) => fmtPct(v)} {...axisProps} axisLine={false} />
          <Tooltip formatter={(v) => [fmtPct(Number(v)), 'Syntetyczny głos']} labelFormatter={(l) => `${l} s`} />
          <Area type="stepAfter" dataKey="score" stroke={C.orange} fill={C.orange} fillOpacity={0.25} isAnimationActive={false} />
          {activeT !== null && <ReferenceLine x={activeT} stroke={C.dark} strokeDasharray="4 3" />}
        </AreaChart>
      )}
    </ChartBox>
  );
}
