import { Anchor, Group, Table, Text } from '@mantine/core';
import { Bar, BarChart, CartesianGrid, Legend, Tooltip, XAxis, YAxis } from 'recharts';
import { Link } from 'react-router-dom';
import type { EntityFinding, EntityModule, EntityOverview } from '../api/entityTypes';
import { fmtShortDate } from '../lib/format';
import { ENTITY_MODULES, ENTITY_MODULE_COLOR, ENTITY_MODULE_LABEL, ENTITY_MODULE_SHORT } from '../lib/labels';
import { CHART_COLORS as C, ChartBox } from './ChartBox';

export type DayRow = { date: string } & Record<EntityModule, number>;

/** Wyniki per dzień z ostatnich `days` dni (koniec okna = najnowszy wynik). */
export function daysFromFindings(findings: EntityFinding[], days = 30): DayRow[] {
  const end = findings.reduce((m, f) => (f.createdAt > m ? f.createdAt : m), '').slice(0, 10) || new Date().toISOString().slice(0, 10);
  const base = new Date(`${end}T00:00:00Z`).getTime();
  const out: DayRow[] = [];
  for (let i = days - 1; i >= 0; i--) out.push({ date: new Date(base - i * 86_400_000).toISOString().slice(0, 10), M1: 0, M2: 0, M3: 0 });
  const idx = new Map(out.map((r, i) => [r.date, i]));
  for (const f of findings) {
    const i = idx.get(f.createdAt.slice(0, 10));
    if (i !== undefined) out[i][f.module] += 1;
  }
  return out;
}

const axisProps = {
  stroke: C.axis,
  tick: { fontSize: 11, fill: C.axis },
  tickLine: false,
  axisLine: { stroke: C.grayLight },
} as const;

/** Wyniki per dzień, słupki skumulowane wg modułu. */
export function FindingsByDayChart({ data, height = 260 }: { data: DayRow[]; height?: number }) {
  return (
    <ChartBox height={height}>
      {(w, h) => (
        <BarChart width={w} height={h} data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid vertical={false} stroke={C.grid} />
          <XAxis dataKey="date" tickFormatter={fmtShortDate} minTickGap={16} {...axisProps} />
          <YAxis allowDecimals={false} {...axisProps} axisLine={false} />
          <Tooltip labelFormatter={(l) => fmtShortDate(String(l))} cursor={{ fill: 'rgba(15,108,189,0.06)' }} />
          <Legend iconType="square" iconSize={10} wrapperStyle={{ fontSize: 12 }} />
          {ENTITY_MODULES.map((m) => (
            <Bar key={m} dataKey={m} name={ENTITY_MODULE_LABEL[m]} stackId="s" fill={ENTITY_MODULE_COLOR[m]} isAnimationActive={false} maxBarSize={28} />
          ))}
        </BarChart>
      )}
    </ChartBox>
  );
}

function heat(v: number): { background: string; color?: string } {
  if (!v) return { background: 'var(--iw-soft-2)' };
  const a = 0.12 + v * 0.85;
  return { background: `rgba(17, 59, 111, ${a.toFixed(2)})`, color: a > 0.5 ? '#fff' : undefined };
}

/** Podmiot × moduł: średni wynik klasyfikatora (0–100). */
export function EntityHeatmap({ rows }: { rows: EntityOverview['heatmap'] }) {
  return (
    <>
      <Table verticalSpacing={4} withRowBorders={false} style={{ borderCollapse: 'separate', borderSpacing: 4 }}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th />
            {ENTITY_MODULES.map((m) => (
              <Table.Th key={m} ta="center" title={ENTITY_MODULE_LABEL[m]} fz="xs" style={{ whiteSpace: 'normal', lineHeight: 1.2, width: '22%' }}>
                {ENTITY_MODULE_SHORT[m]}
              </Table.Th>
            ))}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((r) => (
            <Table.Tr key={r.entityId}>
              <Table.Td>
                <Anchor component={Link} to={`/entities/${r.entityId}`} size="sm" fw={500}>
                  {r.name}
                </Anchor>
              </Table.Td>
              {ENTITY_MODULES.map((m) => (
                <Table.Td key={m} ta="center" fw={600} className="iw-kpi-value" style={{ ...heat(r[m]), height: 40 }} title={`${r.name}, ${ENTITY_MODULE_LABEL[m]}: ${r[m]}`}>
                  {r[m] ? Math.round(r[m] * 100) : '—'}
                </Table.Td>
              ))}
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      <Group gap={8} mt={6}>
        <Text size="xs" c="dimmed">
          Średni wynik klasyfikatora
        </Text>
        <span style={{ width: 96, height: 8, background: 'linear-gradient(90deg, rgba(17,59,111,.12), rgba(17,59,111,.97))' }} />
      </Group>
    </>
  );
}

/** Poziome paski z etykietą nad paskiem (długie nazwy reguł). */
export function LabeledBars({ rows }: { rows: { key: string; label: string; value: number; color?: string }[] }) {
  if (!rows.length) return <Text size="sm" c="dimmed">Brak danych.</Text>;
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div>
      {rows.map((r) => (
        <div key={r.key} style={{ marginBottom: 10 }}>
          <Group justify="space-between" gap={8} wrap="nowrap" mb={3}>
            <Text size="sm" truncate>
              {r.label}
            </Text>
            <Text size="sm" c="dimmed" className="iw-kpi-value">
              {r.value}
            </Text>
          </Group>
          <div style={{ height: 8, background: 'var(--iw-soft-2)' }}>
            <div style={{ height: 8, width: `${(r.value / max) * 100}%`, background: r.color ?? C.blue }} />
          </div>
        </div>
      ))}
    </div>
  );
}
