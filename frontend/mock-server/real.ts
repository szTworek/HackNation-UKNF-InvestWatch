// Tryb DATA_MODE=real: świat z findings.real.json (ml/scripts/build_findings.py), wyniki progów z ai-service.
// Ten moduł niczego nie generuje. Brak danych kończy start serwera błędem.

import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
import type { Campaign, EvalItem, Evidence, Finding, HistoryEntry, Indicator, RiskLevel, Status, Thresholds } from '../src/api/types';
import { indexFinding } from './graph';
import { Rng } from './rng';
import { defaultThresholdValues } from './scoring';
import { recomputeCampaign, type World } from './seed';

const REPLAY_SIZE = 20;
const REPLAY_HIGH_RISK = 6;
const AI_TIMEOUT_MS = 120_000;

type StoredFinding = Finding & { scoringInput?: unknown };

interface RealCampaign {
  id: string;
  name: string;
  memberIds?: string[];
  topIndicators?: Indicator[];
}

interface RealFile {
  generatedAt: string;
  modelVersion: string;
  thresholds?: Pick<Thresholds, 'values'> & Partial<Thresholds>;
  findings: StoredFinding[];
  campaigns?: RealCampaign[];
}

interface SavedState {
  statuses?: Record<string, { status: Status; history: HistoryEntry[] }>;
  thresholds?: Thresholds;
}

export interface RealData {
  world: World;
  held: Finding[]; // rekordy trybu DEMO_REPLAY, jeszcze niepokazane
  scoringInputs: Map<string, unknown>;
  certBlocked: Map<string, string[]>;
  savedThresholds?: Thresholds;
  generatedAt: string;
  modelVersion: string;
}

export interface RescoreResult {
  itemId: string;
  rules: Finding['rules'];
  modules: Finding['modules'];
  riskScore: number;
  riskLevel: RiskLevel;
  scam: Finding['scam'];
}

function readState(path: string): SavedState {
  if (!existsSync(path)) return {};
  try {
    return JSON.parse(readFileSync(path, 'utf8')) as SavedState;
  } catch (e) {
    throw new Error(`Nie można odczytać stanu ${path}: ${(e as Error).message}`, { cause: e });
  }
}

/** ai-service liczy offsety w znakach Unicode, a JavaScript w jednostkach UTF-16 (emoji zajmuje dwie). */
function utf16Index(text: string): number[] | null {
  if (!/[\uD800-\uDFFF]/.test(text)) return null;
  const index = [0];
  let position = 0;
  for (const ch of text) {
    position += ch.length;
    index.push(position);
  }
  return index;
}

function toUtf16(evidence: Evidence[], index: number[] | null): Evidence[] {
  if (!index) return evidence;
  return evidence.map((e) => ({ ...e, start: index[e.start] ?? e.start, end: index[e.end] ?? e.end }));
}

function withUtf16Evidence(f: Finding): Finding {
  const index = utf16Index(f.text);
  if (!index) return f;
  const flags = Object.fromEntries(
    Object.entries(f.flags).map(([key, score]) => [key, { ...score, evidence: toUtf16(score.evidence, index) }]),
  ) as Finding['flags'];
  return { ...f, flags, rules: f.rules.map((r) => ({ ...r, evidence: toUtf16(r.evidence, index) })) };
}

function pickReplay(findings: Finding[]): Set<string> {
  const size = Math.min(REPLAY_SIZE, Math.floor(findings.length / 2));
  const ordered = [...findings].sort((a, b) => a.id.localeCompare(b.id));
  const high = ordered.filter((f) => f.riskLevel === 'HIGH' || f.riskLevel === 'CRITICAL').slice(0, Math.min(REPLAY_HIGH_RISK, size));
  const chosen = new Set(high.map((f) => f.id));
  for (const f of ordered) {
    if (chosen.size >= size) break;
    chosen.add(f.id);
  }
  return chosen;
}

export function refreshBlockedUrls(real: RealData): void {
  const scamThreshold = real.world.thresholds.values['scam.p'] ?? 0.6;
  for (const f of real.world.byId.values()) {
    const cert = real.certBlocked.get(f.id) ?? [];
    f.blockedUrls = f.scam.p >= scamThreshold ? [...new Set([f.url, ...f.outboundLinks])] : cert;
  }
}

