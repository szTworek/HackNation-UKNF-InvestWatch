import { Anchor, Badge, Box, Group, Paper, SimpleGrid, Stack, Table, Text, Title, Tooltip, UnstyledButton } from '@mantine/core';
import { IconExternalLink, IconShieldCheck, IconShieldX } from '@tabler/icons-react';
import { useMemo, useState, type ReactNode } from 'react';
import { API_URL } from '../api/client';
import { useChange, useItem } from '../api/hooks';
import type {
  EntityAlert,
  EntityFinding,
  EntityModule,
  LegibilityCheck,
  LegibilityFailure,
  LegibilityStatus,
  MonitoredPage,
  PageChange,
  PageSnapshot,
  RuleHit,
  Severity,
  SourcePlatform,
} from '../api/entityTypes';
import { fmtDate, fmtDateTime, fmtProb, fmtRelative } from '../lib/format';
import {
  CHANNEL_LABEL,
  ENTITY_MODULE_COLOR,
  ENTITY_MODULE_LABEL,
  ENTITY_MODULE_SHORT,
  SEVERITY_COLOR,
  SEVERITY_LABEL,
  SOURCE_PLATFORM_LABEL,
  TEXT_SECTION_LABEL,
  ruleText,
} from '../lib/labels';
import { ErrorState, Loading } from './PageState';

export const shortUrl = (u: string) => u.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '');

const fmtRel = (x: number) => `${fmtProb(x)}×`;
const fmtContrast = (x: number) => `${x.toLocaleString('pl-PL', { maximumFractionDigits: 1 })}:1`;
const clip = (t: string, n = 60) => (t.length > n ? `${t.slice(0, n)}…` : t);

const LEGIBILITY_LABEL: Record<LegibilityStatus, string> = {
  ok: 'Oznaczenie czytelne',
  problem: 'Oznaczenie słabo widoczne',
  no_disclosure: 'Brak oznaczenia',
};
const LEGIBILITY_COLOR: Record<LegibilityStatus, string> = { ok: 'teal', problem: 'red', no_disclosure: 'gray' };
const METRIC_LABEL: Record<LegibilityFailure['metric'], string> = {
  contrast_ratio: 'Kontrast',
  rel_font_size: 'Rozmiar względem materiału',
  font_px: 'Rozmiar',
};

const fmtFailure = (f: LegibilityFailure) =>
  f.metric === 'contrast_ratio'
    ? `${fmtContrast(f.value)} < ${fmtContrast(f.threshold)}`
    : f.metric === 'rel_font_size'
      ? `${fmtRel(f.value)} < ${fmtRel(f.threshold)}`
      : `${f.value} px < ${f.threshold} px`;

/** Wynik sprawdzenia czytelności oznaczenia: stałe progi z `preprocessing/legibility.py`, bez LLM. */
export function LegibilityResult({ check, note }: { check: LegibilityCheck; note?: string }) {
  return (
    <Stack gap={2}>
      <Group gap={6}>
        <Badge size="xs" variant="light" color={LEGIBILITY_COLOR[check.status]}>
          {LEGIBILITY_LABEL[check.status]}
        </Badge>
        {note && (
          <Text size="xs" c="dimmed">
            {note}
          </Text>
        )}
      </Group>
      {check.failures.map((f, i) => (
        <Text key={i} size="xs">
          {METRIC_LABEL[f.metric]} {fmtFailure(f)} ({f.rule}) · „{clip(f.text)}”
        </Text>
      ))}
    </Stack>
  );
}

export const riskColor = (v: number) => (v >= 0.7 ? 'var(--iw-red)' : v >= 0.5 ? '#c2500a' : 'var(--iw-primary)');

/** Wskaźnik ryzyka 0–100 (średnia 20 najwyższych wyników klasyfikatora). */
export function RiskMeter({ value }: { value: number }) {
  return (
    <Group gap={8} wrap="nowrap">
      <div className="iw-meter" style={{ flex: 1, minWidth: 60 }}>
        <span style={{ width: `${value * 100}%`, background: riskColor(value) }} />
      </div>
      <Text size="sm" fw={600} className="iw-kpi-value" w={24} ta="right">
        {Math.round(value * 100)}
      </Text>
    </Group>
  );
}

export function SeverityBadge({ s }: { s: Severity }) {
  return (
    <Badge size="sm" color={SEVERITY_COLOR[s]} variant={s === 'high' ? 'filled' : 'light'}>
      {SEVERITY_LABEL[s]}
    </Badge>
  );
}

