import type { Evidence, EvidenceSection, Finding, FlagKey, Thresholds } from '../api/types';
import { API_URL } from '../api/client';
import { ALL_FLAGS, FLAG_COLOR, POSITIVE_FLAGS, SCAM_FLAGS, SCAM_SIGNAL_LABEL, SCAM_THRESHOLD_KEY } from './labels';

export type ThresholdValues = Thresholds['values'];

export function thresholdOf(values: ThresholdValues | undefined, key: string, fallback = 0.5): number {
  return values?.[key] ?? fallback;
}

export function flagThreshold(values: ThresholdValues | undefined, flag: FlagKey): number {
  return thresholdOf(values, `flags.${flag}`);
}

export function scamThreshold(values: ThresholdValues | undefined): number {
  return thresholdOf(values, SCAM_THRESHOLD_KEY, 0.6);
}

export function isScam(f: Finding, values: ThresholdValues | undefined): boolean {
  return f.scam.p >= scamThreshold(values);
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
  landingIndex?: number,
  only?: readonly FlagKey[],
): Span[] {
  const spans: Span[] = [];
  for (const flag of only ?? ALL_FLAGS) {
    const score = f.flags[flag];
    if (!score || score.p < flagThreshold(values, flag)) continue;
    for (const e of score.evidence) {
      if (e.section !== section) continue;
      if (section === 'landing' && (e.landingIndex ?? 0) !== (landingIndex ?? 0)) continue;
      if (e.end > e.start) spans.push({ flag, start: e.start, end: e.end, p: score.p, color: FLAG_COLOR[flag] });
    }
  }
  return spans;
}

export interface Quote {
  flags: FlagKey[];
  ev: Evidence;
}

/** Fragmenty z cechami oszustwa ze wszystkich sekcji (tekst, transkrypcja, OCR, landing), bez duplikatów. */
export function scamQuotes(f: Finding, values: ThresholdValues | undefined): Quote[] {
  const byKey = new Map<string, Quote>();
  for (const flag of SCAM_FLAGS) {
    const score = f.flags[flag];
    if (!score || score.p < flagThreshold(values, flag)) continue;
    for (const ev of score.evidence) {
      const k = `${ev.section}:${ev.landingIndex ?? ''}:${ev.t ?? ''}:${ev.start}:${ev.end}`;
      const q = byKey.get(k);
      if (q) q.flags.push(flag);
      else byKey.set(k, { flags: [flag], ev });
    }
  }
  return [...byKey.values()];
}

/** Sekcja, w której flaga ma pierwszy dowód (do przewinięcia / przełączenia zakładki). */
export function firstEvidence(f: Finding, flag: FlagKey): Evidence | undefined {
  return f.flags[flag]?.evidence[0];
}

/**
 * Sygnały oszustwa po polsku, z konkretami z rekordu (marka, domena, podmiot).
 * Backend nie zwraca szczegółów sygnału, więc składamy je ze wskaźników i podmiotów rekordu.
 */
export function scamSignalTexts(f: Finding): string[] {
  const domains = f.indicators.filter((i) => i.type === 'domain').map((i) => i.value);
  const brands = f.indicators.filter((i) => i.type === 'brand').map((i) => i.value);
  const warned = f.entities.filter((e) => e.knfRegister.status === 'ON_WARNING_LIST').map((e) => e.name);
  const unregistered = f.entities.filter((e) => e.knfRegister.status === 'NOT_FOUND' && e.role !== 'advertiser').map((e) => e.name);
  return f.scam.signals.map((s) => {
    switch (s) {
      case 'IMPERSONATION':
        return brands.length && domains.length
          ? `Podszywanie się: wymienia markę ${brands.join(', ')}, link prowadzi do domeny ${domains.join(', ')}`
          : SCAM_SIGNAL_LABEL[s];
      case 'CERT_LIST_DOMAIN':
        return domains.length ? `Domena na liście ostrzeżeń CERT Polska: ${domains.join(', ')}` : SCAM_SIGNAL_LABEL[s];
      case 'KNF_WARNING_LIST':
        return warned.length ? `Na liście ostrzeżeń publicznych KNF: ${warned.join(', ')}` : SCAM_SIGNAL_LABEL[s];
      case 'NOT_IN_REGISTER':
        return unregistered.length ? `Oferuje usługi inwestycyjne, brak w rejestrze KNF: ${unregistered.join(', ')}` : SCAM_SIGNAL_LABEL[s];
      default:
        return SCAM_SIGNAL_LABEL[s];
    }
  });
}

/** Domeny uznane za podejrzane: flagi domenowe ze stron docelowych albo sygnał domenowy rekordu. */
export function suspiciousDomains(f: Finding): Set<string> {
  const out = new Set<string>();
  for (const lp of f.landingPages) {
    if (lp.domainFlags.length) {
      out.add(domainOf(lp.finalUrl));
      lp.redirectChain.slice(1).forEach((u) => out.add(domainOf(u)));
    }
  }
  if (f.scam.signals.some((s) => s === 'IMPERSONATION' || s === 'CERT_LIST_DOMAIN' || s === 'KNF_WARNING_LIST')) {
    f.indicators.filter((i) => i.type === 'domain').forEach((i) => out.add(i.value));
  }
  return out;
}
