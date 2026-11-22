// Generator danych mocka: ok. 300 rekordów z ostatnich 30 dni, kampanie, eval-set.
// Uruchomiony bezpośrednio (`npm run seed`) zapisuje fixture do mock-server/data/seed.json.

import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import type {
  Campaign,
  ContentType,
  EvalItem,
  Evidence,
  Finding,
  FlagKey,
  FlagScore,
  Indicator,
  Instrument,
  Platform,
  Status,
  Thresholds,
  TopicLabel,
} from '../src/api/types';
import {
  ANALYSTS,
  CAMPAIGNS,
  type CampaignDef,
  type Category,
  type Draft,
  campaignDraft,
  education,
  financialOther,
  firmMarketing,
  nonFinancial,
  opinion,
  recommendation,
  scamAwareness,
  serviceOffer,
  standaloneScam,
  thirdPartyPromo,
} from './content';
import { buildLanding, buildMedia } from './enrich';
import { computeRelated, indexFinding } from './graph';
import { Rng, clamp, round3 } from './rng';
import { CONTENT_TYPE_KEYS, FLAG_KEYS, THRESHOLD_KEYS, defaultThresholdValues, rescore } from './scoring';

const DAY = 24 * 3600 * 1000;
const HOUR = 3600 * 1000;
const MODEL_VERSION = 'iw-clf-0.3.1+bge-m3';
const SHORTENERS = new Set(['skroc.to']);

const TOPIC_KEYS: TopicLabel[] = ['NON_FINANCIAL', 'FINANCIAL_OTHER', 'INVESTMENT'];
const INSTRUMENT_KEYS: Instrument[] = ['CFD_FOREX', 'STOCKS', 'FUNDS_ETF', 'BONDS', 'CRYPTO', 'OTHER_DERIVATIVES', 'NON_INSTRUMENT'];

export interface World {
  rng: Rng;
  seq: number;
  findings: Finding[]; // posortowane malejąco po fetchedAt
  byId: Map<string, Finding>;
  index: Map<string, Set<string>>; // `${type}:${value}` -> id rekordów
  members: Map<string, string[]>; // campaignId -> id rekordów
  campaigns: Map<string, Campaign>;
  defs: Map<string, Pick<CampaignDef, 'name' | 'status'>>;
  evalSet: EvalItem[];
  thresholds: Thresholds;
}

// ---------------------------------------------------------------------------
// Tekst + evidence
// ---------------------------------------------------------------------------

