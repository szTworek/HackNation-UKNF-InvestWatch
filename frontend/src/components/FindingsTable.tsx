import { ActionIcon, Badge, Checkbox, Group, Menu, Table, Text, UnstyledButton } from '@mantine/core';
import { IconArrowDown, IconArrowUp, IconDots } from '@tabler/icons-react';
import { useEffect, useRef, type ReactNode } from 'react';
import type { FindingSummary, Status } from '../api/types';
import { fmtDateTime, fmtTime } from '../lib/format';
import { FLAG_LABEL, MODULE_SHORT, RISK_LABEL, STATUSES, STATUS_LABEL } from '../lib/labels';
import { StatusBadge } from './Badges';
import { PlatformIcon } from './PlatformIcon';
import { Meter, RISK_HEX } from './Terminal';

export function StatusMenuItems({ current, onSelect }: { current?: Status; onSelect: (s: Status) => void }) {
  return (
    <>
      {STATUSES.filter((s) => s !== current).map((s) => (
        <Menu.Item key={s} onClick={() => onSelect(s)}>
          {STATUS_LABEL[s]}
        </Menu.Item>
      ))}
    </>
  );
}

function SortTh({ field, sort, onSort, children, w }: { field: string; sort: string; onSort: (s: string) => void; children: ReactNode; w?: number }) {
  const [f, dir] = sort.split(':');
  const active = f === field;
  const next = active && dir === 'desc' ? `${field}:asc` : `${field}:desc`;
  const Icon = dir === 'asc' ? IconArrowUp : IconArrowDown;
  return (
    <Table.Th w={w} aria-sort={active ? (dir === 'asc' ? 'ascending' : 'descending') : undefined}>
      <UnstyledButton onClick={() => onSort(next)} style={{ font: 'inherit', color: active ? 'var(--iw-primary)' : 'inherit' }}>
        <Group gap={4} wrap="nowrap">
          {children}
          {active && <Icon size={12} />}
        </Group>
      </UnstyledButton>
    </Table.Th>
  );
}

/** Ryzyko jako pasek + etykieta; oszustwo zawsze na czerwono. */
export function RiskCell({ f, scam }: { f: FindingSummary; scam: boolean }) {
  const color = scam ? RISK_HEX.CRITICAL : RISK_HEX[f.riskLevel];
  return (
    <div>
      <Text size="xs" fw={600} c={color} mb={3}>
        {scam ? 'Podejrzenie oszustwa' : RISK_LABEL[f.riskLevel]}
      </Text>
      <Meter value={scam ? f.scamP : f.riskScore} color={color} h={4} />
    </div>
  );
}

interface Props {
  items: FindingSummary[];
  scamThreshold: number;
  selected: ReadonlySet<string>;
  activeId: string | null;
  freshIds: ReadonlySet<string>;
  sort: string;
  onSort: (sort: string) => void;
  onToggle: (id: string) => void;
  onToggleAll: (checked: boolean) => void;
  onActivate: (id: string) => void;
  onOpen: (id: string) => void;
  onStatus: (id: string, status: Status) => void;
}

