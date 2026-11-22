// DATA_MODE=real: stan aplikacji w Postgresie (db/migrations/001_core.sql, ładuje go db/load.py), pliki binarne w MinIO.
import type { Request, Response } from 'express';
import pg from 'pg';
import type { RegistryEntry } from '../frontend/src/api/entityTypes';
import type { HistoryEntry, Thresholds } from '../frontend/src/api/types';
import type { Snapshot } from './entities';
import { buildSnapshot } from './entity-snapshot';
import type { RealFile, SavedState, StoredFinding } from './real';

/* eslint-disable @typescript-eslint/no-explicit-any */
type Row = Record<string, any>;

// timestamptz jako ISO bez milisekund, tak jak w danych z importu
pg.types.setTypeParser(1184, (v) => new Date(v).toISOString().replace('.000Z', 'Z'));

const pool = new pg.Pool({
  connectionString: process.env.DATABASE_URL ?? 'postgresql://investwatch:investwatch@localhost:5432/investwatch',
  max: 5,
});
const MINIO_URL = (process.env.MINIO_URL ?? 'http://minio:9000').replace(/\/$/, '');
const MAXTXT = 1800;
const MAXLINES = 60;

const rows = async (sql: string, params: unknown[] = []): Promise<Row[]> => (await pool.query(sql, params)).rows;

export async function loadRealFile(): Promise<{ file: RealFile; state: SavedState; cursor: string | null }> {
  const [run] = await rows('select finished_at, model_version from load_runs where finished_at is not null and model_version is not null order by id desc limit 1');
  const [{ cursor }] = await rows('select max(updated_at)::text as cursor from findings');
  const thresholds = await rows('select id, version, values, updated_at, active from thresholds order by id');
  const findings = await rows('select id, result, scoring_input, status from findings');
  const history = await rows('select finding_id, at, status, "user", comment from finding_history order by id');

  const decisions = new Map<string, HistoryEntry[]>();
  for (const h of history) {
    const entry: HistoryEntry = { at: h.at, status: h.status, user: h.user, comment: h.comment ?? undefined };
    decisions.set(h.finding_id, [...(decisions.get(h.finding_id) ?? []), entry]);
  }
  const statuses: NonNullable<SavedState['statuses']> = {};
  for (const f of findings) {
    const extra = decisions.get(f.id);
    if (f.status !== 'NEW' || extra) statuses[f.id] = { status: f.status, history: [...(f.result.history ?? []), ...(extra ?? [])] };
  }
  const toThresholds = (t: Row): Thresholds => ({ version: t.version, updatedAt: t.updated_at, values: t.values });
  const active = thresholds.filter((t) => t.active).at(-1);
  const file: RealFile = {
    generatedAt: run?.finished_at ?? new Date().toISOString(),
    modelVersion: run?.model_version ?? 'unknown',
    thresholds: thresholds[0] ? toThresholds(thresholds[0]) : undefined,
    findings: findings.map((f) => ({ ...f.result, scoringInput: f.scoring_input ?? undefined })),
  };
  const state: SavedState = { statuses, thresholds: active && active.id !== thresholds[0]?.id ? toThresholds(active) : undefined };
  return { file, state, cursor };
}

/** Wyniki zapisane po `cursor` (updated_at), od najstarszego: loader i scrape-worker piszą do bazy, API je dociąga. */
export async function findingsSince(cursor: string | null): Promise<{ findings: StoredFinding[]; cursor: string | null }> {
  const found = await rows(
    `select id, result, scoring_input, updated_at::text as cursor from findings
      where $1::timestamptz is null or updated_at > $1::timestamptz order by updated_at limit 500`,
    [cursor],
  );
  return { findings: found.map((f) => ({ ...f.result, scoringInput: f.scoring_input ?? undefined })), cursor: found.at(-1)?.cursor ?? cursor };
}

export interface LoadProgress {
  running: boolean; // ocena w tle trwa
  done: number; // ocenione w bieżącym (albo ostatnim) przebiegu
  total: number; // do oceny w tym przebiegu
  pending: number; // rekordy w bazie bez oceny (czekają na kolejne przebiegi)
  startedAt: string | null;
  finishedAt: string | null;
}

