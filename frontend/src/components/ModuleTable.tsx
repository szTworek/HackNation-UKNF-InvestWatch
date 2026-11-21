import { ActionIcon, Anchor, Badge, Checkbox, Group, Menu, Table, Text, Tooltip, UnstyledButton } from '@mantine/core';
import { IconArrowDown, IconArrowUp, IconDots } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import type { FindingSummary, RuleDef, Status } from '../api/types';
import { fmtDateTime, fmtPct } from '../lib/format';
import { FLAG_LABEL, INSTRUMENT_LABEL, MODULE_SHORT, RISK_LABEL } from '../lib/labels';
import { RegisterBadge, StatusBadge } from './Badges';
import { StatusMenuItems } from './FindingsTable';
import { PlatformIcon } from './PlatformIcon';
import { RISK_HEX } from './Terminal';

export type ModuleKey = '1' | '2' | '3' | 'scam' | 'all';

interface Column {
  key: string;
  title: string;
  w?: number;
  sort?: string;
  render: (f: FindingSummary) => ReactNode;
}

const muted = (text: ReactNode) => (
  <Text size="sm" c="dimmed">
    {text}
  </Text>
);

function Content({ f }: { f: FindingSummary }) {
  return (
    <div style={{ minWidth: 0 }}>
      {f.title && (
        <Text size="sm" fw={500} lineClamp={1}>
          {f.title}
        </Text>
      )}
      <Text size="sm" c={f.title ? 'dimmed' : undefined} lineClamp={2}>
        {f.snippet}
      </Text>
    </div>
  );
}

function Risk({ f, scam }: { f: FindingSummary; scam: boolean }) {
  return (
    <Group gap={6} wrap="nowrap">
      <span style={{ width: 8, height: 8, borderRadius: 2, background: scam ? RISK_HEX.CRITICAL : RISK_HEX[f.riskLevel], flexShrink: 0 }} aria-hidden />
      <Text size="sm" fw={500} c={scam ? RISK_HEX.CRITICAL : undefined}>
        {scam ? 'Podejrzenie oszustwa' : RISK_LABEL[f.riskLevel]}
      </Text>
    </Group>
  );
}

function columnsFor(key: ModuleKey, rules: Map<string, RuleDef>): Column[] {
  const source: Column = {
    key: 'source',
    title: 'Źródło',
    w: 170,
    render: (f) => (
      <Group gap={6} wrap="nowrap">
        <PlatformIcon platform={f.platform} size={16} />
        <Text size="sm" truncate maw={140}>
          {f.author.handle}
        </Text>
      </Group>
    ),
  };
  const content: Column = { key: 'content', title: key === '3' ? 'Treść oferty' : 'Treść', render: (f) => <Content f={f} /> };
  const firm: Column = {
    key: 'firm',
    title: 'Firma inwestycyjna',
    w: 200,
    render: (f) =>
      f.firm ? (
        <div>
          <Text size="sm" fw={500} lineClamp={1}>
            {f.firm.name}
          </Text>
          <RegisterBadge status={f.firm.register} size="xs" />
        </div>
      ) : (
        muted('nie rozpoznano')
      ),
  };
  switch (key) {
    case '1':
      return [
        firm,
        { key: 'adv', title: 'Reklamujący', w: 170, render: (f) => <Text size="sm">{f.advertiser ?? f.author.handle}</Text> },
        content,
        {
          key: 'ad',
          title: 'Oznaczenie reklamy',
          w: 130,
          render: (f) => (
            <Badge size="sm" variant="light" color={f.adDisclosed ? 'green' : 'red'} tt="none">
              {f.adDisclosed ? 'Oznaczona' : 'Brak oznaczenia'}
            </Badge>
          ),
        },
        source,
      ];
    case '2':
      return [
        firm,
        content,
        {
          key: 'viol',
          title: 'Naruszone reguły',
          w: 220,
          render: (f) =>
            f.violations.length ? (
              <Tooltip multiline w={300} withArrow label={f.violations.map((id) => rules.get(id)?.name ?? id).join(', ')}>
                <div>
                  <Text size="sm" fw={600} c="red.8">
                    {f.violations.length} {f.violations.length === 1 ? 'naruszenie' : f.violations.length < 5 ? 'naruszenia' : 'naruszeń'}
                  </Text>
                  <Text size="xs" c="dimmed" lineClamp={1}>
                    {f.violations.slice(0, 2).map((id) => rules.get(id)?.name ?? id).join(', ')}
                  </Text>
                </div>
              </Tooltip>
            ) : (
              muted('brak')
            ),
        },
        source,
      ];
    case '3':
      return [
        {
          key: 'advisor',
          title: 'Podmiot',
          w: 220,
          render: (f) =>
            f.advisor ? (
              <div>
                <Text size="sm" fw={500} lineClamp={1}>
                  {f.advisor.name}
                </Text>
                <RegisterBadge status={f.advisor.register} size="xs" />
              </div>
            ) : (
              <Text size="sm">{f.author.displayName ?? f.author.handle}</Text>
            ),
        },
        content,
        {
          key: 'instr',
          title: 'Instrumenty',
          w: 170,
          render: (f) => (f.instruments.length ? <Text size="xs">{f.instruments.map((i) => INSTRUMENT_LABEL[i]).join(', ')}</Text> : muted('—')),
        },
        source,
      ];
    case 'scam':
      return [
        { key: 'brand', title: 'Podszywana marka', w: 160, render: (f) => (f.brand ? <Text size="sm" fw={500}>{f.brand}</Text> : muted('—')) },
        content,
        {
          key: 'domain',
          title: 'Domena i kontakt',
          w: 210,
          render: (f) => (
            <div>
              <Text size="sm" truncate maw={200}>
                {f.domains[0] ?? '—'}
              </Text>
              {f.contacts[0] && (
                <Text size="xs" c="dimmed" truncate maw={200}>
                  {f.contacts[0]}
                </Text>
              )}
            </div>
          ),
        },
        {
          key: 'campaign',
          title: 'Kampania',
          w: 90,
          render: (f) =>
            f.campaignId ? (
              <Anchor component={Link} to={`/campaigns/${f.campaignId}`} size="sm" onClick={(e) => e.stopPropagation()}>
                {f.campaignId}
              </Anchor>
            ) : (
              muted('—')
            ),
        },
        { key: 'p', title: 'Pewność', w: 80, sort: 'scam', render: (f) => <Text size="sm" fw={600} c={RISK_HEX.CRITICAL}>{fmtPct(f.scamP)}</Text> },
        source,
      ];
    default:
      return [
        source,
        content,
        {
          key: 'mods',
          title: 'Moduł',
          w: 80,
          render: (f) => <Text size="sm">{f.modules.map((m) => MODULE_SHORT[m]).join(', ') || '—'}</Text>,
        },
        {
          key: 'flags',
          title: 'Wykryto',
          w: 200,
          render: (f) => <Text size="xs" lineClamp={2}>{f.topFlags.map((t) => FLAG_LABEL[t.flag]).join(', ') || '—'}</Text>,
        },
      ];
  }
}

