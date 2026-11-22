// Kalibracja na pewności modułu z LLM (findings.result.llm.scores): rekord trafia do modułu X, gdy scores[MX] >= próg 'module.MX'.
// Zbiór testowy: ręczne werdykty z eval_decisions.json złączone z rekordami po URL.

import { readFileSync } from 'node:fs';
import pg from 'pg';
import type { EvalItem, Finding, ModuleEval, ModuleId, Thresholds, ThresholdsPreview } from '../frontend/src/api/types';

const MODULES: ModuleId[] = [1, 2, 3];
const DEFAULT_THRESHOLD = 0.5;
const moduleKey = (m: ModuleId) => `module.M${m}`;

type Scores = Partial<Record<'M1' | 'M2' | 'M3' | 'NONE', number>>;
const scoresOf = (f: Finding): Scores | undefined => (f as { llm?: { scores?: Scores } }).llm?.scores;
const scoreOf = (s: Scores, m: ModuleId) => s[`M${m}`] ?? 0;
const thr = (values: Record<string, number>, m: ModuleId) => values[moduleKey(m)] ?? DEFAULT_THRESHOLD;

const pool = new pg.Pool({
  connectionString: process.env.DATABASE_URL ?? 'postgresql://investwatch:investwatch@localhost:5432/investwatch',
  max: 2,
});

/** Progi z bazy uzupełnione o 'module.M1..M3' (domyślnie 0.5, co odtwarza moduły z LLM). */
export function withModuleKeys(t: Thresholds): Thresholds {
  const values = { ...t.values };
  for (const m of MODULES) values[moduleKey(m)] ??= DEFAULT_THRESHOLD;
  return { ...t, values };
}

function modulesAt(f: Finding, values: Record<string, number>): ModuleId[] {
  const s = scoresOf(f);
  return s ? MODULES.filter((m) => scoreOf(s, m) >= thr(values, m)) : f.modules;
}

/** Moduły rekordu przy jednym progu dla wszystkich modułów (podgląd listy modułu bez zapisu progów). */
export function modulesAtConfidence(f: Finding, t: number): ModuleId[] {
  return modulesAt(f, Object.fromEntries(MODULES.map((m) => [moduleKey(m), t])));
}

/** Przypisuje moduły wg progów; zwraca rekordy, którym zmieniła się lista modułów. */
export function applyModules(findings: Finding[], values: Record<string, number>): Finding[] {
  const changed: Finding[] = [];
  for (const f of findings) {
    const next = modulesAt(f, values);
    if (next.join() === f.modules.join()) continue;
    f.modules = next;
    changed.push(f);
  }
  return changed;
}

interface Decision {
  url: string;
  verdict: 'M1' | 'M2' | 'M3' | 'NONE';
}

function loadDecisions(): Decision[] {
  const paths = [process.env.EVAL_DECISIONS_PATH, 'eval_decisions.json', '../eval_decisions.json'].filter((p): p is string => !!p);
  for (const p of paths) {
    try {
      return JSON.parse(readFileSync(p, 'utf8')) as Decision[];
    } catch {
      // następna ścieżka
    }
  }
  process.stdout.write(`[api] kalibracja: brak eval_decisions.json (${paths.join(', ')})\n`);
  return [];
}

const decisions = loadDecisions();

export function buildEvalSet(findings: Finding[]): EvalItem[] {
  const byUrl = new Map(findings.map((f) => [f.url, f]));
  return decisions.flatMap((d) => {
    const f = byUrl.get(d.url);
    const s = f && scoresOf(f);
    if (!f || !s) return [];
    return [
      {
        id: f.id,
        url: f.url,
        probs: Object.fromEntries(MODULES.map((m) => [moduleKey(m), scoreOf(s, m)])),
        gold: Object.fromEntries(MODULES.map((m) => [moduleKey(m), d.verdict === `M${m}` ? 1 : 0])),
      },
    ];
  });
}

function evalAt(items: EvalItem[], m: ModuleId, t: number): ModuleEval {
  const k = moduleKey(m);
  const c = { tp: 0, fp: 0, fn: 0, tn: 0 };
  for (const it of items) {
    const predicted = (it.probs[k] ?? 0) >= t;
    if (it.gold[k] === 1) c[predicted ? 'tp' : 'fn']++;
    else c[predicted ? 'fp' : 'tn']++;
  }
  return { ...c, precision: c.tp + c.fp ? c.tp / (c.tp + c.fp) : 0, recall: c.tp + c.fn ? c.tp / (c.tp + c.fn) : 0 };
}

export function previewModules(findings: Finding[], current: Record<string, number>, proposed: Record<string, number>): ThresholdsPreview {
  const items = buildEvalSet(findings);
  const count = (get: (f: Finding) => ModuleId[]) =>
    Object.fromEntries(MODULES.map((m) => [m, findings.filter((f) => get(f).includes(m)).length])) as Record<ModuleId, number>;
  return {
    current: count((f) => f.modules),
    proposed: count((f) => modulesAt(f, proposed)),
    eval: Object.fromEntries(
      MODULES.map((m) => [m, { current: evalAt(items, m, thr(current, m)), proposed: evalAt(items, m, thr(proposed, m)) }]),
    ) as ThresholdsPreview['eval'],
    evalSize: items.length,
  };
}

/** Nowa aktywna wersja progów i moduły rekordów (kolumna modules i result.modules, z którego API ładuje dane po restarcie). */
export async function saveModuleThresholds(t: Thresholds, findings: Finding[]): Promise<void> {
  const client = await pool.connect();
  try {
    await client.query('begin');
    await client.query('update thresholds set active = false where active');
    await client.query('insert into thresholds (version, values, updated_at, active) values ($1, $2, $3, true)', [t.version, t.values, t.updatedAt]);
    await client.query(
      `update findings f set modules = array(select jsonb_array_elements_text(v.modules)::int),
         result = jsonb_set(f.result, '{modules}', v.modules), updated_at = now()
       from jsonb_to_recordset($1::jsonb) as v(id text, modules jsonb)
       where f.id = v.id and f.modules is distinct from array(select jsonb_array_elements_text(v.modules)::int)`,
      [JSON.stringify(findings.map((f) => ({ id: f.id, modules: f.modules })))],
    );
    await client.query('commit');
  } catch (e) {
    await client.query('rollback');
    throw e;
  } finally {
    client.release();
  }
}
