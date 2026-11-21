import { Text, Tooltip } from '@mantine/core';
import { Fragment, useMemo } from 'react';
import type { FlagKey } from '../api/types';
import type { Span } from '../lib/findings';
import { fmtProb } from '../lib/format';
import { FLAG_LABEL } from '../lib/labels';

interface Props {
  text: string;
  spans: Span[];
  activeFlag?: FlagKey | null;
  /** prefiks id kotwic: `${idPrefix}-${flag}` na pierwszym fragmencie flagi */
  idPrefix?: string;
}

interface Piece {
  start: number;
  end: number;
  spans: Span[];
}

function split(text: string, spans: Span[]): Piece[] {
  const cuts = new Set<number>([0, text.length]);
  for (const s of spans) {
    cuts.add(s.start);
    cuts.add(s.end);
  }
  const points = [...cuts].sort((a, b) => a - b);
  const pieces: Piece[] = [];
  for (let i = 0; i < points.length - 1; i++) {
    const start = points[i];
    const end = points[i + 1];
    if (end <= start) continue;
    pieces.push({ start, end, spans: spans.filter((s) => s.start <= start && s.end >= end).sort((a, b) => b.p - a.p) });
  }
  return pieces;
}

/** Tekst z podświetlonymi fragmentami-dowodami. Każda flaga ma swój kolor; nakładające się fragmenty pokazują wszystkie flagi w tooltipie. */
export function HighlightedText({ text, spans, activeFlag, idPrefix = 'ev' }: Props) {
  const pieces = useMemo(() => split(text, spans), [text, spans]);
  const anchored = new Set<FlagKey>();
  return (
    <Text component="div" size="sm" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
      {pieces.map((piece) => {
        const chunk = text.slice(piece.start, piece.end);
        if (!piece.spans.length) return <Fragment key={piece.start}>{chunk}</Fragment>;
        const main = piece.spans[0];
        const active = !!activeFlag && piece.spans.some((s) => s.flag === activeFlag);
        const anchorFlag = piece.spans.find((s) => !anchored.has(s.flag) && s.start === piece.start)?.flag;
        if (anchorFlag) anchored.add(anchorFlag);
        return (
          <Tooltip
            key={piece.start}
            withArrow
            multiline
            label={piece.spans.map((s) => `${FLAG_LABEL[s.flag]}: ${fmtProb(s.p)}`).join('\n')}
            style={{ whiteSpace: 'pre-line' }}
          >
            <mark
              id={anchorFlag ? `${idPrefix}-${anchorFlag}` : undefined}
              data-flags={piece.spans.map((s) => s.flag).join(' ')}
              style={{
                backgroundColor: `var(--mantine-color-${main.color}-light)`,
                borderBottom: `2px solid var(--mantine-color-${main.color}-6)`,
                outline: active ? `2px solid var(--mantine-color-${main.color}-7)` : undefined,
                borderRadius: 2,
                padding: '0 1px',
                color: 'inherit',
                scrollMarginTop: 120,
              }}
            >
              {chunk}
            </mark>
          </Tooltip>
        );
      })}
    </Text>
  );
}