interface Props {
  moduleKey: ModuleKey;
  items: FindingSummary[];
  rules: RuleDef[];
  scamThreshold: number;
  selected: ReadonlySet<string>;
  freshIds: ReadonlySet<string>;
  sort: string;
  onSort: (s: string) => void;
  onToggle: (id: string) => void;
  onToggleAll: (checked: boolean) => void;
  onOpen: (id: string) => void;
  onStatus: (id: string, s: Status) => void;
}

export function ModuleTable(p: Props) {
  const ruleMap = new Map(p.rules.map((r) => [r.id, r]));
  const cols = columnsFor(p.moduleKey, ruleMap);
  const allChecked = p.items.length > 0 && p.items.every((f) => p.selected.has(f.id));
  const someChecked = p.items.some((f) => p.selected.has(f.id));
  const [sf, sd] = p.sort.split(':');

  const sortHead = (title: string, field: string, w?: number) => {
    const active = sf === field;
    const Icon = sd === 'asc' ? IconArrowUp : IconArrowDown;
    return (
      <Table.Th key={field} w={w} aria-sort={active ? (sd === 'asc' ? 'ascending' : 'descending') : undefined}>
        <UnstyledButton onClick={() => p.onSort(active && sd === 'desc' ? `${field}:asc` : `${field}:desc`)} style={{ font: 'inherit', color: active ? 'var(--iw-primary)' : 'inherit' }}>
          <Group gap={4} wrap="nowrap">
            {title}
            {active && <Icon size={12} />}
          </Group>
        </UnstyledButton>
      </Table.Th>
    );
  };

  return (
    <Table.ScrollContainer minWidth={1000}>
      <Table highlightOnHover verticalSpacing={10} horizontalSpacing="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th w={36}>
              <Checkbox size="xs" aria-label="Zaznacz wszystkie na stronie" checked={allChecked} indeterminate={someChecked && !allChecked} onChange={(e) => p.onToggleAll(e.currentTarget.checked)} />
            </Table.Th>
            {sortHead('Wykryto', 'fetchedAt', 120)}
            {cols.map((c) => (c.sort ? sortHead(c.title, c.sort, c.w) : <Table.Th key={c.key} w={c.w}>{c.title}</Table.Th>))}
            {sortHead('Ryzyko', 'riskScore', 170)}
            <Table.Th w={110}>Status</Table.Th>
            <Table.Th w={40} aria-label="Akcje" />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {p.items.map((f) => {
            const scam = f.scamP >= p.scamThreshold;
            const cls = [scam ? 'iw-row-scam' : '', p.freshIds.has(f.id) ? 'iw-row-new' : ''].filter(Boolean).join(' ');
            return (
              <Table.Tr key={f.id} className={cls || undefined} onClick={() => p.onOpen(f.id)} style={{ cursor: 'pointer' }} bg={p.selected.has(f.id) ? '#ebf3fc' : undefined}>
                <Table.Td onClick={(e) => e.stopPropagation()}>
                  <Checkbox size="xs" aria-label={`Zaznacz ${f.id}`} checked={p.selected.has(f.id)} onChange={() => p.onToggle(f.id)} />
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{fmtDateTime(f.fetchedAt)}</Text>
                </Table.Td>
                {cols.map((c) => (
                  <Table.Td key={c.key}>{c.render(f)}</Table.Td>
                ))}
                <Table.Td>
                  <Risk f={f} scam={scam} />
                </Table.Td>
                <Table.Td>
                  <StatusBadge status={f.status} size="sm" />
                </Table.Td>
                <Table.Td onClick={(e) => e.stopPropagation()}>
                  <Menu position="bottom-end" withinPortal>
                    <Menu.Target>
                      <ActionIcon variant="subtle" color="gray" aria-label={`Zmień status ${f.id}`}>
                        <IconDots size={16} />
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
