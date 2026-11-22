// API InvestWatch (kontrakt: docs/frontend-agent.md, sekcja 4). DATA_MODE=real: Postgres + MinIO, mock: generator w pamięci.

import { createServer } from 'node:http';
import express, { type Request, type Response } from 'express';
import { Server } from 'socket.io';
import type {
  BulkStatusUpdate,
  CampaignDetail,
  CampaignListItem,
  CampaignStatus,
  ClientToServerEvents,
  ContentType,
  Finding,
  FindingSummary,
  HistoryRow,
  FlagKey,
  IndicatorFindings,
  Instrument,
  ModuleId,
  Page,
  ServerToClientEvents,
  StatsOverview,
  Status,
  Thresholds,
  ThresholdsPreview,
  Timeseries,
  TimeseriesGroupBy,
} from '../frontend/src/api/types';
import {
  CONTENT_TYPES,
  PLATFORMS,
  PLATFORM_LABEL,
  REGISTER_LABEL,
  RISK_LABEL,
  RISK_LEVELS,
  STATUSES,
  STATUS_LABEL,
} from '../frontend/src/lib/labels';
import { loadEntitySnapshot, loadRealFile, saveStatuses, saveThresholds } from './db';
import { readSnapshotFile, registerEntityRoutes } from './entities';
import { frameSvg, landingSvg } from './enrich';
import { campaignGraph, egoGraph } from './graph';
import { RULES } from './rules';
import { THRESHOLD_KEYS, rescore } from './scoring';
import {
  addRealFinding,
  applyRescore,
  fetchEvalSet,
  loadRealWorld,
  type RealData,
  rescoreViaAi,
} from './real';
import { applyThresholds, createWorld, recomputeCampaign, type World } from './seed';

try {
  process.loadEnvFile('.env');
} catch {
  // brak .env – zostają wartości domyślne
}

const PORT = Number(process.env.API_PORT ?? 4000);
const SEED = Number(process.env.MOCK_SEED ?? 42);
const CORS_ORIGIN = process.env.CORS_ORIGIN ?? '*';

const log = (msg: string) => process.stdout.write(`[api] ${msg}\n`);

const DATA_MODE = process.env.DATA_MODE ?? 'mock';
if (DATA_MODE !== 'mock' && DATA_MODE !== 'real') {
  process.stderr.write(`[api] Nieznany DATA_MODE: ${DATA_MODE} (dozwolone: mock, real)\n`);
  process.exit(1);
}
const AI_URL = (process.env.AI_URL ?? 'http://localhost:8000').replace(/\/$/, '');

// Wypełniane w start(): w trybie real z Postgresa, w trybie mock z generatora.
let real: RealData | null = null;
let world!: World;
const DAY = 24 * 3600 * 1000;

// ---------------------------------------------------------------------------
// Pomocnicze: query string, filtry
// ---------------------------------------------------------------------------

type Query = Request['query'];

function arr(q: Query, key: string): string[] {
  const v = q[key] ?? q[`${key}[]`];
  if (v === undefined) return [];
  return (Array.isArray(v) ? v : [v]).map(String).flatMap((x) => x.split(',')).filter(Boolean);
}

function str(q: Query, key: string): string | undefined {
  const v = q[key];
  return typeof v === 'string' && v.length ? v : undefined;
}

function dateRange(q: Query): { from: number; to: number } {
  const from = str(q, 'from');
  const to = str(q, 'to');
  return {
    from: from ? new Date(`${from}T00:00:00`).getTime() : -Infinity,
    to: to ? new Date(`${to}T23:59:59.999`).getTime() : Infinity,
  };
}

const th = (key: string) => world.thresholds.values[key] ?? 0.5;
const isScam = (f: Finding) => f.scam.p >= th('scam.p');
const isIncident = (f: Finding) => f.modules.length > 0 || isScam(f);

