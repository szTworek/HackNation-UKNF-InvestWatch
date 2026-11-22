import { Badge, Button, Group, Table, Text } from '@mantine/core';
import { useState } from 'react';
import type { RuleDef, RuleResult } from '../api/types';
import { snippet } from '../lib/findings';
import { fmtProb } from '../lib/format';
import { RULE_STATUS_COLOR, RULE_STATUS_LABEL } from '../lib/labels';

interface Props {
  defs: RuleDef[];
  results: RuleResult[];
}

export function RulesChecklist({ defs, results }: Props) {
  const [showNa, setShowNa] = useState(false);
  const byId = new Map(results.map((r) => [r.ruleId, r]));
  const rows = defs.map((d) => ({ def: d, result: byId.get(d.id) }));
  const applicable = rows.filter((r) => r.result && r.result.status !== 'NOT_APPLICABLE');
  const naCount = rows.length - applicable.length;

  if (!applicable.length) {
    return (
      <Text size="sm" c="dimmed">
        Reguły dotyczą materiałów reklamowych (moduły 1 i 2) i ofert doradztwa (moduł 3). Ten materiał nie trafił do żadnego z nich.
      </Text>
    );
  }

  const visible = showNa ? rows : applicable;
  return (
    <>
      <Table verticalSpacing={6} fz="sm" layout="fixed">
        <Table.Thead>
          <Table.Tr>
            <Table.Th w={44}>Nr</Table.Th>
            <Table.Th>Reguła</Table.Th>
            <Table.Th w={190}>Wynik</Table.Th>
            <Table.Th w="34%">Dowód</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {visible.map(({ def, result }) => {
            const status = result?.status ?? 'NOT_APPLICABLE';
            const ev = result?.evidence[0];
            return (
              <Table.Tr key={def.id} bg={status === 'VIOLATION' ? 'var(--mantine-color-red-light)' : undefined}>
                <Table.Td c="dimmed">
                  {def.id.startsWith('M') ? '—' : def.id}
                </Table.Td>
                <Table.Td>
                  <Text size="sm" fw={500}>
                    {def.name}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {def.legalBasis}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Group gap={6}>
                    <Badge color={RULE_STATUS_COLOR[status]} variant={status === 'VIOLATION' ? 'filled' : 'light'} size="sm" tt="none">
                      {RULE_STATUS_LABEL[status]}
                    </Badge>
                    {status === 'VIOLATION' && result && (
                      <Text size="xs" c="dimmed">
                        {fmtProb(result.score)}
                      </Text>
                    )}
                  </Group>
                </Table.Td>
                <Table.Td>
                  {ev ? (
                    <Text size="xs" fs="italic">
                      „{snippet(ev.text, 110)}”
                    </Text>
                  ) : null}
                </Table.Td>
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
      {naCount > 0 && (
        <Button variant="subtle" size="xs" mt="xs" onClick={() => setShowNa((v) => !v)}>
          {showNa ? 'Ukryj reguły, które nie dotyczą' : `Pokaż reguły, które nie dotyczą (${naCount})`}
        </Button>
      )}
    </>
  );
}
