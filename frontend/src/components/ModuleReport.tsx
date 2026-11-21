import { Badge, Group, Paper, SimpleGrid, Stack, Text } from '@mantine/core';
import type { Finding, ModuleId, RuleDef } from '../api/types';
import { MODULE_COLOR } from '../app/theme';
import { flagThreshold, type ThresholdValues } from '../lib/findings';
import { INSTRUMENT_LABEL, MODULE_LABEL } from '../lib/labels';
import { RegisterBadge } from './Badges';
import { ExternalLink } from './FindingPanels';

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text size="sm" component="div" fw={500}>
        {children}
      </Text>
    </div>
  );
}

/** Dane rekordu w układzie raportu modułu (M1: firma, reklamujący, treść, URL; M3: podmiot, oferta, URL…). */
export function ModuleReport({ finding: f, rules, thresholds }: { finding: Finding; rules: RuleDef[]; thresholds: ThresholdValues | undefined }) {
  if (!f.modules.length) return null;
  const firm = f.entities.find((e) => e.role === 'investment_firm');
  const advertiser = f.entities.find((e) => e.role === 'advertiser');
  const advisor = f.entities.find((e) => e.role === 'advisor');
  const ruleName = new Map(rules.map((r) => [r.id, r.name]));
  const violations = f.rules.filter((r) => r.status === 'VIOLATION');
  const adDisclosed = f.flags.AD_DISCLOSURE.p >= flagThreshold(thresholds, 'AD_DISCLOSURE');
  const instruments = Object.entries(f.instruments)
    .filter(([, p]) => p >= 0.5)
    .map(([k]) => INSTRUMENT_LABEL[k as keyof typeof INSTRUMENT_LABEL]);

  const body = (m: ModuleId) => {
    if (m === 1)
      return (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
          <Field label="Firma inwestycyjna">
            {firm ? (
              <Stack gap={2} align="flex-start">
                {firm.name}
                <RegisterBadge status={firm.knfRegister.status} size="xs" />
              </Stack>
            ) : (
              'nie rozpoznano'
            )}
          </Field>
          <Field label="Reklamujący">{advertiser?.name ?? f.author.displayName ?? f.author.handle}</Field>
          <Field label="Oznaczenie reklamy">
            <Badge size="sm" variant="light" color={adDisclosed ? 'green' : 'red'} tt="none">
              {adDisclosed ? 'Oznaczona' : 'Brak oznaczenia'}
            </Badge>
          </Field>
          <Field label="Lokalizacja">
            <ExternalLink href={f.url}>{f.url}</ExternalLink>
          </Field>
        </SimpleGrid>
      );
    if (m === 2)
      return (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
          <Field label="Firma inwestycyjna">{firm?.name ?? 'nie rozpoznano'}</Field>
          <Field label={`Naruszone reguły (${violations.length})`}>
            {violations.length ? violations.map((v) => ruleName.get(v.ruleId) ?? v.ruleId).join(', ') : 'brak'}
          </Field>
          <Field label="Lokalizacja">
            <ExternalLink href={f.url}>{f.url}</ExternalLink>
          </Field>
        </SimpleGrid>
      );
    return (
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
        <Field label="Podmiot">
          {advisor ? (
            <Stack gap={2} align="flex-start">
              {advisor.name}
              <RegisterBadge status={advisor.knfRegister.status} size="xs" />
            </Stack>
          ) : (
            f.author.displayName ?? f.author.handle
          )}
        </Field>
        <Field label="Instrumenty">{instruments.join(', ') || '—'}</Field>
        <Field label="Lokalizacja">
          <ExternalLink href={f.url}>{f.url}</ExternalLink>
        </Field>
      </SimpleGrid>
    );
  };

  return (
    <Stack gap="sm">
      {f.modules.map((m) => (
        <Paper key={m} p="md" bg="var(--iw-soft)">
          <Group mb="sm">
            <Text fw={600} c={MODULE_COLOR[m]}>
              Raport: {MODULE_LABEL[m]}
            </Text>
          </Group>
          {body(m)}
        </Paper>
      ))}
    </Stack>
  );
}