export function EntityModuleBadge({ m }: { m: EntityModule }) {
  return (
    <Tooltip label={ENTITY_MODULE_LABEL[m]}>
      <Badge size="sm" variant="outline" style={{ color: ENTITY_MODULE_COLOR[m], borderColor: ENTITY_MODULE_COLOR[m] }}>
        {ENTITY_MODULE_SHORT[m]}
      </Badge>
    </Tooltip>
  );
}

export function MockBadge({ hint = 'Dane syntetyczne, nie zebrane ze źródła' }: { hint?: string }) {
  return (
    <Tooltip label={hint}>
      <Badge size="xs" color="yellow" variant="light">
        atrapa
      </Badge>
    </Tooltip>
  );
}

export function PlatformText({ p }: { p: SourcePlatform }) {
  return (
    <Text span size="sm" fw={500}>
      {SOURCE_PLATFORM_LABEL[p] ?? p}
    </Text>
  );
}

export function RiskWarningStatus({ snap }: { snap: PageSnapshot | null }) {
  if (!snap)
    return (
      <Text size="xs" c="dimmed">
        nie pobrano
      </Text>
    );
  const rw = snap.riskWarning;
  return rw.present ? (
    <Group gap={4} wrap="nowrap" c="green.8">
      <IconShieldCheck size={16} />
      <Text size="xs" fw={500}>
        Ostrzeżenie{rw.cfdLossPct ? ` · ${rw.cfdLossPct}%` : ''} · {rw.aboveFold ? 'na górze strony' : 'niżej na stronie'}
      </Text>
    </Group>
  ) : (
    <Group gap={4} wrap="nowrap" c="red.8">
      <IconShieldX size={16} />
      <Text size="xs" fw={600}>
        Brak ostrzeżenia o ryzyku
      </Text>
    </Group>
  );
}

// ---------------------------------------------------------------------------
// Rekord z podświetleniem dowodów
// ---------------------------------------------------------------------------

function Highlighted({ text, hits }: { text: string; hits: RuleHit[] }) {
  const parts = useMemo(() => {
    const spans = hits
      .filter((h): h is RuleHit & { span: [number, number] } => !!h.span && h.span[1] <= text.length)
      .sort((a, b) => a.span[0] - b.span[0]);
    const out: ReactNode[] = [];
    let pos = 0;
    spans.forEach((h, i) => {
      const [s, e] = h.span;
      if (s < pos) return;
      out.push(text.slice(pos, s));
      out.push(
        <mark key={i} className="iw-hit" title={ruleText(h.ruleId, h.label)}>
          {text.slice(s, e)}
          {/^R\d/.test(h.ruleId) && <sup>{h.ruleId}</sup>}
        </mark>,
      );
      pos = e;
    });
    out.push(text.slice(pos));
    return out;
  }, [text, hits]);
  return <>{parts}</>;
}

function FindingBlock({ f, focus }: { f: EntityFinding; focus: boolean }) {
  return (
    <Paper p="sm" style={focus ? { borderColor: 'var(--iw-link)', boxShadow: '0 0 0 2px rgba(30,106,200,.25)' } : undefined}>
      <Group gap={8}>
        <EntityModuleBadge m={f.module} />
        <SeverityBadge s={f.severity} />
        <Text size="xs" c="dimmed">
          wynik <b className="iw-kpi-value">{fmtProb(f.score)}</b>
        </Text>
        <Text size="xs" c="dimmed" ml="auto">
          {fmtDateTime(f.createdAt)}
        </Text>
      </Group>
      <Stack gap={6} mt={8}>
        {f.ruleHits.map((h, i) => (
          <Box key={i}>
            <Text size="sm" fw={500}>
              {ruleText(h.ruleId, h.label)}
            </Text>
            <Text size="xs" c="dimmed" fs="italic" bg="var(--iw-soft)" px={8} py={4} mt={2}>
              „{h.evidence}” <span style={{ fontStyle: 'normal' }}>— {TEXT_SECTION_LABEL[h.section] ?? h.section}</span>
            </Text>
          </Box>
        ))}
      </Stack>
    </Paper>
  );
}