export function loadRealWorld(path: string, statePath: string, replay: boolean, now: Date): RealData {
  if (!existsSync(path)) {
    throw new Error(`DATA_MODE=real: brak pliku ${path}. Zbuduj go poleceniem: python ml/scripts/build_findings.py`);
  }
  let file: RealFile;
  try {
    file = JSON.parse(readFileSync(path, 'utf8')) as RealFile;
  } catch (e) {
    throw new Error(`DATA_MODE=real: nieprawidłowy plik ${path}: ${(e as Error).message}`, { cause: e });
  }
  if (!Array.isArray(file.findings) || file.findings.length === 0) {
    throw new Error(`DATA_MODE=real: plik ${path} nie zawiera rekordów`);
  }

  const state = readState(statePath);
  const scoringInputs = new Map<string, unknown>();
  const certBlocked = new Map<string, string[]>();
  const all: Finding[] = file.findings.map(({ scoringInput, ...f }) => {
    if (scoringInput !== undefined) scoringInputs.set(f.id, scoringInput);
    certBlocked.set(f.id, f.blockedUrls ?? []);
    const saved = state.statuses?.[f.id];
    return withUtf16Evidence(saved ? { ...f, status: saved.status, history: saved.history } : f);
  });
  all.sort((a, b) => b.fetchedAt.localeCompare(a.fetchedAt));

  const heldIds = replay ? pickReplay(all) : new Set<string>();
  const campaigns = file.campaigns ?? [];
  const world: World = {
    rng: new Rng(0),
    seq: all.length,
    findings: all.filter((f) => !heldIds.has(f.id)),
    byId: new Map(all.map((f) => [f.id, f])), // także rekordy odtwarzania, żeby linki „powiązane” działały
    index: new Map(),
    members: new Map(),
    campaigns: new Map(),
    defs: new Map(campaigns.map((c) => [c.id, { name: c.name, status: 'ACTIVE' as Campaign['status'] }])),
    evalSet: [],
    thresholds: {
      version: 'v1',
      updatedAt: file.generatedAt ?? now.toISOString(),
      values: file.thresholds?.values ?? defaultThresholdValues(),
    },
  };
  for (const f of world.findings) {
    indexFinding(world, f);
    if (f.campaignId) world.members.set(f.campaignId, [...(world.members.get(f.campaignId) ?? []), f.id]);
  }
  for (const c of campaigns) recomputeCampaign(world, c.id);

  const real: RealData = {
    world,
    held: all.filter((f) => heldIds.has(f.id)),
    scoringInputs,
    certBlocked,
    savedThresholds: state.thresholds,
    generatedAt: file.generatedAt,
    modelVersion: file.modelVersion,
  };
  refreshBlockedUrls(real);
  return real;
}

/** Odsłania kolejny prawdziwy rekord w trybie demo. Data pobrania pozostaje prawdziwa. */
export function releaseNext(real: RealData): { finding: Finding; campaign?: Campaign } | null {
  const finding = real.held.shift();
  if (!finding) return null;
  const { world } = real;
  world.findings = [finding, ...world.findings].sort((a, b) => b.fetchedAt.localeCompare(a.fetchedAt));
  indexFinding(world, finding);
  let campaign: Campaign | undefined;
  if (finding.campaignId) {
    world.members.set(finding.campaignId, [...(world.members.get(finding.campaignId) ?? []), finding.id]);
    campaign = recomputeCampaign(world, finding.campaignId);
  }
  return { finding, campaign };
}

export function saveState(path: string, real: RealData): void {
  const statuses: NonNullable<SavedState['statuses']> = {};
  for (const f of real.world.byId.values()) {
    if (f.status !== 'NEW' || f.history.some((h) => h.user !== 'system')) statuses[f.id] = { status: f.status, history: f.history };
  }
  const body: SavedState = { statuses, thresholds: real.world.thresholds };
  mkdirSync(dirname(path), { recursive: true });
  const tmp = `${path}.${process.pid}.tmp`;
  writeFileSync(tmp, JSON.stringify(body));
  renameSync(tmp, path);
}

async function postAi<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(AI_TIMEOUT_MS),
  });
  if (!res.ok) throw new Error(`ai-service zwrócił ${res.status}`);
  return (await res.json()) as T;
}

/** Wyniki dla wszystkich `ids`. Niepełna odpowiedź jest błędem, żeby nie zapisać częściowego przeliczenia. */
export async function rescoreViaAi(
  aiUrl: string,
  real: RealData,
  values: Record<string, number>,
  ids: string[],
  persist: boolean,
): Promise<Map<string, RescoreResult>> {
  const items = ids.flatMap((itemId) => (real.scoringInputs.has(itemId) ? [{ itemId, scoringInput: real.scoringInputs.get(itemId) }] : []));
  const data = await postAi<{ results: RescoreResult[] }>(`${aiUrl}/rescore`, { thresholds: { values }, persist, itemIds: ids, items });
  const out = new Map(data.results.map((r) => [r.itemId, r]));
  const missing = ids.filter((id) => !out.has(id)).length;
  if (missing) throw new Error(`ai-service nie przeliczył ${missing} z ${ids.length} rekordów`);
  return out;
}

export function applyRescore(real: RealData, results: Map<string, RescoreResult>): void {
  for (const [id, r] of results) {
    const f = real.world.byId.get(id);
    if (!f) continue;
    const index = utf16Index(f.text);
    const rules = r.rules.map((rule) => ({ ...rule, evidence: toUtf16(rule.evidence, index) }));
    Object.assign(f, { rules, modules: r.modules, riskScore: r.riskScore, riskLevel: r.riskLevel, scam: r.scam });
  }
  refreshBlockedUrls(real);
  for (const id of real.world.campaigns.keys()) recomputeCampaign(real.world, id);
}

export async function fetchEvalSet(aiUrl: string): Promise<EvalItem[]> {
  const res = await fetch(`${aiUrl}/calibration/eval-set`, { signal: AbortSignal.timeout(15_000) });
  if (!res.ok) throw new Error(`ai-service zwrócił ${res.status}`);
  const items = (await res.json()) as EvalItem[];
  // ai-service bez eval_set.json zwraca dane syntetyczne o identyfikatorach eval-NNN
  return items.some((i) => /^eval-\d+$/.test(i.id)) ? [] : items;
}
