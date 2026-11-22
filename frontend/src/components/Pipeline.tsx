import { Badge, Group, Paper, Text, Title } from '@mantine/core';
import { IconArrowDown } from '@tabler/icons-react';
import { Fragment, type ReactNode } from 'react';
import type { EntityOverview, SourcePlatform } from '../api/entityTypes';
import { fmtInt } from '../lib/format';
import { ENTITY_MODULES, ENTITY_MODULE_COLOR, ENTITY_MODULE_DESC, ENTITY_MODULE_LABEL } from '../lib/labels';

function Block({ title, sub, color, mock }: { title: ReactNode; sub?: ReactNode; color?: string; mock?: boolean }) {
  return (
    <div className="iw-flow-block" data-tone={mock ? 'mock' : undefined} style={color ? { borderTop: `3px solid ${color}` } : undefined}>
      <Group gap={6}>
        <Text size="sm" fw={700}>
          {title}
        </Text>
        {mock && (
          <Badge size="xs" color="yellow" variant="light">
            atrapa
          </Badge>
        )}
      </Group>
      {sub && (
        <Text size="xs" c="dimmed" mt={2} lh={1.4}>
          {sub}
        </Text>
      )}
    </div>
  );
}

const SOURCES: { p: SourcePlatform; name: string; how: string }[] = [
  { p: 'google_ads', name: 'Google Ads Transparency', how: 'kreacje wg domeny reklamodawcy, OCR obrazów' },
  { p: 'meta_ads', name: 'Meta Ad Library', how: 'reklamy wg strony i słów kluczowych' },
  { p: 'bing_ads', name: 'Microsoft Ad Library', how: 'reklamy wg nazwy reklamodawcy' },
  { p: 'youtube', name: 'YouTube', how: 'wyszukiwanie + transkrypcje' },
  { p: 'tiktok', name: 'TikTok', how: 'konta oficjalne i finfluencerzy, transkrypcje' },
  { p: 'website', name: 'Strony firm', how: 'monitorowane podstrony, cykliczne zrzuty' },
];

/** Przepływ danych: od źródeł do alertów; oś to podmiot z rejestru KNF. */
export function Pipeline({ o }: { o: EntityOverview | undefined }) {
  const count = (p: SourcePlatform) => (p === 'website' ? o?.totals.pages : o?.itemsByPlatform[p]);
  const layers: { name: string; blocks: ReactNode }[] = [
    {
      name: 'Źródła',
      blocks: SOURCES.map((s) => {
        const n = count(s.p);
        return (
          <Block
            key={s.p}
            title={s.name}
            sub={
              <>
                {s.how}
                {n !== undefined && (
                  <>
                    {' · '}
                    <b>{fmtInt(n)}</b> {s.p === 'website' ? 'stron' : 'rekordów'}
                  </>
                )}
              </>
            }
          />
        );
      }),
    },
    {
      name: 'Zbieranie',
      blocks: (
        <>
          <Block title="Kolektory reklam i social media" sub="scrapers/ · jeden kolektor na źródło, limity zapytań, ponowienia" />
          <Block title="Monitor stron" sub="monitor/ · zrzut strony + sha256; zmiana skrótu = zmiana strony (ostrzeżenie dodane, zmienione, usunięte)" />
        </>
      ),
    },
    {
      name: 'Normalizacja',
      blocks: (
        <>
          <Block title="Wspólny rekord" sub="źródło, URL, autor, data, sekcje tekstu (tytuł, treść reklamy, OCR, transkrypcja)" />
          <Block
            title="Powiązanie z podmiotem"
            sub={`rejestr KNF (${o ? fmtInt(o.totals.knfEntries) : '…'} wpisów) zgrupowany w marki · domeny · konta oficjalne · aliasy z wykluczeniem homonimów`}
          />
        </>
      ),
    },
    {
      name: 'Klasyfikacja',
      blocks: (
        <>
          {ENTITY_MODULES.map((m) => (
            <Block key={m} title={ENTITY_MODULE_LABEL[m]} sub={ENTITY_MODULE_DESC[m]} color={ENTITY_MODULE_COLOR[m]} />
          ))}
          <Block mock title="Klasyfikator mock-v0" sub="reguły słownikowe zwracają ten sam kształt wyniku co docelowy LLM: moduł, wynik, waga, naruszenia z cytatem i pozycją w tekście" />
        </>
      ),
    },
    {
      name: 'Alerty',
      blocks: (
        <>
          <Block title="Alert z wyniku" sub="każdy wynik o wysokiej wadze" color="var(--iw-red)" />
          <Block title="Alert ze strony" sub="usunięte lub zmienione ostrzeżenie o ryzyku na monitorowanej stronie" color="#c2500a" />
        </>
      ),
    },
    {
      name: 'Panel',
      blocks: <Block title="Statystyki · Podmioty · Raporty" sub="widoki wokół podmiotu, porównanie zrzutów stron, raporty do druku" color="var(--iw-primary)" />,
    },
  ];
  return (
    <Paper p="lg">
      <Title order={4} mb="md">
        Jak to działa
      </Title>
      {layers.map((l, i) => (
        <Fragment key={l.name}>
          {i > 0 && (
            <div className="iw-flow-arrow">
              <IconArrowDown size={16} />
            </div>
          )}
          <div className="iw-flow-layer">
            <Group gap={8} wrap="nowrap">
              <Badge circle size="lg">
                {i + 1}
              </Badge>
              <Text size="xs" fw={700} tt="uppercase" c="dimmed">
                {l.name}
              </Text>
            </Group>
            <div className="iw-flow-blocks">{l.blocks}</div>
          </div>
        </Fragment>
      ))}
    </Paper>
  );
}