/** Postęp oceny w tle (db/load.py --stage score). */
export async function loadProgress(): Promise<LoadProgress> {
  const [run] = await rows("select started_at, finished_at, total, done from load_runs where stage = 'score' order by id desc limit 1");
  const [{ n }] = await rows('select count(*)::int as n from items where analyzed_at is null');
  return {
    running: !!run && !run.finished_at,
    done: run?.done ?? 0,
    total: run?.total ?? 0,
    pending: n,
    startedAt: run?.started_at ?? null,
    finishedAt: run?.finished_at ?? null,
  };
}

/** Progi z importu (zapisuje je loader przy pierwszej ocenie), gdy API wystartowało przed nim. */
export async function firstThresholds(): Promise<Thresholds | null> {
  const [t] = await rows('select version, values, updated_at from thresholds order by id limit 1');
  return t ? { version: t.version, updatedAt: t.updated_at, values: t.values } : null;
}

export async function saveStatuses(updates: { id: string; entry: HistoryEntry }[]): Promise<void> {
  const client = await pool.connect();
  try {
    await client.query('begin');
    for (const { id, entry } of updates) {
      await client.query('update findings set status = $1, updated_at = now() where id = $2', [entry.status, id]);
      await client.query('insert into finding_history (finding_id, at, status, "user", comment) values ($1, $2, $3, $4, $5)', [
        id,
        entry.at,
        entry.status,
        entry.user,
        entry.comment ?? null,
      ]);
    }
    await client.query('commit');
  } catch (e) {
    await client.query('rollback');
    throw e;
  } finally {
    client.release();
  }
}

/** Nowa aktywna wersja progów i przeliczone kolumny ryzyka. Pełny wynik (result) zostaje z importu: po restarcie przelicza go ai-service. */
export async function saveThresholds(
  t: Thresholds,
  scores: { id: string; modules: number[]; risk_score: number; risk_level: string }[],
): Promise<void> {
  const client = await pool.connect();
  try {
    await client.query('begin');
    await client.query('update thresholds set active = false where active');
    await client.query('insert into thresholds (version, values, updated_at, active) values ($1, $2, $3, true)', [t.version, t.values, t.updatedAt]);
    await client.query(
      `update findings f set modules = array(select jsonb_array_elements_text(v.modules)::int), risk_score = v.risk_score,
         risk_level = v.risk_level, updated_at = now()
       from jsonb_to_recordset($1::jsonb) as v(id text, modules jsonb, risk_score real, risk_level text)
       where f.id = v.id`,
      [JSON.stringify(scores)],
    );
    await client.query('commit');
  } catch (e) {
    await client.query('rollback');
    throw e;
  } finally {
    client.release();
  }
}

function trimText(text: Record<string, string>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(text)
      .filter(([, v]) => typeof v === 'string' && v.trim())
      .map(([k, v]) => [k, v.length > MAXTXT ? `${v.slice(0, MAXTXT)}…` : v]),
  );
}

/** Pierwsze linie OCR i każda linia z informacją o ryzyku dalej (odwołuje się do nich legibility_check). */
function trimLines(lines: Row[]): Row[] {
  return [...lines.slice(0, MAXLINES), ...lines.slice(MAXLINES).filter((l) => l.is_disclosure)];
}

function lastDays(end: string, n: number): string[] {
  const d = new Date(`${end.slice(0, 10)}T00:00:00Z`);
  return Array.from({ length: n }, (_, i) => new Date(d.getTime() - (n - 1 - i) * 86_400_000).toISOString().slice(0, 10));
}

const SEVERITY: Record<string, string> = { CRITICAL: 'high', HIGH: 'high', MEDIUM: 'medium' };
const OPEN = new Set(['NEW', 'IN_REVIEW']);
const RULE_KEY: Record<string, string> = { M1_PROMO: 'M1.PROMO', M3_ADVISORY: 'M3.ADV', M3_RECOMMENDATION: 'M3.REC' };
const ruleKey = (id: string) => {
  const n = /^(\d+)/.exec(id);
  return n ? `R${n[1].padStart(2, '0')}` : (RULE_KEY[id] ?? id);
};