function filterFindings(q: Query): Finding[] {
  const { from, to } = dateRange(q);
  const platforms = arr(q, 'platform');
  const modules = arr(q, 'module').map(Number);
  const levels = arr(q, 'riskLevel');
  const statuses = arr(q, 'status');
  const flags = arr(q, 'flag') as FlagKey[];
  const scam = str(q, 'scam') === '1' || str(q, 'scam') === 'true';
  const campaignId = str(q, 'campaignId');
  const text = str(q, 'q')?.toLowerCase();
  return world.findings.filter((f) => {
    const t = new Date(f.fetchedAt).getTime();
    if (t < from || t > to) return false;
    if (platforms.length && !platforms.includes(f.platform)) return false;
    if (modules.length && !f.modules.some((m) => modules.includes(m))) return false;
    if (levels.length && !levels.includes(f.riskLevel)) return false;
    if (statuses.length && !statuses.includes(f.status)) return false;
    if (flags.length && !flags.every((fl) => (f.flags[fl]?.p ?? 0) >= th(`flags.${fl}`))) return false;
    if (scam && !isScam(f)) return false;
    if (campaignId && f.campaignId !== campaignId) return false;
    if (text) {
      const hay = `${f.text} ${f.author.handle} ${f.author.displayName ?? ''} ${f.title ?? ''} ${f.url} ${f.id}`.toLowerCase();
      if (!hay.includes(text)) return false;
    }
    return true;
  });
}

/** Wartość sortowania dla pola z URL. Nieznane pole oznacza sortowanie po dacie pobrania. */
function sortValue(f: Finding, field: string): number | string {
  switch (field) {
    case 'publishedAt':
      return f.publishedAt ?? '';
    case 'riskScore':
      return f.riskScore;
    case 'scam':
      return f.scam.p;
    case 'author':
      return f.author.handle.toLowerCase();
    case 'status':
      return STATUSES.indexOf(f.status);
    case 'riskLevel':
      return RISK_LEVELS.indexOf(f.riskLevel);
    case 'platform':
      return f.platform;
    default:
      return f.fetchedAt;
  }
}

function sortFindings(items: Finding[], sort: string | undefined): Finding[] {
  const [field, dir] = (sort ?? 'fetchedAt:desc').split(':');
  const sign = dir === 'asc' ? 1 : -1;
  return [...items].sort((a, b) => {
    const x = sortValue(a, field);
    const y = sortValue(b, field);
    if (x < y) return -sign;
    if (x > y) return sign;
    return b.fetchedAt.localeCompare(a.fetchedAt);
  });
}

function countBy<K extends string>(keys: readonly K[], items: Finding[], get: (f: Finding) => K | K[]): Record<K, number> {
  const out = Object.fromEntries(keys.map((k) => [k, 0])) as Record<K, number>;
  for (const f of items) {
    const v = get(f);
    for (const k of Array.isArray(v) ? v : [v]) if (k in out) out[k] += 1;
  }
  return out;
}

