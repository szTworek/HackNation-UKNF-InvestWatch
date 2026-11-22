// Świat w pamięci API: wyniki z Postgresa (db.ts, ładuje go db/load.py), przeliczenia progów z ai-service.
// Ten moduł niczego nie generuje. Brak danych kończy start serwera błędem.

import type { EvalItem, Evidence, Finding, HistoryEntry, RiskLevel, Status, Thresholds } from '../frontend/src/api/types';
import { computeRelated, indexFinding } from './graph';

const AI_TIMEOUT_MS = 120_000;

export type StoredFinding = Finding & { scoringInput?: unknown };

export interface World {
  findings: Finding[]; // posortowane malejąco po fetchedAt
  byId: Map<string, Finding>;
  index: Map<string, Set<string>>; // `${type}:${value}` -> id rekordów
  evalSet: EvalItem[];
  thresholds: Thresholds;
}

export interface RealFile {
  generatedAt: string;
  modelVersion: string;
  thresholds?: Pick<Thresholds, 'values'> & Partial<Thresholds>;
  findings: StoredFinding[];
}

export interface SavedState {
  statuses?: Record<string, { status: Status; history: HistoryEntry[] }>;
  thresholds?: Thresholds;
}

export interface RealData {
  world: World;
  scoringInputs: Map<string, unknown>;
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

export function loadRealWorld(file: RealFile, state: SavedState, now: Date): RealData {
  const scoringInputs = new Map<string, unknown>();
  const all: Finding[] = file.findings.map(({ scoringInput, ...f }) => {
    if (scoringInput !== undefined) scoringInputs.set(f.id, scoringInput);
    const saved = state.statuses?.[f.id];
    return withUtf16Evidence(saved ? { ...f, status: saved.status, history: saved.history } : f);
  });
  all.sort((a, b) => b.fetchedAt.localeCompare(a.fetchedAt));

  const world: World = {
    findings: all,
    byId: new Map(all.map((f) => [f.id, f])),
    index: new Map(),
    evalSet: [],
    thresholds: {
      version: 'v1',
      updatedAt: file.generatedAt ?? now.toISOString(),
      values: file.thresholds?.values ?? {},
    },
  };
  for (const f of world.findings) indexFinding(world, f);
  return { world, scoringInputs, savedThresholds: state.thresholds, generatedAt: file.generatedAt, modelVersion: file.modelVersion };
}

/** Nowy rekord z Postgresa (zapisał go loader albo scrape-worker). Znany identyfikator lub adres jest pomijany. */
export function addRealFinding(real: RealData, raw: StoredFinding): Finding | null {
  const { world } = real;
  if (world.byId.has(raw.id) || world.findings.some((x) => x.url === raw.url)) return null;
  const { scoringInput, ...rest } = raw;
  if (scoringInput !== undefined) real.scoringInputs.set(rest.id, scoringInput);
  const f = withUtf16Evidence(rest);
  world.findings.unshift(f);
  world.byId.set(f.id, f);
  indexFinding(world, f);
  f.related = computeRelated(world, f);
  return f;
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
    // rekord oceniony przez LLM (ml/scripts/merge_llm.py): moduł, ryzyko i reguły zostają z LLM
    if ((f as { llm?: unknown }).llm !== undefined) continue;
    Object.assign(f, { rules, modules: r.modules, riskScore: r.riskScore, riskLevel: r.riskLevel });
  }
}

export async function fetchEvalSet(aiUrl: string): Promise<EvalItem[]> {
  const res = await fetch(`${aiUrl}/calibration/eval-set`, { signal: AbortSignal.timeout(15_000) });
  if (!res.ok) throw new Error(`ai-service zwrócił ${res.status}`);
  const items = (await res.json()) as EvalItem[];
  // ai-service bez eval_set.json zwraca dane syntetyczne o identyfikatorach eval-NNN
  return items.some((i) => /^eval-\d+$/.test(i.id)) ? [] : items;
}