export function ItemView({ id, focusFinding }: { id: string; focusFinding: string | null }) {
  const q = useItem(id);
  const [hover, setHover] = useState<number | null>(null);
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const it = q.data;
  if (!it) return <Loading />;
  const hits = it.findings.flatMap((f) => f.ruleHits);
  const media = it.media ?? [];
  const ocrLines = it.ocrLines ?? [];
  const lg = it.legibility;
  return (
    <Stack gap="md">
      <Group gap={8}>
        <PlatformText p={it.platform} />
        <Badge size="sm" variant="default">
          {CHANNEL_LABEL[it.channel]}
        </Badge>
        <Badge size="sm" variant="light" color={it.authorIsEntity ? 'knf' : 'orange'}>
          {it.authorIsEntity ? 'konto oficjalne' : 'osoba trzecia'}
        </Badge>
        <Text size="sm" fw={500}>
          {it.author}
        </Text>
        {it.mock && <MockBadge />}
      </Group>
      <Group gap="md">
        <Text size="xs" c="dimmed">
          Publikacja {fmtDate(it.publishedAt ?? undefined)} · pobrano {fmtDateTime(it.fetchedAt)}
        </Text>
        <Anchor href={it.sourceUrl} target="_blank" rel="noreferrer" size="xs" ml="auto">
          <Group gap={4}>
            Źródło <IconExternalLink size={13} />
          </Group>
        </Anchor>
      </Group>

      {it.findings.length > 0 && (
        <div>
          <Group gap={8} mb={6}>
            <Title order={5}>Wyniki</Title>
          </Group>
          <Stack gap="xs">
            {it.findings.map((f) => (
              <FindingBlock key={f.id} f={f} focus={f.id === focusFinding} />
            ))}
          </Stack>
        </div>
      )}

      {media.length > 0 && (
        <Group gap="sm" align="flex-start">
          {media.map((m) => (
            <Box key={m.key} pos="relative" maw={m.width} style={{ flex: '1 1 240px' }}>
              <img src={`${API_URL}/media/${m.key}`} alt="" style={{ display: 'block', width: '100%' }} />
              {m.ocr &&
                lg?.imageWidth &&
                lg.imageHeight &&
                ocrLines.map((l, i) =>
                  l.isDisclosure ? (
                    <Box
                      key={i}
                      pos="absolute"
                      onMouseEnter={() => setHover(i)}
                      onMouseLeave={() => setHover(null)}
                      style={{
                        left: `${(l.box[0] / lg.imageWidth!) * 100}%`,
                        top: `${(l.box[1] / lg.imageHeight!) * 100}%`,
                        width: `${(l.box[2] / lg.imageWidth!) * 100}%`,
                        height: `${(l.box[3] / lg.imageHeight!) * 100}%`,
                        outline: `${hover === i ? 2 : 1}px dashed var(--iw-link)`,
                        background: hover === i ? 'rgba(30,106,200,.25)' : 'rgba(30,106,200,.08)',
                      }}
                    >
                      <Box
                        pos="absolute"
                        style={{
                          top: -9,
                          left: -9,
                          minWidth: 18,
                          height: 18,
                          borderRadius: 9,
                          background: 'var(--iw-link)',
                          color: '#fff',
                          fontSize: 11,
                          lineHeight: '18px',
                          textAlign: 'center',
                          boxShadow: '0 0 0 2px #fff',
                        }}
                      >
                        {i + 1}
                      </Box>
                    </Box>
                  ) : null,
                )}
            </Box>
          ))}
          {'ocr' in it.text && (
            <Text size="xs" c="dimmed" maw={240}>
              Sekcja „{TEXT_SECTION_LABEL.ocr}” to tekst odczytany z tego obrazu; numerowane ramki zaznaczają linie z oznaczeniem (numer = wiersz w tabeli pomiarów).
            </Text>
          )}
        </Group>
      )}

      <div>
        <Title order={5} mb={6}>
          Zebrana treść
        </Title>
        <Stack gap="sm">
          {Object.entries(it.text).map(([sec, t]) => (
            <div key={sec}>
              <Text size="xs" fw={600} tt="uppercase" c="dimmed" mb={2}>
                {TEXT_SECTION_LABEL[sec] ?? sec}
              </Text>
              <Text size="sm" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                <Highlighted text={t} hits={hits.filter((h) => h.section === sec)} />
              </Text>
            </div>
          ))}
        </Stack>
      </div>

      {(lg || ocrLines.length > 0) && (
        <div>
          <Title order={5} mb={6}>
            Pomiary czytelności
          </Title>
          {it.legibilityCheck && (
            <Box mb={6}>
              <LegibilityResult
                check={it.legibilityCheck}
                note={it.legibilityCheck.status === 'ok' && lg?.disclosureInText ? 'oznaczenie jest też w opisie' : undefined}
              />
            </Box>
          )}
          <Stack gap={2} mb={ocrLines.length ? 6 : 0}>
            {lg?.dominantLinePx != null && (
              <Text size="xs">Dominująca wysokość linii na grafice: {lg.dominantLinePx} px</Text>
            )}
            {lg && <Text size="xs">Ujawnienie w tekście opisu: {lg.disclosureInText ? 'tak' : 'nie'}</Text>}
            {lg?.disclosureOnImage != null && (
              <Text size="xs">Ujawnienie na grafice: {lg.disclosureOnImage ? 'tak' : 'nie'}</Text>
            )}
          </Stack>
          {ocrLines.length > 0 && (
            <Table verticalSpacing={4} fz="xs">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>#</Table.Th>
                  <Table.Th>Linia OCR</Table.Th>
                  <Table.Th>Wysokość</Table.Th>
                  <Table.Th>Względem dominującej</Table.Th>
                  <Table.Th>Kontrast</Table.Th>
                  <Table.Th>Ujawnienie</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {ocrLines.map((l, i) => (
                  <Table.Tr
                    key={i}
                    onMouseEnter={() => setHover(i)}
                    onMouseLeave={() => setHover(null)}
                    bg={hover === i ? 'rgba(30,106,200,.12)' : undefined}
                  >
                    <Table.Td ff="monospace">{i + 1}</Table.Td>
                    <Table.Td>{clip(l.text)}</Table.Td>
                    <Table.Td ff="monospace">{l.boxHeightPx} px</Table.Td>
                    <Table.Td ff="monospace">{fmtRel(l.relFontSize)}</Table.Td>
                    <Table.Td ff="monospace">{l.contrastRatio == null ? '—' : fmtContrast(l.contrastRatio)}</Table.Td>
                    <Table.Td>{l.isDisclosure ? 'tak' : 'nie'}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </div>
      )}
    </Stack>
  );
}

// ---------------------------------------------------------------------------
// Diff dwóch zrzutów strony
// ---------------------------------------------------------------------------

type Row = { kind: 'same' | 'del' | 'add' | 'mod'; a?: string; b?: string; ai?: number; bi?: number };

function diffLines(a: string[], b: string[]): Row[] {
  const n = a.length;
  const m = b.length;
  const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const raw: Row[] = [];
  let i = 0;
  let j = 0;
  while (i < n || j < m) {
    if (i < n && j < m && a[i] === b[j]) raw.push({ kind: 'same', a: a[i], b: b[j], ai: i++, bi: j++ });
    else if (j < m && (i >= n || dp[i][j + 1] >= dp[i + 1][j])) raw.push({ kind: 'add', b: b[j], bi: j++ });
    else raw.push({ kind: 'del', a: a[i], ai: i++ });
  }
  const out: Row[] = [];
  for (let k = 0; k < raw.length; k++) {
    const r = raw[k];
    const nx = raw[k + 1];
    if (r.kind === 'del' && nx?.kind === 'add') {
      out.push({ kind: 'mod', a: r.a, ai: r.ai, b: nx.b, bi: nx.bi });
      k++;
    } else if (r.kind === 'add' && nx?.kind === 'del') {
      out.push({ kind: 'mod', a: nx.a, ai: nx.ai, b: r.b, bi: r.bi });
      k++;
    } else out.push(r);
  }
  return out;
}

function wordDiff(a: string, b: string, side: 'a' | 'b') {
  const wa = a.split(/(\s+)/);
  const wb = b.split(/(\s+)/);
  const other = new Set(side === 'a' ? wb : wa);
  return (side === 'a' ? wa : wb).map((w, i) =>
    other.has(w) ? <span key={i}>{w}</span> : <span key={i} className={side === 'a' ? 'iw-diff-word-del' : 'iw-diff-word-add'}>{w}</span>,
  );
}

function SnapCard({ s, label }: { s: PageSnapshot; label: string }) {
  const rw = s.riskWarning;
  return (
    <Paper p="sm">
      <Group gap={8} mb={4}>
        <Text size="sm" fw={600}>
          {label}
        </Text>
        {s.mock && <MockBadge hint="Wcześniejszy zrzut zrekonstruowany syntetycznie" />}
        <Text size="xs" c="dimmed" ml="auto">
          {fmtDateTime(s.fetchedAt)}
        </Text>
      </Group>
      <RiskWarningStatus snap={s} />
      {rw.present && rw.cfdLossPct !== null && (
        <Text size="xs" c="dimmed" mt={2}>
          {rw.cfdLossPct}% rachunków detalicznych traci pieniądze
        </Text>
      )}
      {s.legibilityCheck && (
        <Box mt={4}>
          <LegibilityResult check={s.legibilityCheck} />
        </Box>
      )}
      {Object.entries(s.legibility ?? {}).map(([vp, l]) => (
        <Stack key={vp} gap={0} mt={4}>
          <Text size="xs" c="dimmed">
            {vp} · dominująca czcionka {l.dominantFontPx} px
          </Text>
          {l.disclosureBlocks.map((b, i) => (
            <Text key={i} size="xs">
              „{clip(b.text)}”: {b.fontSizePx} px ({fmtRel(b.relFontSize)} dominującej)
              {b.contrastRatio != null && `, kontrast ${fmtContrast(b.contrastRatio)} (${b.contrastSource === 'css' ? 'CSS' : 'zrzut ekranu'})`}
              {` · ${b.aboveFold ? 'na górze strony' : 'niżej na stronie'}`}
            </Text>
          ))}
        </Stack>
      ))}
      <Text size="xs" c="dimmed" mt={4} ff="monospace">
        sha256 {s.textSha256.slice(0, 16)}…
      </Text>
    </Paper>
  );
}

export function DiffView({ id }: { id: string }) {
  const q = useChange(id);
  const c = q.data;
  const rows = useMemo(() => (c ? diffLines(c.from.text.split('\n'), c.to.text.split('\n')) : []), [c]);
  const visible = useMemo(() => {
    const keep = new Set<number>();
    rows.forEach((r, i) => {
      if (r.kind !== 'same') for (let k = i - 2; k <= i + 2; k++) keep.add(k);
    });
    const out: (Row | { kind: 'gap'; count: number })[] = [];
    let gap = 0;
    rows.forEach((r, i) => {
      if (keep.has(i)) {
        if (gap) out.push({ kind: 'gap', count: gap });
        gap = 0;
        out.push(r);
      } else gap++;
    });
    if (gap) out.push({ kind: 'gap', count: gap });
    return out;
  }, [rows]);
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  if (!c) return <Loading />;
  return (
    <Stack gap="md">
      <Group gap={8}>
        {c.mock && <MockBadge />}
        <Text size="sm" fw={600}>
          {c.summary}
        </Text>
        <Anchor href={c.to.url} target="_blank" rel="noreferrer" size="xs" ml="auto">
          <Group gap={4}>
            {shortUrl(c.to.url)} <IconExternalLink size={13} />
          </Group>
        </Anchor>
      </Group>
      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        <SnapCard s={c.from} label="Przed" />
        <SnapCard s={c.to} label="Po" />
      </SimpleGrid>
      <div className="iw-diff">
        <div className="iw-diff-row iw-diff-head">
          <div>Przed · {fmtDate(c.from.fetchedAt)}</div>
          <div>Po · {fmtDate(c.to.fetchedAt)}</div>
        </div>
        {visible.map((r, i) =>
          r.kind === 'gap' ? (
            <div key={i} className="iw-diff-gap">
              ⋯ {r.count} niezmienionych linii
            </div>
          ) : (
            <div key={i} className="iw-diff-row">
              <div className={r.kind === 'del' || r.kind === 'mod' ? 'iw-diff-del' : undefined}>
                <span className="iw-diff-ln">{r.ai !== undefined ? r.ai + 1 : ''}</span>
                <span>{r.kind === 'mod' ? wordDiff(r.a ?? '', r.b ?? '', 'a') : r.a}</span>
              </div>
              <div className={r.kind === 'add' || r.kind === 'mod' ? 'iw-diff-add' : undefined}>
                <span className="iw-diff-ln">{r.bi !== undefined ? r.bi + 1 : ''}</span>
                <span>{r.kind === 'mod' ? wordDiff(r.a ?? '', r.b ?? '', 'b') : r.b}</span>
              </div>
            </div>
          ),
        )}
      </div>
      {c.styleChanges.length > 0 && (
        <Table verticalSpacing={4} fz="xs">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Fragment</Table.Th>
              <Table.Th>Właściwość</Table.Th>
              <Table.Th>Przed → po</Table.Th>
              <Table.Th>Widok</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {c.styleChanges.map((s, i) => (
              <Table.Tr key={i}>
                <Table.Td>{s.text}</Table.Td>
                <Table.Td ff="monospace">{s.field}</Table.Td>
                <Table.Td ff="monospace">
                  {String(s.before)} → {String(s.after)}
                  {s.contrastBefore != null && s.contrastAfter != null && (
                    <Text size="xs" c="dimmed" ff="monospace">
                      kontrast {fmtContrast(s.contrastBefore)} → {fmtContrast(s.contrastAfter)}
                    </Text>
                  )}
                  {s.relSizeBefore != null && s.relSizeAfter != null && (
                    <Text size="xs" c="dimmed" ff="monospace">
                      rozmiar wzgl. {fmtRel(s.relSizeBefore)} → {fmtRel(s.relSizeAfter)}
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>{s.viewport}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      {(c.from.screenshots || c.to.screenshots) && (
        <SimpleGrid cols={2}>
          {[c.from, c.to].map((s) => (
            <Stack key={s.id} gap={4}>
              {Object.entries(s.screenshots ?? {}).map(([vp, path]) => {
                const src = `${API_URL}/screens/${path.split('/').pop()}`;
                return (
                  <Anchor key={vp} href={src} target="_blank" rel="noreferrer" size="xs">
                    {s === c.from ? 'Przed' : 'Po'} · {vp}
                    <img src={src} alt="" style={{ display: 'block', width: '100%', maxHeight: 240, objectFit: 'cover', objectPosition: 'top' }} />
                  </Anchor>
                );
              })}
            </Stack>
          ))}
        </SimpleGrid>
      )}
    </Stack>
  );
}

// ---------------------------------------------------------------------------
// Oś czasu zmian i lista alertów
// ---------------------------------------------------------------------------

export function ChangeTimeline({ changes, onOpen }: { changes: (PageChange & { label: string })[]; onOpen: (id: string) => void }) {
  if (!changes.length)
    return (
      <Text size="sm" c="dimmed">
        Brak wykrytych zmian: kolejne zrzuty są identyczne.
      </Text>
    );
  return (
    <div className="iw-timeline">
      {changes.map((c) => (
        <div key={c.id} className="iw-timeline-item">
          <UnstyledButton onClick={() => onOpen(c.id)} className="iw-timeline-card" w="100%">
            <Group gap={6}>
              <Text size="xs" c="dimmed">
                {fmtDateTime(c.detectedAt)} · {fmtRelative(c.detectedAt)}
              </Text>
              {c.mock && <MockBadge hint="Zmiana wobec zrzutu zrekonstruowanego syntetycznie" />}
            </Group>
            <Text size="sm" fw={600} mt={2}>
              {c.summary}
            </Text>
            <Text size="xs" c="dimmed">
              {c.label}
            </Text>
          </UnstyledButton>
        </div>
      ))}
    </div>
  );
}

export function pageChanges(pages: MonitoredPage[]) {
  return pages.flatMap((p) => p.changes.map((c) => ({ ...c, label: p.label, url: p.url }))).sort((a, b) => b.detectedAt.localeCompare(a.detectedAt));
}

export function AlertRows({ alerts, onOpen }: { alerts: EntityAlert[]; onOpen?: (a: EntityAlert) => void }) {
  if (!alerts.length)
    return (
      <Text size="sm" c="dimmed">
        Brak alertów.
      </Text>
    );
  return (
    <Stack gap={0}>
      {alerts.map((a) => (
        <UnstyledButton key={a.id} onClick={() => onOpen?.(a)} className="iw-alert-row">
          <Group gap={8} wrap="nowrap" align="flex-start">
            <SeverityBadge s={a.severity} />
            <Box style={{ minWidth: 0, flex: 1 }}>
              <Text size="sm" lineClamp={2}>
                {a.title}
              </Text>
              <Text size="xs" c="dimmed">
                Wynik klasyfikatora · {fmtRelative(a.createdAt)}
              </Text>
            </Box>
            {a.status === 'new' ? (
              <Badge size="xs" variant="filled">
                nowy
              </Badge>
            ) : (
              <Badge size="xs" variant="default">
                {a.status === 'ack' ? 'przyjęty' : 'zamknięty'}
              </Badge>
            )}
          </Group>
        </UnstyledButton>
      ))}
    </Stack>
  );
}