function dayKey(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function daysBetween(from: number, to: number): string[] {
  const out: string[] = [];
  const d = new Date(from);
  d.setHours(0, 0, 0, 0);
  for (let i = 0; d.getTime() <= to && i < 400; i++) {
    out.push(dayKey(d));
    d.setDate(d.getDate() + 1);
  }
  return out;
}

function effectiveRange(q: Query, items: Finding[]): { from: number; to: number } {
  const r = dateRange(q);
  const times = items.map((f) => new Date(f.fetchedAt).getTime());
  return {
    from: Number.isFinite(r.from) ? r.from : Math.min(...times, Date.now() - 29 * DAY),
    to: Number.isFinite(r.to) ? Math.min(r.to, Date.now()) : Date.now(),
  };
}

function campaignListItem(id: string, from: number, to: number): CampaignListItem | null {
  const c = world.campaigns.get(id);
  if (!c) return null;
  const days = daysBetween(from, to);
  const counts = new Map(days.map((d) => [d, 0]));
  for (const fid of world.members.get(id) ?? []) {
    const f = world.byId.get(fid);
    if (!f) continue;
    const k = dayKey(new Date(f.fetchedAt));
    if (counts.has(k)) counts.set(k, (counts.get(k) ?? 0) + 1);
  }
  return { ...c, trend: [...counts.values()] };
}

/** Lekki wiersz listy: bez pełnego tekstu, flag, reguł i wzbogaceń. */
function toSummary(f: Finding): FindingSummary {
  const body = (f.kind === 'transcript' && f.transcript ? f.transcript : f.text).replace(/\s+/g, ' ').trim();
  const topFlags = (Object.entries(f.flags) as [FlagKey, Finding['flags'][FlagKey]][])
    .filter(([k, v]) => !['RISK_WARNING', 'AD_DISCLOSURE', 'PAST_PERF_DISCLAIMER', 'FORECAST_DISCLAIMER'].includes(k) && v.p >= th(`flags.${k}`))
    .sort((a, b) => b[1].p - a[1].p)
    .slice(0, 3)
    .map(([flag, v]) => ({ flag, p: v.p }));
  const contentType = (Object.entries(f.contentType) as [ContentType, number][]).sort((a, b) => b[1] - a[1])[0][0];
  const firm = f.entities.find((e) => e.role === 'investment_firm');
  const advisor = f.entities.find((e) => e.role === 'advisor');
  return {
    id: f.id,
    url: f.url,
    platform: f.platform,
    kind: f.kind,
    author: { handle: f.author.handle, displayName: f.author.displayName },
    title: f.title,
    snippet: body.length > 200 ? `${body.slice(0, 199)}…` : body,
    publishedAt: f.publishedAt,
    fetchedAt: f.fetchedAt,
    modules: f.modules,
    contentType,
    topFlags,
    scamP: f.scam.p,
    riskScore: f.riskScore,
    riskLevel: f.riskLevel,
    status: f.status,
    campaignId: f.campaignId,
    hasLanding: f.landingPages.length > 0,
    hasMedia: !!f.media,
    firm: firm ? { name: firm.name, register: firm.knfRegister.status } : undefined,
    advertiser: f.entities.find((e) => e.role === 'advertiser')?.name ?? (f.modules.includes(1) ? f.author.displayName ?? f.author.handle : undefined),
    adDisclosed: f.adDisclosure ? f.adDisclosure !== 'MISSING' : f.flags.AD_DISCLOSURE.p >= th('flags.AD_DISCLOSURE'),
    adDisclosure: f.adDisclosure ?? (f.flags.AD_DISCLOSURE.p >= th('flags.AD_DISCLOSURE') ? 'DISCLOSED' : 'MISSING'),
    advisor: advisor ? { name: advisor.name, register: advisor.knfRegister.status } : undefined,
    instruments: (Object.entries(f.instruments) as [Instrument, number][]).filter(([, p]) => p >= 0.5).map(([k]) => k),
    violations: f.rules.filter((r) => r.status === 'VIOLATION').map((r) => r.ruleId),
    brand: f.indicators.find((i) => i.type === 'brand')?.value,
    domains: f.indicators.filter((i) => i.type === 'domain').map((i) => i.value),
    contacts: f.indicators.filter((i) => i.type === 'phone' || i.type === 'telegram' || i.type === 'whatsapp').map((i) => i.value),
  };
}

function csvCell(v: string | number | undefined): string {
  const raw = String(v ?? '').replace(/\r?\n/g, ' ');
  // treść ze scrapera jest niezaufana: bez formuł po otwarciu raportu w arkuszu
  const s = /^[=+\-@\t]/.test(raw) ? `'${raw}` : raw;
  return /[";\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

// ---------------------------------------------------------------------------
// HTTP
// ---------------------------------------------------------------------------

const app = express();
app.disable('x-powered-by');
app.use(express.json({ limit: '200kb' }));
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', CORS_ORIGIN);
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PUT,PATCH,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Access-Control-Expose-Headers', 'Content-Disposition');
  if (req.method === 'OPTIONS') {
    res.sendStatus(204);
    return;
  }
  next();
});

const notFound = (res: Response, what = 'Nie znaleziono') => res.status(404).json({ error: what });

// ---------------------------------------------------------------------------
// Zbieranie danych: pośrednik do scrape-workera (usługa dostępna tylko w sieci Compose)
// ---------------------------------------------------------------------------

const WORKER_URL = (process.env.SCRAPE_WORKER_URL ?? 'http://scrape-worker:8100').replace(/\/$/, '');

async function proxyWorker(res: Response, path: string, method: string, body?: unknown): Promise<void> {
  try {
    const r = await fetch(`${WORKER_URL}${path}`, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(8000),
    });
    res.status(r.status).json(await r.json());
  } catch {
    res.status(503).json({ error: 'Usługa zbierania danych jest niedostępna' });
  }
}

app.get('/api/jobs', (_req, res) => void proxyWorker(res, '/status', 'GET'));
app.post('/api/jobs/run', (req, res) => void proxyWorker(res, '/run', 'POST', { includeMeta: req.body?.includeMeta === true }));
app.put('/api/jobs/schedule', (req, res) =>
  void proxyWorker(res, '/schedule', 'PUT', { enabled: req.body?.enabled, intervalMin: req.body?.intervalMin }));