/** Styl ASR: małe litery, bez interpunkcji, emoji i hashtagów. */
export function toAsr(text: string): string {
  return text
    .toLowerCase()
    .replace(/https?:\/\/\S+/g, ' ')
    .replace(/#\S+/g, ' ')
    .replace(/%/g, ' procent')
    .replace(/\p{Extended_Pictographic}|\u{FE0F}|\u{200D}/gu, ' ')
    .replace(/[.,!?;:„”"…()[\]–—\-*/|&+]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

interface Built {
  text: string;
  transcript?: string;
  strong: Map<FlagKey, Evidence[]>;
  weak: Map<FlagKey, Evidence[]>;
}

/** Posty: segmenty w `text`. Wideo: segmenty w transkrypcji (styl ASR), `text` to krótki opis pod filmem. */
function buildText(d: Draft, caption: string): Built {
  const asr = d.kind === 'transcript';
  const section: Evidence['section'] = asr ? 'transcript' : 'text';
  let body = '';
  const strong = new Map<FlagKey, Evidence[]>();
  const weak = new Map<FlagKey, Evidence[]>();
  for (const seg of d.segs) {
    const t = asr ? toAsr(seg.text) : seg.text.trim();
    if (!t) continue;
    if (body.length) body += asr ? ' ' : d.sep;
    const start = body.length;
    body += t;
    const ev: Evidence = { section, start, end: start + t.length, text: t, ...(asr ? { t: Math.round(start / 14) } : {}) };
    for (const f of seg.flags ?? []) strong.set(f, [...(strong.get(f) ?? []), ev]);
    for (const f of seg.weak ?? []) weak.set(f, [...(weak.get(f) ?? []), ev]);
  }
  for (const map of [strong, weak]) {
    for (const evs of map.values()) {
      for (const e of evs) {
        if (body.slice(e.start, e.end) !== e.text) throw new Error(`Złe offsety evidence: ${e.text}`);
      }
    }
  }
  return asr ? { text: caption, transcript: body, strong, weak } : { text: body, strong, weak };
}

function distribution<K extends string>(rng: Rng, keys: K[], main: K, lo: number, hi: number): Record<K, number> {
  const out = {} as Record<K, number>;
  const top = rng.range(lo, hi);
  const rest = keys.filter((k) => k !== main);
  const raw = rest.map(() => rng.next() ** 2 + 0.05);
  const sum = raw.reduce((a, b) => a + b, 0);
  out[main] = round3(top);
  rest.forEach((k, i) => (out[k] = round3(((1 - top) * raw[i]) / sum)));
  return out;
}

function postUrl(rng: Rng, platform: Platform, handle: string, links: string[]): string {
  const h = handle.replace(/^@/, '');
  const n = () => String(rng.int(1e8, 9e8)) + String(rng.int(1e8, 9e8));
  const code = () => Array.from({ length: 11 }, () => 'abcdefghijklmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ0123456789_-'[rng.int(0, 63)]).join('');
  switch (platform) {
    case 'facebook':
      return `https://www.facebook.com/${h}/posts/${n()}`;
    case 'instagram':
      return `https://www.instagram.com/p/${code()}/`;
    case 'tiktok':
      return `https://www.tiktok.com/@${h}/video/${n()}`;
    case 'youtube':
      return `https://www.youtube.com/watch?v=${code()}`;
    case 'x':
      return `https://x.com/${h}/status/${n()}`;
    case 'web':
      return links.find((l) => !SHORTENERS.has(new URL(l).hostname)) ?? `https://${h.replace(/[^a-z0-9]/gi, '')}.pl/`;
    default:
      return `https://example.org/${h}`;
  }
}

function hostname(url: string): string | null {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return null;
  }
}

const YT_TITLES = ['Mój portfel po roku', 'Jak zacząć inwestować w 2026', 'Q&A: wasze pytania o finanse', 'Vlog: tydzień z życia tradera'];
const CAPTION_TAGS = ['#inwestowanie #finanse', '#giełda #pieniądze', '#krypto #zarabianie', '#oszczędzanie'];

export function draftToFinding(world: World, d: Draft, fetchedAt: Date): Finding {
  const rng = world.rng;
  let title = d.title;
  if (!title && d.platform === 'youtube') title = rng.pick(YT_TITLES);
  if (!title && d.kind === 'page') title = d.entities[0]?.name ?? 'Strona oferty';
  const caption = d.category === 'NON_FIN' ? (title ?? 'Nowy film 🎬') : `${title ?? 'Nowy film'} ${rng.pick(CAPTION_TAGS)}`;
  const { text, transcript, strong, weak } = buildText(d, caption);

  world.seq += 1;
  const id = `F-${String(world.seq).padStart(4, '0')}`;

  // wzbogacenia: strona docelowa (ok. 40% inwestycyjnych z linkiem), wideo (ok. 30%, scamy częściej)
  const sink = (flag: FlagKey, ev: Evidence) => strong.set(flag, [...(strong.get(flag) ?? []), ev]);
  const investment = d.topic === 'INVESTMENT' && d.links.length > 0;
  const landingPages = investment && rng.chance(d.category === 'SCAM' ? 0.6 : 0.3) ? buildLanding(rng, d, id, sink) : [];
  const media = transcript && rng.chance(d.category === 'SCAM' ? 0.6 : 0.25) ? buildMedia(rng, d, id, transcript.length, sink) : undefined;

  const flags = {} as Record<FlagKey, FlagScore>;
  for (const key of FLAG_KEYS) {
    const se = strong.get(key);
    const we = weak.get(key);
    if (se) flags[key] = { p: round3(rng.range(0.66, 0.98)), evidence: se };
    else if (we) flags[key] = { p: round3(rng.range(0.34, 0.64)), evidence: we };
    else flags[key] = { p: round3(rng.next() ** 3 * 0.3), evidence: [] };
  }

  const topic = distribution(rng, TOPIC_KEYS, d.topic, 0.75, 0.97);
  const contentType = distribution<ContentType>(rng, CONTENT_TYPE_KEYS, d.contentType, 0.55, 0.92);
  const instruments = {} as Record<Instrument, number>;
  for (const k of INSTRUMENT_KEYS) instruments[k] = round3(d.instruments.includes(k) ? rng.range(0.6, 0.95) : rng.range(0.01, 0.2));

  const indicators: Indicator[] = [{ type: 'author', value: d.author.handle }];
  const seen = new Set<string>(['author:' + d.author.handle]);
  const addInd = (i: Indicator) => {
    const k = `${i.type}:${i.value}`;
    if (!seen.has(k)) {
      seen.add(k);
      indicators.push(i);
    }
  };
  for (const l of d.links) {
    const h = hostname(l);
    if (h && !SHORTENERS.has(h)) addInd({ type: 'domain', value: h });
  }
  d.extraIndicators.forEach(addInd);

  const scamP = round3(rng.range(d.scam[0], d.scam[1]));
  const base = {
    id,
    url: postUrl(rng, d.platform, d.author.handle, d.links),
    platform: d.platform,
    kind: d.kind,
    author: d.author,
    title,
    text,
    transcript,
    landingPages,
    media,
    publishedAt: new Date(fetchedAt.getTime() - rng.range(0.2, 30) * HOUR).toISOString(),
    fetchedAt: fetchedAt.toISOString(),
    topic,
    contentType,
    instruments,
    flags,
    entities: d.entities,
    outboundLinks: d.links,
    scam: { p: scamP, signals: scamP >= 0.5 ? d.signals : d.signals.filter((s) => s !== 'TEXT_MODEL') },
    indicators,
    campaignId: d.campaignId,
    related: [],
    status: 'NEW' as Status,
    history: [{ at: fetchedAt.toISOString(), status: 'NEW' as Status, user: 'system' }],
    modelVersion: MODEL_VERSION,
  };
  const scored = rescore(base, world.thresholds.values);
  return { ...base, ...scored };
}

// ---------------------------------------------------------------------------
// Statusy i historia dla rekordów z seeda
// ---------------------------------------------------------------------------

const COMMENTS: Partial<Record<Status, string[]>> = {
  IN_REVIEW: ['Weryfikacja podmiotu w rejestrze KNF.', 'Sprawdzam powiązane domeny.'],
  CONFIRMED: [
    'Potwierdzone, schemat zgodny z kampanią.',
    'Brak ostrzeżenia o ryzyku przy obietnicy zysku.',
    'Podmiot spoza rejestru oferuje doradztwo.',
  ],
  DISMISSED: ['Materiał edukacyjny, brak naruszenia.', 'Cytat w kontekście ostrzeżenia przed oszustwem.', 'Podmiot posiada zezwolenie.'],
  ESCALATED: ['Przekazano do Departamentu Prawnego.', 'Domeny zgłoszone do CERT Polska.'],
};

function assignStatus(world: World, f: Finding, category: Category, now: Date): void {
  const rng = world.rng;
  const ageDays = (now.getTime() - new Date(f.fetchedAt).getTime()) / DAY;
  if (ageDays < 1.5) return;
  let status: Status;
  if (category === 'SCAM') status = rng.weighted<Status>([['NEW', 3], ['IN_REVIEW', 2], ['CONFIRMED', 5], ['ESCALATED', 1]]);
  else if (f.riskLevel === 'LOW') status = rng.weighted<Status>([['NEW', 9], ['DISMISSED', 1]]);
  else if (['NON_FIN', 'FIN_OTHER', 'EDU', 'SCAM_AWARE', 'OPINION'].includes(category))
    status = rng.weighted<Status>([['NEW', 5], ['DISMISSED', 3], ['IN_REVIEW', 1]]);
  else status = rng.weighted<Status>([['NEW', 4], ['IN_REVIEW', 2], ['CONFIRMED', 2], ['DISMISSED', 1], ['ESCALATED', 1]]);
  if (status === 'NEW') return;

  const user = rng.pick(ANALYSTS);
  const t0 = new Date(f.fetchedAt).getTime();
  const span = Math.min(ageDays - 0.5, 4) * DAY;
  if (status !== 'IN_REVIEW' && rng.chance(0.6)) {
    f.history.push({ at: new Date(t0 + span * 0.3).toISOString(), status: 'IN_REVIEW', user });
  }
  const comments = COMMENTS[status];
  f.history.push({
    at: new Date(t0 + span * rng.range(0.5, 1)).toISOString(),
    status,
    user,
    comment: comments && rng.chance(0.8) ? rng.pick(comments) : undefined,
  });
  f.status = status;
}

// ---------------------------------------------------------------------------
// Kampanie
// ---------------------------------------------------------------------------

export function recomputeCampaign(world: World, id: string): Campaign | undefined {
  const def = world.defs.get(id);
  const ids = world.members.get(id) ?? [];
  const members = ids.map((x) => world.byId.get(x)).filter((x): x is Finding => !!x);
  if (!def || members.length === 0) return undefined;
  const times = members.map((m) => m.fetchedAt).sort();
  const freq = new Map<string, { ind: Indicator; n: number }>();
  for (const m of members) {
    for (const ind of m.indicators) {
      if (ind.type === 'author') continue;
      const k = `${ind.type}:${ind.value}`;
      freq.set(k, { ind, n: (freq.get(k)?.n ?? 0) + 1 });
    }
  }
  const campaign: Campaign = {
    id,
    name: def.name,
    size: members.length,
    // udział potwierdzonych lub wysokich scamów
    scamShare: round3(
      members.filter((m) => m.scam.p >= 0.75 || (m.status === 'CONFIRMED' && m.scam.p >= 0.5)).length / members.length,
    ),
    avgScam: round3(members.reduce((s, m) => s + m.scam.p, 0) / members.length),
    firstSeen: times[0],
    lastSeen: times[times.length - 1],
    platforms: [...new Set(members.map((m) => m.platform))],
    topIndicators: [...freq.values()].sort((a, b) => b.n - a.n).slice(0, 5).map((x) => x.ind),
    status: world.campaigns.get(id)?.status ?? def.status,
  };
  world.campaigns.set(id, campaign);
  return campaign;
}

function addFinding(world: World, f: Finding): void {
  world.byId.set(f.id, f);
  indexFinding(world, f);
  if (f.campaignId) world.members.set(f.campaignId, [...(world.members.get(f.campaignId) ?? []), f.id]);
}

// ---------------------------------------------------------------------------
// Eval-set (gold) – prawdopodobieństwa skorelowane z etykietami
// ---------------------------------------------------------------------------

function hashKey(key: string): number {
  let h = 2166136261;
  for (let i = 0; i < key.length; i++) h = Math.imul(h ^ key.charCodeAt(i), 16777619);
  return (h >>> 0) / 4294967296;
}

function buildEvalSet(rng: Rng, n = 200): EvalItem[] {
  const items: EvalItem[] = [];
  const levelCenters = [0.22, 0.52, 0.74, 0.9];
  for (let i = 0; i < n; i++) {
    const level = rng.weighted<number>([[0, 40], [1, 25], [2, 20], [3, 15]]);
    const riskScore = clamp(rng.normal(levelCenters[level], 0.1));
    const probs: Record<string, number> = {};
    const gold: Record<string, 0 | 1> = {};
    for (const key of THRESHOLD_KEYS) {
      if (key.startsWith('risk.')) {
        const idx = ['risk.MEDIUM', 'risk.HIGH', 'risk.CRITICAL'].indexOf(key) + 1;
        probs[key] = round3(riskScore);
        gold[key] = level >= idx ? 1 : 0;
        continue;
      }
      const h = hashKey(key);
      const rate = key === 'scam.p' ? 0.3 : 0.15 + h * 0.22;
      const sep = key === 'scam.p' ? 0.55 : 0.32 + ((h * 7) % 1) * 0.3;
      const sigma = 0.15 + ((h * 13) % 1) * 0.05;
      const g: 0 | 1 = rng.chance(rate) ? 1 : 0;
      probs[key] = round3(clamp(rng.normal(g ? 0.5 + sep / 2 : 0.5 - sep / 2, sigma)));
      gold[key] = g;
    }
    items.push({ id: `E-${String(i + 1).padStart(3, '0')}`, probs, gold });
  }
  return items;
}

// ---------------------------------------------------------------------------
// Świat
// ---------------------------------------------------------------------------

const STANDALONE: [Category, number, (rng: Rng) => Draft][] = [
  ['NON_FIN', 64, nonFinancial],
  ['FIN_OTHER', 12, financialOther],
  ['EDU', 28, education],
  ['SCAM_AWARE', 8, scamAwareness],
  ['OPINION', 10, opinion],
  ['FIRM', 22, (r) => firmMarketing(r)],
  ['PROMO', 22, (r) => thirdPartyPromo(r)],
  ['RECO', 8, recommendation],
  ['OFFER', 18, serviceOffer],
  ['SCAM', 5, standaloneScam],
];

export function createWorld(seed: number, now: Date): World {
  const rng = new Rng(seed);
  const world: World = {
    rng,
    seq: 0,
    findings: [],
    byId: new Map(),
    index: new Map(),
    members: new Map(),
    campaigns: new Map(),
    defs: new Map(CAMPAIGNS.map((c) => [c.id, c])),
    evalSet: [],
    thresholds: { version: 'v1', updatedAt: now.toISOString(), values: defaultThresholdValues() },
  };

  const pending: { draft: Draft; at: Date }[] = [];
  for (const [, count, make] of STANDALONE) {
    for (let i = 0; i < count; i++) {
      const daysAgo = 30 * rng.next() ** 1.15;
      pending.push({ draft: make(rng), at: new Date(now.getTime() - daysAgo * DAY - rng.range(0, 1) * HOUR) });
    }
  }
  for (const c of CAMPAIGNS) {
    for (let i = 0; i < c.size; i++) {
      const daysAgo = rng.range(c.daysAgoEnd, c.daysAgoStart) + rng.range(0, 0.9);
      pending.push({ draft: campaignDraft(rng, c), at: new Date(now.getTime() - Math.max(daysAgo, 0.02) * DAY) });
    }
  }
  pending.sort((a, b) => a.at.getTime() - b.at.getTime());

  for (const { draft, at } of pending) {
    const f = draftToFinding(world, draft, at);
    assignStatus(world, f, draft.category, now);
    addFinding(world, f);
  }
  world.findings = [...world.byId.values()].sort((a, b) => b.fetchedAt.localeCompare(a.fetchedAt));
  for (const f of world.findings) f.related = computeRelated(world, f);
  for (const c of CAMPAIGNS) recomputeCampaign(world, c.id);
  world.evalSet = buildEvalSet(rng);
  return world;
}

/** Nowy rekord „z produkcji” dla socketu. Czasem dołącza do istniejącej kampanii. */
export function createLiveFinding(world: World, now: Date): { finding: Finding; campaign?: Campaign } {
  const rng = world.rng;
  let draft: Draft;
  const roll = rng.next();
  const active = CAMPAIGNS.filter((c) => world.campaigns.get(c.id)?.status !== 'CLOSED');
  if (roll < 0.4 && active.some((c) => c.scam)) {
    const def = rng.weighted(active.filter((c) => c.scam).map((c) => [c, c.size] as const));
    draft = campaignDraft(rng, def);
  } else if (roll < 0.47 && active.some((c) => !c.scam)) {
    draft = campaignDraft(rng, rng.pick(active.filter((c) => !c.scam)));
  } else {
    const [, , make] = rng.weighted(STANDALONE.map((e) => [e, e[0] === 'NON_FIN' ? 20 : e[1]] as const));
    draft = make(rng);
  }
  const finding = draftToFinding(world, draft, now);
  addFinding(world, finding);
  world.findings.unshift(finding);
  finding.related = computeRelated(world, finding);
  for (const r of finding.related) {
    const other = world.byId.get(r.findingId);
    if (other) other.related = computeRelated(world, other);
  }
  const campaign = finding.campaignId ? recomputeCampaign(world, finding.campaignId) : undefined;
  return { finding, campaign };
}

/** Przeliczenie reguł, modułów i ryzyka wszystkich rekordów po zmianie progów. */
export function applyThresholds(world: World, values: Record<string, number>, now: Date): Thresholds {
  const n = Number(world.thresholds.version.replace(/\D/g, '')) || 1;
  world.thresholds = { version: `v${n + 1}`, updatedAt: now.toISOString(), values: { ...world.thresholds.values, ...values } };
  for (const f of world.findings) Object.assign(f, rescore(f, world.thresholds.values));
  return world.thresholds;
}

// CLI: `npm run seed` zapisuje fixture do mock-server/data/seed.json
if (process.argv[1]?.replace(/\\/g, '/').endsWith('mock-server/seed.ts')) {
  const world = createWorld(Number(process.env.MOCK_SEED ?? 42), new Date());
  const dir = join(process.cwd(), 'mock-server', 'data');
  mkdirSync(dir, { recursive: true });
  const out = join(dir, 'seed.json');
  writeFileSync(
    out,
    JSON.stringify(
      { thresholds: world.thresholds, findings: world.findings, campaigns: [...world.campaigns.values()], evalSet: world.evalSet },
      null,
      2,
    ),
  );
  process.stdout.write(`Zapisano ${world.findings.length} rekordów, ${world.campaigns.size} kampanii do ${out}\n`);
}