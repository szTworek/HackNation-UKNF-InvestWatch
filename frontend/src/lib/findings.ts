import type { Evidence, EvidenceSection, Finding, FlagKey, Thresholds } from '../api/types';
import { API_URL } from '../api/client';
import { ALL_FLAGS, FLAG_COLOR, POSITIVE_FLAGS } from './labels';

export type ThresholdValues = Thresholds['values'];

export function thresholdOf(values: ThresholdValues | undefined, key: string, fallback = 0.5): number {
  return values?.[key] ?? fallback;
}

export function flagThreshold(values: ThresholdValues | undefined, flag: FlagKey): number {
  return thresholdOf(values, `flags.${flag}`);
}

export interface FlagHit {
  flag: FlagKey;
  p: number;
}

/** Flagi powyżej progu, od najwyższego p. */
export function activeFlags(f: Finding, values: ThresholdValues | undefined, kind: 'risk' | 'positive' = 'risk'): FlagHit[] {
  return ALL_FLAGS.filter((k) => (kind === 'positive' ? POSITIVE_FLAGS.has(k) : !POSITIVE_FLAGS.has(k)))
    .map((k) => ({ flag: k, p: f.flags[k]?.p ?? 0 }))
    .filter((h) => h.p >= flagThreshold(values, h.flag))
    .sort((a, b) => b.p - a.p);
}

export function snippet(text: string, max = 140): string {
  const t = text.replace(/\s+/g, ' ').trim();
  return t.length > max ? `${t.slice(0, max - 1).trimEnd()}…` : t;
}

export function domainOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

/** Ścieżki zasobów z API (np. `/api/assets/...`) zamieniane na pełny URL serwera API. */
export function assetUrl(path: string): string {
  try {
    return new URL(path, new URL(API_URL).origin).href;
  } catch {
    return path;
  }
}

export interface Span {
  flag: FlagKey;
  start: number;
  end: number;
  p: number;
  color: string;
}

/** Fragmenty-dowody flag powyżej progu w jednej sekcji (do podświetlenia). */
export function evidenceSpans(
  f: Finding,
  values: ThresholdValues | undefined,
  section: EvidenceSection,
  only?: readonly FlagKey[],
): Span[] {
  const spans: Span[] = [];
  for (const flag of only ?? ALL_FLAGS) {
    const score = f.flags[flag];
    if (!score || score.p < flagThreshold(values, flag)) continue;
    for (const e of score.evidence) {
      if (e.section !== section) continue;
      if (e.end > e.start) spans.push({ flag, start: e.start, end: e.end, p: score.p, color: FLAG_COLOR[flag] });
    }
  }
  return spans;
}

/** Sekcja, w której flaga ma pierwszy dowód (do przewinięcia / przełączenia zakładki). */
export function firstEvidence(f: Finding, flag: FlagKey): Evidence | undefined {
  return f.flags[flag]?.evidence[0];
}
