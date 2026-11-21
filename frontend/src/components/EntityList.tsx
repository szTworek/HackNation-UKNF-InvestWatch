import { Stack, Table, Text } from '@mantine/core';
import type { Entity } from '../api/types';
import { fmtProb } from '../lib/format';
import { ENTITY_ROLE_LABEL } from '../lib/labels';
import { RegisterBadge } from './Badges';

export function EntityList({ entities }: { entities: Entity[] }) {
  if (!entities.length) {
    return (
      <Text size="sm" c="dimmed">
        Model nie rozpoznał podmiotów.
      </Text>
    );
  }
  return (
    <Table verticalSpacing={6} fz="sm">
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Podmiot</Table.Th>
          <Table.Th>Rola</Table.Th>
          <Table.Th>Rejestr KNF</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {entities.map((e) => (
          <Table.Tr key={`${e.role}-${e.name}`}>
            <Table.Td>
              <Stack gap={0}>
                <Text size="sm" fw={500}>
                  {e.name}
                </Text>
                {e.knfRegister.matchedName && e.knfRegister.matchedName !== e.name && (
                  <Text size="xs" c="dimmed">
                    dopasowano: {e.knfRegister.matchedName}
                  </Text>
                )}
              </Stack>
            </Table.Td>
            <Table.Td>{ENTITY_ROLE_LABEL[e.role]}</Table.Td>
            <Table.Td>
              <Stack gap={2} align="flex-start">
                <RegisterBadge status={e.knfRegister.status} />
                {e.knfRegister.score !== undefined && (
                  <Text size="xs" c="dimmed">
                    dopasowanie {fmtProb(e.knfRegister.score)}
                  </Text>
                )}
              </Stack>
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}
