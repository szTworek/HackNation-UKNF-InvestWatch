import { Anchor, Badge, Group, List, Paper, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { IconExternalLink } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import type { Finding } from '../api/types';
import { domainOf, scamQuotes, scamSignalTexts, suspiciousDomains, type ThresholdValues } from '../lib/findings';
import { fmtCompact, fmtDateTime, fmtPct } from '../lib/format';
import { FLAG_COLOR, FLAG_LABEL, KIND_LABEL, PLATFORM_LABEL } from '../lib/labels';

export function ExternalLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Anchor href={href} target="_blank" rel="noopener noreferrer" size="sm" style={{ wordBreak: 'break-all' }}>
      {children} <IconExternalLink size={12} style={{ verticalAlign: 'middle' }} aria-label="otwiera się w nowej karcie" />
    </Anchor>
  );
}

const SECTION_LABEL = { text: 'treść', transcript: 'transkrypcja', ocr: 'napis w filmie', landing: 'strona docelowa' } as const;

/** „Ocena oszustwa” na górze szczegółów. Język ostrożny: cechy i podejrzenie, nie rozstrzygnięcie. */
export function ScamPanel({ finding, thresholds }: { finding: Finding; thresholds: ThresholdValues | undefined }) {
  const signals = scamSignalTexts(finding);
  const quotes = scamQuotes(finding, thresholds);
  return (
    <Paper withBorder p="md" bg="var(--iw-red-soft)" style={{ borderColor: 'var(--iw-red)' }}>
      <Group justify="space-between" mb="sm">
        <Title order={4}>Podejrzenie oszustwa</Title>
        <Badge color="red" size="lg" variant="filled" tt="none">
          {fmtPct(finding.scam.p)} pewności modelu
        </Badge>
      </Group>
      <SimpleGrid cols={{ base: 1, md: 3 }} spacing="lg">
        <Stack gap={4}>
          <Text size="sm" fw={600}>
            Sygnały
          </Text>
          <List size="sm" spacing={4}>
            {signals.map((s) => (
              <List.Item key={s}>{s}</List.Item>
            ))}
          </List>
        </Stack>
        <Stack gap={6}>
          <Text size="sm" fw={600}>
            Cechy oszustwa
          </Text>
          {quotes.slice(0, 5).map((q) => (
            <div key={`${q.ev.section}-${q.ev.t ?? ''}-${q.ev.start}`}>
              <Text
                size="sm"
                component="mark"
                bg={`var(--mantine-color-${FLAG_COLOR[q.flags[0]]}-light)`}
                style={{ borderBottom: `2px solid var(--mantine-color-${FLAG_COLOR[q.flags[0]]}-6)` }}
              >
                „{q.ev.text}”
              </Text>
              <Text size="xs" c="dimmed">
                {q.flags.map((f) => FLAG_LABEL[f]).join(', ')} ({SECTION_LABEL[q.ev.section]})
              </Text>
            </div>
          ))}
        </Stack>
        <Stack gap={4}>
          <Text size="sm" fw={600}>
            Linki wychodzące
          </Text>
          <LinkList finding={finding} />
        </Stack>
      </SimpleGrid>
    </Paper>
  );
}

export function LinkList({ finding }: { finding: Finding }) {
  if (!finding.outboundLinks.length) return <Text size="sm" c="dimmed">Brak linków.</Text>;
  const bad = suspiciousDomains(finding);
  return (
    <Stack gap={6}>
      {finding.outboundLinks.map((url) => (
        <Group key={url} gap={6} wrap="nowrap" align="flex-start">
          <ExternalLink href={url}>{domainOf(url)}</ExternalLink>
          {bad.has(domainOf(url)) && (
            <Badge color="red" variant="light" size="xs" style={{ flexShrink: 0 }} mt={3} tt="none">
              podejrzana domena
            </Badge>
          )}
        </Group>
      ))}
    </Stack>
  );
}

function Meta({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text size="sm" component="div">
        {children}
      </Text>
    </div>
  );
}

export function FindingMeta({ finding }: { finding: Finding }) {
  const a = finding.author;
  return (
    <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm" verticalSpacing="sm">
      <Meta label="Źródło">
        <ExternalLink href={finding.url}>
          {PLATFORM_LABEL[finding.platform]}, {KIND_LABEL[finding.kind].toLowerCase()}
        </ExternalLink>
      </Meta>
      <Meta label="Autor">
        {a.displayName ? `${a.displayName} (${a.handle})` : a.handle}
        {a.followers !== undefined && <Text span size="xs" c="dimmed">{`, ${fmtCompact(a.followers)} obserwujących`}</Text>}
      </Meta>
      <Meta label="Opublikowano">{fmtDateTime(finding.publishedAt)}</Meta>
      <Meta label="Pobrano">{fmtDateTime(finding.fetchedAt)}</Meta>
      {finding.campaignId && (
        <Meta label="Kampania">
          <Anchor component={Link} to={`/campaigns/${finding.campaignId}`} size="sm">
            {finding.campaignId}
          </Anchor>
        </Meta>
      )}
      <Meta label="Wersja modelu">
        <Text span size="xs" c="dimmed">
          {finding.modelVersion}
        </Text>
      </Meta>
    </SimpleGrid>
  );
}