/** Kolejka rekordów: klik zaznacza (podgląd obok), dwuklik lub Enter otwiera akta. */
export function FindingsTable(p: Props) {
  const { items, scamThreshold, selected, activeId, freshIds, sort } = p;
  const allChecked = items.length > 0 && items.every((f) => selected.has(f.id));
  const someChecked = items.some((f) => selected.has(f.id));
  const activeRef = useRef<HTMLTableRowElement>(null);
  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: 'nearest' });
  }, [activeId]);

  return (
    <Table.ScrollContainer minWidth={760}>
      <Table highlightOnHover verticalSpacing={7} horizontalSpacing="sm" stickyHeader>
        <Table.Thead>
          <Table.Tr>
            <Table.Th w={34}>
              <Checkbox
                size="xs"
                aria-label="Zaznacz wszystkie na stronie"
                checked={allChecked}
                indeterminate={someChecked && !allChecked}
                onChange={(e) => p.onToggleAll(e.currentTarget.checked)}
              />
            </Table.Th>
            <SortTh field="fetchedAt" sort={sort} onSort={p.onSort} w={92}>
              Czas
            </SortTh>
            <Table.Th w={150}>Źródło</Table.Th>
            <Table.Th>Treść</Table.Th>
            <Table.Th w={56}>Mod.</Table.Th>
            <SortTh field="riskScore" sort={sort} onSort={p.onSort} w={110}>
              Ryzyko
            </SortTh>
            <Table.Th w={104}>Status</Table.Th>
            <Table.Th w={34} aria-label="Akcje" />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {items.map((f) => {
            const scam = f.scamP >= scamThreshold;
            const active = f.id === activeId;
            const cls = [active ? 'iw-row-selected' : '', scam && !active ? 'iw-row-scam' : '', freshIds.has(f.id) ? 'iw-row-new' : '']
              .filter(Boolean)
              .join(' ');
            return (
              <Table.Tr
                key={f.id}
                ref={active ? activeRef : undefined}
                className={cls}
                onClick={() => p.onActivate(f.id)}
                onDoubleClick={() => p.onOpen(f.id)}
                style={{ cursor: 'pointer' }}
                aria-selected={active}
              >
                <Table.Td onClick={(e) => e.stopPropagation()}>
                  <Checkbox size="xs" aria-label={`Zaznacz ${f.id}`} checked={selected.has(f.id)} onChange={() => p.onToggle(f.id)} />
                </Table.Td>
                <Table.Td>
                  <Text size="xs" ff="monospace" title={fmtDateTime(f.fetchedAt)}>
                    {fmtTime(f.fetchedAt)}
                  </Text>
                  <Text size="xs" ff="monospace" c="dimmed">
                    {fmtDateTime(f.fetchedAt).slice(0, 5)}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Group gap={6} wrap="nowrap">
                    <PlatformIcon platform={f.platform} size={15} color="var(--mantine-color-gray-7)" />
                    <Text size="sm" truncate maw={118}>
                      {f.author.handle}
                    </Text>
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" lineClamp={1} fw={f.title ? 500 : 400}>
                    {f.title ?? f.snippet}
                  </Text>
                  <Group gap={4} mt={2} wrap="nowrap">
                    {f.topFlags.slice(0, 2).map((t) => (
                      <Badge key={t.flag} size="xs" variant="outline" color="gray" radius="xs" tt="none">
                        {FLAG_LABEL[t.flag]}
                      </Badge>
                    ))}
                    {f.title && (
                      <Text size="xs" c="dimmed" lineClamp={1}>
                        {f.snippet}
                      </Text>
                    )}
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Text size="xs" ff="monospace" c="dimmed">
                    {f.modules.map((m) => MODULE_SHORT[m]).join(' ') || '—'}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <RiskCell f={f} scam={scam} />
                </Table.Td>
                <Table.Td>
                  <StatusBadge status={f.status} size="xs" />
                </Table.Td>
                <Table.Td onClick={(e) => e.stopPropagation()}>
                  <Menu position="bottom-end" withinPortal>
                    <Menu.Target>
                      <ActionIcon variant="subtle" color="gray" size="sm" aria-label={`Zmień status ${f.id}`}>
                        <IconDots size={14} />
                      </ActionIcon>
                    </Menu.Target>
                    <Menu.Dropdown>
                      <Menu.Label>Zmień status</Menu.Label>
                      <StatusMenuItems current={f.status} onSelect={(s) => p.onStatus(f.id, s)} />
                    </Menu.Dropdown>
                  </Menu>
                </Table.Td>
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

/** Zwarta lista rekordów (kampania, wskaźnik). */
export function FindingList({ items, scamThreshold, onOpen }: { items: FindingSummary[]; scamThreshold: number; onOpen: (id: string) => void }) {
  if (!items.length) return <Text size="sm" c="dimmed">Brak rekordów.</Text>;
  return (
    <Table.ScrollContainer minWidth={560}>
      <Table highlightOnHover verticalSpacing={6}>
        <Table.Tbody>
          {items.map((f) => {
            const scam = f.scamP >= scamThreshold;
            return (
              <Table.Tr key={f.id} onClick={() => onOpen(f.id)} style={{ cursor: 'pointer' }} className={scam ? 'iw-row-scam' : undefined}>
                <Table.Td w={120}>
                  <Text size="xs" ff="monospace">
                    {fmtDateTime(f.fetchedAt)}
                  </Text>
                </Table.Td>
                <Table.Td w={150}>
                  <Group gap={6} wrap="nowrap">
                    <PlatformIcon platform={f.platform} size={15} color="var(--mantine-color-gray-7)" />
                    <Text size="sm" truncate maw={120}>
                      {f.author.handle}
                    </Text>
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" lineClamp={1}>
                    {f.snippet}
                  </Text>
                </Table.Td>
                <Table.Td w={110}>
                  <RiskCell f={f} scam={scam} />
                </Table.Td>
                <Table.Td w={104}>
                  <StatusBadge status={f.status} size="xs" />
                </Table.Td>
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