/** Reguły modułu: M3 doradztwo (albo rekomendacja do weryfikacji), M1/M2 naruszenia reguł z 18 i promocji. */
function moduleRules(module: string, rules: Row[]): Row[] {
  return rules.filter((r) => {
    if (module === 'M3') return (r.ruleId === 'M3_ADVISORY' && r.status === 'VIOLATION') || (r.ruleId === 'M3_RECOMMENDATION' && r.status === 'NOT_CHECKED');
    return r.status === 'VIOLATION' && (/^\d/.test(r.ruleId) || (module === 'M1' && r.ruleId === 'M1_PROMO'));
  });
}

/** Cytat dowodu odszukany w sekcjach tekstu rekordu (offsety ai-service dotyczą tekstu analizowanego, nie sekcji). */
function ruleHit(rule: Row, text: Record<string, string>): Row {
  const quote = rule.evidence?.[0]?.text as string | undefined;
  const sections = Object.entries(text ?? {});
  const found = quote ? sections.find(([, t]) => t.includes(quote)) : undefined;
  const at = found && quote ? found[1].indexOf(quote) : -1;
  return {
    rule_id: ruleKey(rule.ruleId),
    label: ruleKey(rule.ruleId),
    evidence: quote ?? 'Brak wymaganej informacji w treści.',
    section: found?.[0] ?? sections[0]?.[0] ?? 'text',
    span: at >= 0 && quote ? [at, at + quote.length] : null,
  };
}

/** Wyniki osi podmiotu z ocen ai-service (tabela findings): M2 tylko dla własnych materiałów podmiotu, M1 i M3 dla autorów trzecich. */
function entityFindings(rows: Row[]): Row[] {
  return rows.flatMap((f) =>
    (f.result.modules as number[]).flatMap((m) => {
      const module = `M${m}`;
      if ((module === 'M2') !== Boolean(f.author_is_entity)) return [];
      const rules = moduleRules(module, f.result.rules as Row[]);
      if (!rules.length) return [];
      return [{
        id: `${f.id}-${f.entity_id}-${module}`,
        item_id: f.item_id,
        entity_id: f.entity_id,
        module,
        score: Math.round(Math.max(...rules.map((r) => Number(r.score) || 0)) * 1000) / 1000,
        severity: SEVERITY[f.result.riskLevel] ?? 'low',
        rule_hits: [...new Map(rules.map((r) => [ruleKey(r.ruleId), ruleHit(r, f.text)])).values()],
        model: f.result.llm?.model ?? f.result.modelVersion,
        created_at: f.result.publishedAt ?? f.result.fetchedAt,
        open: OPEN.has(f.status),
      }];
    }),
  );
}