app.get('/api/jobs/known', (_req, res) => {
  res.json({ urls: world.findings.map((f) => f.url) });
});

let jobCursor = 0;
async function pullJobFindings(data: RealData): Promise<void> {
  try {
    for (;;) {
      const r = await fetch(`${WORKER_URL}/findings?after=${jobCursor}`, { signal: AbortSignal.timeout(8000) });
      if (!r.ok) return;
      const page = (await r.json()) as { items: Parameters<typeof addRealFinding>[1][]; next: number };
      if (!page.items.length) return;
      let added = 0;
      for (const item of page.items) if (addRealFinding(data, item)) added += 1;
      jobCursor = page.next;
      if (added) log(`job: dodano ${added} rekordów`);
    }
  } catch {
    // worker wyłączony albo jeszcze startuje: spróbujemy przy kolejnym odpytaniu
  }
}

app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', findings: world.findings.length, dataMode: DATA_MODE });
});

app.get('/api/findings', (req, res) => {
  const items = sortFindings(filterFindings(req.query), str(req.query, 'sort'));
  const pageSize = Math.min(200, Math.max(1, Number(str(req.query, 'pageSize') ?? 25)));
  const page = Math.max(1, Number(str(req.query, 'page') ?? 1));
  const body: Page<FindingSummary> = {
    items: items.slice((page - 1) * pageSize, page * pageSize).map(toSummary),
    total: items.length,
    page,
    pageSize,
  };
  res.json(body);
});

function updateStatus(f: Finding, status: Status, comment: string | undefined): Finding {
  f.status = status;
  f.history = [...f.history, { at: new Date().toISOString(), status, user: 'analityk', comment: comment || undefined }];
  if (f.campaignId) recomputeCampaign(world, f.campaignId);
  return f;
}

/** Tryb real: status i wpis historii trafiają do Postgresa przed odpowiedzią. */
async function persistStatuses(updated: Finding[], res: Response): Promise<boolean> {
  if (!real || !updated.length) return true;
  try {
    await saveStatuses(updated.map((f) => ({ id: f.id, entry: f.history[f.history.length - 1] })));
    return true;
  } catch (e) {
    log(`postgres: ${(e as Error).message}`);
    res.status(503).json({ error: 'Baza danych jest niedostępna, status nie został zapisany' });
    return false;
  }
}

app.patch('/api/findings/status', async (req, res) => {
  const body = req.body as Partial<BulkStatusUpdate>;
  if (!Array.isArray(body.ids) || !STATUSES.includes(body.status as Status)) {
    res.status(400).json({ error: 'Wymagane: ids[], status' });
    return;
  }
  const updated: Finding[] = [];
  for (const id of body.ids) {
    const f = world.byId.get(String(id));
    if (!f) continue;
    updated.push(updateStatus(f, body.status as Status, body.comment));
  }
  if (!(await persistStatuses(updated, res))) return;
  for (const f of updated) io.emit('finding:updated', f);
  res.json({ items: updated });
});

app.get('/api/findings/:id', (req, res) => {
  const f = world.byId.get(req.params.id);
  if (!f) return void notFound(res, 'Nie ma takiego rekordu');
  res.json(f);
});

app.patch('/api/findings/:id/status', async (req, res) => {
  const f = world.byId.get(req.params.id);
  if (!f) return void notFound(res, 'Nie ma takiego rekordu');
  const { status, comment } = req.body as { status?: Status; comment?: string };
  if (!status || !STATUSES.includes(status)) {
    res.status(400).json({ error: 'Nieprawidłowy status' });
    return;
  }
  updateStatus(f, status, comment);
  if (!(await persistStatuses([f], res))) return;
  io.emit('finding:updated', f);
  res.json(f);
});

app.get('/api/findings/:id/graph', (req, res) => {
  const depth = str(req.query, 'depth') === '2' ? 2 : 1;
  const g = egoGraph(world, req.params.id, depth);
  if (!g) return void notFound(res, 'Nie ma takiego rekordu');
  res.json(g);
});

