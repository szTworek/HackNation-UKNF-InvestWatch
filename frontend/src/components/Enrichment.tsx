import { Badge, Box, Group, Image, Modal, Paper, ScrollArea, SimpleGrid, Stack, Text, Title, UnstyledButton } from '@mantine/core';
import { IconChevronRight } from '@tabler/icons-react';
import { lazy, Suspense, useState } from 'react';
import type { LandingDomainFlag, LandingPageView, MediaView } from '../api/types';
import { assetUrl, domainOf, type Span } from '../lib/findings';
import { fmtPct } from '../lib/format';
import { HighlightedText } from './HighlightedText';
import { Loading } from './PageState';

const VoiceChart = lazy(() => import('./Charts').then((m) => ({ default: m.VoiceChart })));

const DOMAIN_FLAG_LABEL: Record<LandingDomainFlag, string> = {
  CERT_LIST_DOMAIN: 'Lista ostrzeżeń CERT Polska',
  KNF_WARNING_LIST: 'Lista ostrzeżeń KNF',
  IMPERSONATION: 'Podszywanie się pod markę',
  NEW_DOMAIN: 'Nowa domena',
};

// ---------------------------------------------------------------------------
// Strona docelowa
// ---------------------------------------------------------------------------

/** Łańcuch przekierowań jako „breadcrumb”; podejrzane domeny na czerwono. */
function RedirectChain({ chain, suspicious }: { chain: string[]; suspicious: boolean }) {
  return (
    <Group gap={4} wrap="wrap">
      {chain.map((url, i) => {
        const last = i === chain.length - 1;
        const bad = suspicious && i > 0;
        return (
          <Group key={`${url}-${i}`} gap={4} wrap="nowrap">
            {i > 0 && <IconChevronRight size={14} color="var(--mantine-color-gray-5)" aria-hidden />}
            <Badge
              variant={bad ? 'light' : 'default'}
              color={bad ? 'red' : 'gray'}
              tt="none"
              size="md"
              fw={last ? 700 : 400}
              title={url}
            >
              {domainOf(url)}
            </Badge>
          </Group>
        );
      })}
    </Group>
  );
}

export function LandingView({ page, spans }: { page: LandingPageView; spans: Span[] }) {
  const [zoom, setZoom] = useState<string | null>(null);
  const suspicious = page.domainFlags.length > 0;
  return (
    <Stack gap="md">
      <Paper withBorder p="md">
        <Stack gap="sm">
          <RedirectChain chain={page.redirectChain} suspicious={suspicious} />
          <Group gap={6}>
            {page.hasContactForm && (
              <Badge color="orange" variant="light" tt="none">
                Formularz kontaktowy (telefon)
              </Badge>
            )}
            {page.domainFlags.map((f) => (
              <Badge key={f} color="red" variant="light" tt="none">
                {DOMAIN_FLAG_LABEL[f]}
              </Badge>
            ))}
          </Group>
        </Stack>
      </Paper>

      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
        <Paper withBorder p="md">
          <Title order={5} mb="sm">
            {page.title ?? 'Treść strony'}
          </Title>
          <HighlightedText text={page.text} spans={spans} idPrefix="ev-landing" />
        </Paper>
        <Group align="flex-start" gap="sm" wrap="nowrap">
          {[
            { url: page.screenshotUrl, label: 'Komputer', w: '70%' },
            { url: page.mobileScreenshotUrl, label: 'Telefon', w: '30%' },
          ]
            .filter((s) => s.url)
            .map((s) => (
              <UnstyledButton key={s.label} onClick={() => setZoom(assetUrl(s.url ?? ''))} w={s.w} aria-label={`Powiększ zrzut: ${s.label}`}>
                <Text size="xs" c="dimmed" mb={4}>
                  {s.label}
                </Text>
                <Image src={assetUrl(s.url ?? '')} alt={`Zrzut strony, ${s.label.toLowerCase()}`} loading="lazy" radius="sm" style={{ border: '1px solid var(--iw-border)' }} />
              </UnstyledButton>
            ))}
        </Group>
      </SimpleGrid>

      <Modal opened={!!zoom} onClose={() => setZoom(null)} size="auto" title="Zrzut strony" centered>
        {zoom && <Image src={zoom} alt="Zrzut strony w powiększeniu" mah="80vh" fit="contain" />}
      </Modal>
    </Stack>
  );
}

// ---------------------------------------------------------------------------
// Wideo
// ---------------------------------------------------------------------------

const mmss = (t: number) => `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(Math.round(t) % 60).padStart(2, '0')}`;

export function VideoView({
  media,
  transcript,
  spans,
  activeT,
  onSelectT,
}: {
  media: MediaView;
  transcript?: string;
  spans: Span[];
  activeT: number | null;
  onSelectT: (t: number) => void;
}) {
  return (
    <Stack gap="md">
      <Paper withBorder p="md">
        <Group justify="space-between" mb="sm">
          <Title order={5}>Klatki i napisy na ekranie</Title>
          {media.asrUsed && (
            <Badge variant="light" color="gray" tt="none">
              Transkrypcja z naszego rozpoznawania mowy
            </Badge>
          )}
        </Group>
        <ScrollArea type="auto" offsetScrollbars>
          <Group gap="sm" wrap="nowrap" align="flex-start">
            {media.keyframes.map((k) => {
              const active = activeT !== null && Math.abs(activeT - k.t) < 0.5;
              return (
                <UnstyledButton
                  key={k.t}
                  id={`frame-${k.t}`}
                  onClick={() => onSelectT(k.t)}
                  w={120}
                  style={{ flexShrink: 0, borderRadius: 4, outline: active ? '3px solid var(--iw-primary)' : undefined }}
                >
                  <Image src={assetUrl(k.imageUrl)} alt={`Klatka ${mmss(k.t)}`} loading="lazy" radius="sm" h={200} fit="cover" />
                  <Text size="xs" c="dimmed" mt={4}>
                    {mmss(k.t)}
                  </Text>
                  <Text size="xs" lineClamp={2}>
                    {k.ocrText}
                  </Text>
                </UnstyledButton>
              );
            })}
          </Group>
        </ScrollArea>
      </Paper>

      {media.syntheticVoice && (
        <Paper withBorder p="md">
          <Group justify="space-between" mb={4}>
            <Title order={5}>Syntetyczny głos</Title>
            <Badge color="yellow" variant="light" tt="none">
              Sygnał eksperymentalny – wymaga weryfikacji
            </Badge>
          </Group>
          <Text size="sm" mb="sm">
            Średnio {fmtPct(media.syntheticVoice.score)} prawdopodobieństwa, że głos jest wygenerowany.
          </Text>
          <Suspense fallback={<Loading />}>
            <VoiceChart segments={media.syntheticVoice.segments} activeT={activeT} />
          </Suspense>
        </Paper>
      )}

      {transcript && (
        <Paper withBorder p="md">
          <Title order={5} mb="sm">
            Transkrypcja
          </Title>
          <Box>
            <HighlightedText text={transcript} spans={spans} idPrefix="ev-transcript" />
          </Box>
        </Paper>
      )}
    </Stack>
  );
}