/** Oś podmiotu z Postgresa: tylko zebrane dane (rekordy, wyniki ai-service, monitor stron), KPI liczone tutaj. */
export async function loadEntitySnapshot(): Promise<Snapshot> {
  const [run] = await rows('select finished_at from load_runs where finished_at is not null order by id desc limit 1');
  const registry = await rows('select * from knf_entities order by name');
  const entities = await rows('select * from entities order by id');
  const items = await rows(
    `select i.*, array_agg(ie.entity_id order by ie.entity_id) as entity_ids, bool_or(ie.author_is_entity) as author_is_entity
       from items i join item_entities ie on ie.item_id = i.id group by i.id`,
  );
  const findings = entityFindings(
    await rows(
      `select f.id, f.item_id, f.result, f.status, ie.entity_id, ie.author_is_entity, i.text
         from findings f join item_entities ie on ie.item_id = f.item_id join items i on i.id = f.item_id`,
    ),
  );
  const pages = await rows('select * from monitored_pages');
  const snapshots = await rows('select * from page_snapshots');
  const changes = await rows('select * from page_changes');
  const alerts = findings
    .filter((f) => f.severity === 'high')
    .map((f) => ({ id: `alr_${f.id}`, created_at: f.created_at, entity_id: f.entity_id, kind: 'finding', severity: 'high',
      title: f.module, ref: { finding_id: f.id, change_id: null }, status: 'new' }))
    .sort((a, b) => b.created_at.localeCompare(a.created_at));

  const now = new Date().toISOString();
  const weekAgo = new Date(Date.now() - 7 * 86_400_000).toISOString();
  const byDay = new Map<string, Record<string, number>>();
  for (const f of findings) {
    const day = byDay.get(f.created_at.slice(0, 10)) ?? { M1: 0, M2: 0, M3: 0 };
    day[f.module] += 1;
    byDay.set(f.created_at.slice(0, 10), day);
  }
  const count = (xs: string[]) => xs.reduce<Record<string, number>>((acc, x) => ({ ...acc, [x]: (acc[x] ?? 0) + 1 }), {});
  const itemsByPlatform = count(items.map((i) => i.platform));
  if (pages.length) itemsByPlatform.website = pages.length;

  const fx: Row = {
    generated_at: run?.finished_at ?? now,
    entities: entities.map((e) => {
      const ef = findings.filter((f) => f.entity_id === e.id);
      const top = ef.map((f) => f.score).sort((a, b) => b - a).slice(0, 20);
      const avg = (xs: number[]) => (xs.length ? Math.round((xs.reduce((a, b) => a + b, 0) / xs.length) * 100) / 100 : 0);
      const eitems = items.filter((i) => i.entity_ids.includes(e.id));
      return {
        ...e,
        registry_entries: e.registry_names.map((name: string) => ({ name })),
        kpis: {
          items: eitems.length,
          findings_open: ef.filter((f) => f.open).length,
          alerts_new: alerts.filter((a) => a.entity_id === e.id).length,
          risk_score: avg(top),
          pages_changed_7d: new Set(changes.filter((c) => c.entity_id === e.id && c.detected_at >= weekAgo).map((c) => c.page_id)).size,
        },
        modules: Object.fromEntries(
          ['M1', 'M2', 'M3'].map((m) => {
            const mf = ef.filter((f) => f.module === m);
            return [m, { findings: mf.length, avg_score: avg(mf.map((f) => f.score)) }];
          }),
        ),
        platforms: count(eitems.map((i) => i.platform)),
      };
    }),
    items: items.map((i) => ({
      id: i.id,
      entity_ids: i.entity_ids,
      channel: i.channel,
      platform: i.platform,
      source_url: i.url,
      author: i.author ?? i.sponsor ?? 'unknown',
      author_is_entity: i.author_is_entity,
      published_at: i.published_at,
      fetched_at: i.fetched_at,
      text: trimText(i.text),
      media: i.media ?? [],
      ocr_lines: trimLines(i.source_meta?.ocr_lines ?? []),
      legibility: i.source_meta?.legibility,
      legibility_check: i.source_meta?.legibility_check,
      mock: false,
    })),
    findings,
    pages,
    snapshots,
    changes,
    alerts,
    overview: {
      findings_by_day: lastDays(now, 30).map((date) => ({ date, ...(byDay.get(date) ?? { M1: 0, M2: 0, M3: 0 }) })),
      items_by_platform: itemsByPlatform,
    },
  };
  const entries: RegistryEntry[] = registry.map((r) => ({
    name: r.name,
    aliases: r.aliases ?? [],
    category: r.category,
    country: r.country,
    supervisor: r.supervisor,
    registeredAt: r.registered_at,
    address: r.address,
    sourceUrl: r.source_url,
  }));
  // podmioty bez danych nie mają modules/platforms, uzupełnia je GET /api/entities/:id (jak przy pliku)
  return buildSnapshot(fx, entries, 'postgres: knf_entities', 'postgres') as unknown as Snapshot;
}

/** Plik z MinIO (bucket media albo screens) przez API: przeglądarka nie ma dostępu do sieci Compose. */
export function objectProxy(bucket: string) {
  return async (req: Request, res: Response): Promise<void> => {
    const key = String(req.params.key);
    if (!/^[\w.-]+$/.test(key)) return void res.status(404).json({ error: 'Nie znaleziono' });
    try {
      const r = await fetch(`${MINIO_URL}/${bucket}/${key}`, { signal: AbortSignal.timeout(10_000) });
      if (!r.ok) return void res.status(404).json({ error: 'Nie znaleziono' });
      res.setHeader('Content-Type', r.headers.get('content-type') ?? 'application/octet-stream');
      res.setHeader('Cache-Control', 'public, max-age=86400');
      res.send(Buffer.from(await r.arrayBuffer()));
    } catch {
      res.status(503).json({ error: 'Magazyn plików jest niedostępny' });
    }
  };
}
