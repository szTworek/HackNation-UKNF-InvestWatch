import { Anchor, Group, SimpleGrid, Stack, Text } from '@mantine/core';
import { IconExternalLink } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import type { Finding } from '../api/types';
import { domainOf } from '../lib/findings';
import { fmtCompact, fmtDateTime } from '../lib/format';
import { KIND_LABEL, PLATFORM_LABEL } from '../lib/labels';

export function ExternalLink({ href, blocked, children }: { href: string; blocked?: boolean; children: ReactNode }) {
  if (blocked) {
    return (
      <Text span size="sm" title="Link nieaktywny: domena na liście ostrzeżeń CERT Polska" style={{ wordBreak: 'break-all' }}>
        {href}
      </Text>
    );
  }
  return (
    <Anchor href={href} target="_blank" rel="noopener noreferrer" size="sm" style={{ wordBreak: 'break-all' }}>
      {children} <IconExternalLink size={12} style={{ verticalAlign: 'middle' }} aria-label="otwiera się w nowej karcie" />
    </Anchor>
  );
}

export function LinkList({ finding }: { finding: Finding }) {
  if (!finding.outboundLinks.length) return <Text size="sm" c="dimmed">Brak linków.</Text>;
  return (
    <Stack gap={6}>
      {finding.outboundLinks.map((url) => (
        <Group key={url} gap={6} wrap="nowrap" align="flex-start">
          <ExternalLink href={url} blocked={finding.blockedUrls?.includes(url)}>
            {domainOf(url)}
          </ExternalLink>
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
        <ExternalLink href={finding.url} blocked={finding.blockedUrls?.includes(finding.url)}>
          {PLATFORM_LABEL[finding.platform]}, {KIND_LABEL[finding.kind].toLowerCase()}
        </ExternalLink>
      </Meta>
      <Meta label="Autor">
        {a.displayName ? `${a.displayName} (${a.handle})` : a.handle}
        {a.followers !== undefined && <Text span size="xs" c="dimmed">{`, ${fmtCompact(a.followers)} obserwujących`}</Text>}
      </Meta>
      <Meta label="Opublikowano">{fmtDateTime(finding.publishedAt)}</Meta>
      <Meta label="Pobrano">{fmtDateTime(finding.fetchedAt)}</Meta>
      <Meta label="Wersja modelu">
        <Text span size="xs" c="dimmed">
          {finding.modelVersion}
        </Text>
      </Meta>
    </SimpleGrid>
  );
}