app.get('/api/stats/overview', (req, res) => {
  const items = filterFindings({ from: req.query.from, to: req.query.to });
  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);
  const dayAgo = Date.now() - DAY;
  const brands = new Map<string, number>();
  for (const f of items) {
    if (!isScam(f) || !f.scam.signals.includes('IMPERSONATION')) continue;
    for (const ind of f.indicators) if (ind.type === 'brand') brands.set(ind.value, (brands.get(ind.value) ?? 0) + 1);
  }
  const byStatus = countBy(STATUSES, items, (f) => f.status);
  const body: StatsOverview = {
    total: items.length,
    newToday: world.findings.filter((f) => new Date(f.fetchedAt).getTime() >= todayStart.getTime()).length,
    highCritical: items.filter((f) => f.riskLevel === 'HIGH' || f.riskLevel === 'CRITICAL').length,
    byModule: countBy(['1', '2', '3'] as const, items, (f) => f.modules.map((m) => String(m) as '1' | '2' | '3')),
    byRiskLevel: countBy(RISK_LEVELS, items, (f) => f.riskLevel),
    byPlatform: countBy(PLATFORMS, items, (f) => f.platform),
    byStatus,
    byContentType: countBy(CONTENT_TYPES, items, (f) => {
      const entries = Object.entries(f.contentType) as [ContentType, number][];
      return entries.sort((a, b) => b[1] - a[1])[0][0];
    }),
    scam24h: world.findings.filter((f) => isScam(f) && new Date(f.fetchedAt).getTime() >= dayAgo).length,
    scamTotal: items.filter(isScam).length,
    topImpersonatedBrands: [...brands.entries()]
      .map(([brand, count]) => ({ brand, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5),
    confirmed: byStatus.CONFIRMED,
    verified: byStatus.CONFIRMED + byStatus.DISMISSED + byStatus.ESCALATED,
  };
  res.json(body);
});

app.get('/api/stats/timeseries', (req, res) => {
  const groupBy = (str(req.query, 'groupBy') ?? 'module') as TimeseriesGroupBy;
  const items = filterFindings({ from: req.query.from, to: req.query.to }).filter(isIncident);
  const { from, to } = effectiveRange(req.query, items);
  const days = daysBetween(from, to);
  const keys: string[] =
    groupBy === 'platform' ? [...PLATFORMS] : groupBy === 'riskLevel' ? [...RISK_LEVELS] : ['1', '2', '3', 'scam'];
  const points = days.map((date) => ({ date, counts: Object.fromEntries(keys.map((k) => [k, 0])) as Record<string, number> }));
  const byDay = new Map(points.map((p) => [p.date, p]));
  for (const f of items) {
    const p = byDay.get(dayKey(new Date(f.fetchedAt)));
    if (!p) continue;
    if (groupBy === 'platform') p.counts[f.platform] += 1;
    else if (groupBy === 'riskLevel') p.counts[f.riskLevel] += 1;
    else {
      for (const m of f.modules) p.counts[String(m)] += 1;
      if (isScam(f)) p.counts.scam += 1;
    }
  }
  const body: Timeseries = { bucket: 'day', groupBy, keys, points };
  res.json(body);
});

app.get('/api/history', (req, res) => {
  const { from, to } = dateRange(req.query);
  const user = str(req.query, 'user');
  const rows: HistoryRow[] = [];
  for (const f of world.findings) {
    for (const h of f.history) {
      if (h.user === 'system') continue; // tylko decyzje analityków
      const t = new Date(h.at).getTime();
      if (t < from || t > to || (user && h.user !== user)) continue;
      const body = (f.kind === 'transcript' && f.transcript ? f.transcript : f.text).replace(/\s+/g, ' ');
      rows.push({ ...h, findingId: f.id, platform: f.platform, author: f.author.handle, snippet: body.slice(0, 140), riskLevel: f.riskLevel });
    }
  }
  rows.sort((a, b) => b.at.localeCompare(a.at));
  const pageSize = Math.min(200, Math.max(1, Number(str(req.query, 'pageSize') ?? 50)));
  const page = Math.max(1, Number(str(req.query, 'page') ?? 1));
  const body: Page<HistoryRow> = { items: rows.slice((page - 1) * pageSize, page * pageSize), total: rows.length, page, pageSize };
  res.json(body);
});

app.get('/api/rules', (_req, res) => {
  res.json(RULES);
});

app.get('/api/thresholds', (_req, res) => {
  res.json(world.thresholds);
});

function parseValues(body: unknown): Record<string, number> | null {
  const values = (body as Partial<Thresholds> | undefined)?.values;
  if (!values || typeof values !== 'object') return null;
  const out: Record<string, number> = {};
  for (const key of real ? Object.keys(world.thresholds.values) : THRESHOLD_KEYS) {
    const v = (values as Record<string, unknown>)[key];
    if (v === undefined) continue;
    if (typeof v !== 'number' || !Number.isFinite(v) || v < 0 || v > 1) return null;
    out[key] = Math.round(v * 1000) / 1000;
  }
  return out;
}

app.put('/api/thresholds', (req, res) => {
  const values = parseValues(req.body);
  if (!values) {
    res.status(400).json({ error: 'Progi muszą być liczbami z zakresu 0–1' });
    return;
  }
  if (real) return void saveRealThresholds(real, values, res);
  const t = applyThresholds(world, values, new Date());
  for (const id of world.campaigns.keys()) recomputeCampaign(world, id);
  io.emit('thresholds:updated', t);
  log(`progi zapisane (${t.version})`);
  res.json(t);
});

const aiUnavailable = (res: Response, e: unknown) => {
  log(`ai-service: ${(e as Error).message}`);
  res.status(503).json({ error: 'ai-service jest niedostępny, progi nie zostały zmienione' });
};

async function saveRealThresholds(data: RealData, values: Record<string, number>, res: Response): Promise<void> {
  const proposed = { ...world.thresholds.values, ...values };
  const ids = [...world.byId.keys()];
  try {
    const results = await rescoreViaAi(AI_URL, data, proposed, ids, false);
    await rescoreViaAi(AI_URL, data, proposed, ids.slice(0, 1), true);
    const n = Number(world.thresholds.version.replace(/\D/g, '')) || 1;
    world.thresholds = { version: `v${n + 1}`, updatedAt: new Date().toISOString(), values: proposed };
    applyRescore(data, results);
    await saveThresholds(
      world.thresholds,
      world.findings.map((f) => ({ id: f.id, modules: f.modules, risk_score: f.riskScore, risk_level: f.riskLevel, scam_p: f.scam.p })),
    );
  } catch (e) {
    return aiUnavailable(res, e);
  }
  io.emit('thresholds:updated', world.thresholds);
  log(`progi zapisane (${world.thresholds.version})`);
  res.json(world.thresholds);
}

app.post('/api/thresholds/preview', (req, res) => {
  const values = parseValues(req.body);
  if (!values) {
    res.status(400).json({ error: 'Progi muszą być liczbami z zakresu 0–1' });
    return;
  }
  const proposedValues = { ...world.thresholds.values, ...values };
  const since = Date.now() - 30 * DAY;
  const recent = world.findings.filter((f) => new Date(f.fetchedAt).getTime() >= since);
  if (real) {
    rescoreViaAi(AI_URL, real, proposedValues, recent.map((f) => f.id), false)
      .then((results) => {
        const preview: ThresholdsPreview = {
          current: countBy(RISK_LEVELS, recent, (f) => f.riskLevel),
          proposed: countBy(RISK_LEVELS, recent, (f) => results.get(f.id)?.riskLevel ?? f.riskLevel),
        };
        res.json(preview);
      })
      .catch((e: unknown) => aiUnavailable(res, e));
    return;
  }
  const body: ThresholdsPreview = {
    current: countBy(RISK_LEVELS, recent, (f) => f.riskLevel),
    proposed: countBy(RISK_LEVELS, recent, (f) => rescore(f, proposedValues).riskLevel),
  };
  res.json(body);
});

app.get('/api/calibration/eval-set', (_req, res) => {
  if (!real || world.evalSet.length) return void res.json(world.evalSet);
  fetchEvalSet(AI_URL)
    .then((items) => {
      world.evalSet = items;
      res.json(items);
    })
    .catch((e: unknown) => {
      log(`ai-service: ${(e as Error).message}`);
      res.status(503).json({ error: 'ai-service jest niedostępny' });
    });
});

app.get('/api/reports/module/:file', (req, res) => {
  const match = /^([123])\.csv$/.exec(req.params.file);
  if (!match) return void notFound(res, 'Raport: /reports/module/1.csv, 2.csv albo 3.csv');
  const moduleId = Number(match[1]) as ModuleId;
  const items = sortFindings(filterFindings({ ...req.query, module: String(moduleId), 'module[]': undefined }), str(req.query, 'sort'));
  const date = (f: Finding) => new Date(f.fetchedAt).toISOString().slice(0, 16).replace('T', ' ');
  const firm = (f: Finding) => f.entities.find((e) => e.role === 'investment_firm');
  const advisor = (f: Finding) => f.entities.find((e) => e.role === 'advisor') ?? f.entities[0];
  let header: string[];
  let rows: (string | number | undefined)[][];
  if (moduleId === 1) {
    header = ['ID', 'Data wykrycia', 'Platforma', 'Firma inwestycyjna', 'Status w rejestrze KNF', 'Reklamujący', 'Treść', 'URL', 'Poziom ryzyka', 'Status'];
    rows = items.map((f) => [
      f.id,
      date(f),
      PLATFORM_LABEL[f.platform],
      firm(f)?.name,
      firm(f) ? REGISTER_LABEL[firm(f)!.knfRegister.status] : '',
      f.author.displayName ? `${f.author.displayName} (${f.author.handle})` : f.author.handle,
      f.text,
      f.url,
      RISK_LABEL[f.riskLevel],
      STATUS_LABEL[f.status],
    ]);
  } else if (moduleId === 2) {
    header = ['ID', 'Data wykrycia', 'Platforma', 'Firma inwestycyjna', 'Reguły do weryfikacji', 'Treść', 'URL', 'Poziom ryzyka', 'Status'];
    rows = items.map((f) => [
      f.id,
      date(f),
      PLATFORM_LABEL[f.platform],
      firm(f)?.name,
      f.rules.filter((r) => r.status === 'VIOLATION').map((r) => r.ruleId).join(', '),
      f.text,
      f.url,
      RISK_LABEL[f.riskLevel],
      STATUS_LABEL[f.status],
    ]);
  } else {
    header = ['ID', 'Data wykrycia', 'Platforma', 'Podmiot', 'Status w rejestrze KNF', 'Treść oferty', 'URL', 'Poziom ryzyka', 'Status'];
    rows = items.map((f) => [
      f.id,
      date(f),
      PLATFORM_LABEL[f.platform],
      advisor(f)?.name ?? f.author.displayName ?? f.author.handle,
      advisor(f) ? REGISTER_LABEL[advisor(f)!.knfRegister.status] : '',
      f.text,
      f.url,
      RISK_LABEL[f.riskLevel],
      STATUS_LABEL[f.status],
    ]);
  }
  const csv = '﻿' + [header, ...rows].map((r) => r.map(csvCell).join(';')).join('\r\n');
  res.setHeader('Content-Type', 'text/csv; charset=utf-8');
  res.setHeader('Content-Disposition', `attachment; filename="investwatch-modul-${moduleId}-${dayKey(new Date())}.csv"`);
  res.send(csv);
});

app.get('/api/campaigns', (req, res) => {
  const r = dateRange(req.query);
  const from = Number.isFinite(r.from) ? r.from : Date.now() - 29 * DAY;
  const to = Number.isFinite(r.to) ? Math.min(r.to, Date.now()) : Date.now();
  const minSize = Number(str(req.query, 'minSize') ?? 0);
  const statuses = arr(req.query, 'status') as CampaignStatus[];
  let items = [...world.campaigns.keys()]
    .map((id) => campaignListItem(id, from, to))
    .filter((c): c is CampaignListItem => !!c)
    .filter((c) => new Date(c.lastSeen).getTime() >= from && new Date(c.firstSeen).getTime() <= to)
    .filter((c) => c.size >= minSize)
    .filter((c) => !statuses.length || statuses.includes(c.status));
  const [field, dir] = (str(req.query, 'sort') ?? 'size:desc').split(':');
  const sign = dir === 'asc' ? 1 : -1;
  const key = (c: CampaignListItem): number | string =>
    field === 'lastSeen' ? c.lastSeen : field === 'scamShare' ? c.scamShare : field === 'avgScam' ? c.avgScam : c.size;
  items = items.sort((a, b) => (key(a) < key(b) ? -sign : key(a) > key(b) ? sign : 0));
  const body: Page<CampaignListItem> = { items, total: items.length, page: 1, pageSize: items.length };
  res.json(body);
});

app.get('/api/campaigns/:id', (req, res) => {
  const campaign = world.campaigns.get(req.params.id);
  if (!campaign) return void notFound(res, 'Nie ma takiej kampanii');
  const members = (world.members.get(campaign.id) ?? [])
    .map((id) => world.byId.get(id))
    .filter((f): f is Finding => !!f)
    .sort((a, b) => b.fetchedAt.localeCompare(a.fetchedAt))
    .map(toSummary);
  const body: CampaignDetail = { campaign, graph: campaignGraph(world, campaign.id), members };
  res.json(body);
});

app.get('/api/indicators/:type/:value', (req, res) => {
  const type = req.params.type as IndicatorFindings['indicator']['type'];
  const value = req.params.value;
  const ids = world.index.get(`${type}:${value}`);
  if (!ids) return void notFound(res, 'Nie ma takiego wskaźnika');
  const findings = [...ids]
    .map((id) => world.byId.get(id))
    .filter((f): f is Finding => !!f)
    .sort((a, b) => b.fetchedAt.localeCompare(a.fetchedAt))
    .slice(0, 200)
    .map(toSummary);
  const body: IndicatorFindings = { indicator: { type, value }, findings };
  res.json(body);
});

// makiety zrzutów stron docelowych i klatek wideo (SVG)
app.get('/api/assets/landing/:id/:idx/:file', (req, res) => {
  const page = world.byId.get(req.params.id)?.landingPages[Number(req.params.idx)];
  const variant = req.params.file === 'mobile.svg' ? 'mobile' : req.params.file === 'desktop.svg' ? 'desktop' : null;
  if (!page || !variant) return void notFound(res);
  res.setHeader('Content-Type', 'image/svg+xml');
  res.setHeader('Cache-Control', 'public, max-age=3600');
  res.send(landingSvg(page, variant));
});

app.get('/api/assets/frame/:id/:file', (req, res) => {
  const idx = Number(req.params.file.replace(/\.svg$/, ''));
  const frame = world.byId.get(req.params.id)?.media?.keyframes[idx];
  if (!frame) return void notFound(res);
  res.setHeader('Content-Type', 'image/svg+xml');
  res.setHeader('Cache-Control', 'public, max-age=3600');
  res.send(frameSvg(frame.ocrText, frame.t));
});

// ---------------------------------------------------------------------------
// Socket.io + emisja nowych rekordów
// ---------------------------------------------------------------------------

const httpServer = createServer(app);
const io = new Server<ClientToServerEvents, ServerToClientEvents>(httpServer, {
  cors: { origin: CORS_ORIGIN },
  serveClient: false,
});

io.on('connection', (socket) => {
  log(`klient połączony (${socket.id}), aktywnych: ${io.engine.clientsCount}`);
  socket.on('disconnect', () => log(`klient rozłączony (${socket.id})`));
});

/** Zapisane progi działają po restarcie tylko wtedy, gdy ai-service potrafi je przeliczyć. */
async function restoreThresholds(data: RealData): Promise<void> {
  const saved = data.savedThresholds;
  if (!saved) return;
  try {
    const results = await rescoreViaAi(AI_URL, data, saved.values, [...world.byId.keys()], true);
    world.thresholds = saved;
    applyRescore(data, results);
    log(`przywrócono progi ${saved.version}`);
  } catch (e) {
    log(`nie przywrócono progów ${saved.version}, działają progi z importu: ${(e as Error).message}`);
  }
}

async function start(): Promise<void> {
  try {
    if (DATA_MODE === 'real') {
      const { file, state } = await loadRealFile();
      real = loadRealWorld(file, state, new Date());
    }
    world = real?.world ?? createWorld(SEED, new Date());
    const entityCount = registerEntityRoutes(app, DATA_MODE === 'real' ? await loadEntitySnapshot() : readSnapshotFile(), DATA_MODE === 'real');
    log(`podmioty: ${entityCount} (rejestr KNF + rekordy, źródło: ${DATA_MODE === 'real' ? 'Postgres' : 'entities.snapshot.json'})`);
  } catch (e) {
    process.stderr.write(`[api] ${(e as Error).message}\n`);
    process.exit(1);
  }
  app.use('/api', (_req, res) => {
    notFound(res, 'Nieznany endpoint');
  });
  const data = real;
  if (data) await restoreThresholds(data);
  httpServer.listen(PORT, () => {
    log(`API: http://localhost:${PORT}/api, tryb ${DATA_MODE}, ${world.findings.length} rekordów, ${world.campaigns.size} kampanii`);
    if (data) {
      log(`dane z ${data.generatedAt}, model ${data.modelVersion}`);
      void pullJobFindings(data);
      setInterval(() => void pullJobFindings(data), 5000).unref();
    }
  });
}

void start();

