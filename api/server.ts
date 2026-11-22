// API InvestWatch (kontrakt: docs/frontend-agent.md, sekcja 4). Dane z Postgresa (db.ts) i MinIO, oceny z ai-service.

import { createServer } from 'node:http';
import express, { type Request, type Response } from 'express';
import { Server } from 'socket.io';
import type {
  BulkStatusUpdate,
  ClientToServerEvents,
  ContentType,
  Finding,
  FindingSummary,
  HistoryPage, HistoryRow,
  FlagKey,
  IndicatorFindings,
  Instrument,
  ModuleId,
  Page,
  ServerToClientEvents,
  StatsOverview,
  Status,
  Thresholds,
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
import { applyModules, buildEvalSet, modulesAtConfidence, previewModules, saveModuleThresholds, withModuleKeys } from './calibration';
import { findingsSince, firstThresholds, type LoadProgress, loadEntitySnapshot, loadProgress, loadRealFile, saveStatuses } from './db';
import { registerEntityRoutes, type Snapshot } from './entities';
import { egoGraph } from './graph';
import { RULES } from './rules';
import { addRealFinding, loadRealWorld, type RealData, type World } from './real';

try {
  process.loadEnvFile('.env');
} catch {
  // brak .env – zostają wartości domyślne
}

const PORT = Number(process.env.API_PORT ?? 4000);
const CORS_ORIGIN = process.env.CORS_ORIGIN ?? '*';

const log = (msg: string) => process.stdout.write(`[api] ${msg}\n`);

// Wypełniane w start() z Postgresa.
let real!: RealData;
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
const isIncident = (f: Finding) => f.modules.length > 0;

function filterFindings(q: Query): Finding[] {
  const { from, to } = dateRange(q);
  const platforms = arr(q, 'platform');
  const modules = arr(q, 'module').map(Number);
  const levels = arr(q, 'riskLevel');
  const statuses = arr(q, 'status');
  const flags = arr(q, 'flag') as FlagKey[];
  const text = str(q, 'q')?.toLowerCase();
  const confidence = str(q, 'confidence') === undefined ? NaN : Number(str(q, 'confidence'));
  return world.findings.filter((f) => {
    const t = new Date(f.fetchedAt).getTime();
    if (t < from || t > to) return false;
    if (platforms.length && !platforms.includes(f.platform)) return false;
    const fModules = Number.isFinite(confidence) ? modulesAtConfidence(f, confidence) : f.modules;
    if (modules.length && !fModules.some((m) => modules.includes(m))) return false;
    if (levels.length && !levels.includes(f.riskLevel)) return false;
    if (statuses.length && !statuses.includes(f.status)) return false;
    if (flags.length && !flags.every((fl) => (f.flags[fl]?.p ?? 0) >= th(`flags.${fl}`))) return false;
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
    riskScore: f.riskScore,
    riskLevel: f.riskLevel,
    status: f.status,
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

// Loader (ocena w tle) i scrape-worker zapisują wyniki w Postgresie; API dociąga je co POLL_MS i wysyła przez socket.
const POLL_MS = 5000;
let cursor: string | null = null;
let lastProgress = '';
let polling = false;
let updateEntities: (s: Snapshot) => void = () => {};

async function pollDb(): Promise<void> {
  if (polling) return;
  polling = true;
  try {
    if (!Object.keys(world.thresholds.values).length) {
      const t = await firstThresholds();
      if (t) {
        world.thresholds = withModuleKeys(t);
        io.emit('thresholds:updated', world.thresholds);
      }
    }
    const page = await findingsSince(cursor);
    cursor = page.cursor;
    const added = page.findings.map((f) => addRealFinding(real, f)).filter((f): f is Finding => !!f);
    applyModules(added, world.thresholds.values);
    for (const f of added) {
      io.emit('finding:new', f);
      if (f.riskLevel === 'HIGH' || f.riskLevel === 'CRITICAL') io.emit('finding:high_risk', f);
    }
    const progress = await loadProgress();
    const key = JSON.stringify(progress);
    if (added.length || (key !== lastProgress && !progress.running)) updateEntities(await loadEntitySnapshot());
    if (key !== lastProgress) {
      lastProgress = key;
      io.emit('load:progress', progress);
    }
    if (added.length) log(`baza: ${added.length} nowych rekordów`);
  } catch (e) {
    log(`postgres: ${(e as Error).message}`);
  } finally {
    polling = false;
  }
}

app.get('/api/load', (_req, res) => {
  loadProgress()
    .then((p) => res.json(p))
    .catch(() => res.status(503).json({ error: 'Baza danych jest niedostępna' }));
});

app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', findings: world.findings.length });
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
  return f;
}

/** Status i wpis historii trafiają do Postgresa przed odpowiedzią. */
async function persistStatuses(updated: Finding[], res: Response): Promise<boolean> {
  if (!updated.length) return true;
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
    groupBy === 'platform' ? [...PLATFORMS] : groupBy === 'riskLevel' ? [...RISK_LEVELS] : ['1', '2', '3'];
  const points = days.map((date) => ({ date, counts: Object.fromEntries(keys.map((k) => [k, 0])) as Record<string, number> }));
  const byDay = new Map(points.map((p) => [p.date, p]));
  for (const f of items) {
    const p = byDay.get(dayKey(new Date(f.fetchedAt)));
    if (!p) continue;
    if (groupBy === 'platform') p.counts[f.platform] += 1;
    else if (groupBy === 'riskLevel') p.counts[f.riskLevel] += 1;
    else for (const m of f.modules) p.counts[String(m)] += 1;
  }
  const body: Timeseries = { bucket: 'day', groupBy, keys, points };
  res.json(body);
});

// Wpisy importu i klasyfikacji nie są decyzjami analityków.
const AUTOMATED_USERS = new Set(['system', 'model']);

app.get('/api/history', (req, res) => {
  const { from, to } = dateRange(req.query);
  const user = str(req.query, 'user');
  const rows: HistoryRow[] = [];
  const users = new Set<string>();
  for (const f of world.findings) {
    for (const h of f.history) {
      if (AUTOMATED_USERS.has(h.user)) continue;
      const t = new Date(h.at).getTime();
      if (t < from || t > to) continue;
      users.add(h.user); // lista do filtra: wszyscy analitycy z okresu, nie tylko z bieżącej strony
      if (user && h.user !== user) continue;
      const body = (f.kind === 'transcript' && f.transcript ? f.transcript : f.text).replace(/\s+/g, ' ');
      rows.push({ ...h, findingId: f.id, platform: f.platform, author: f.author.handle, snippet: body.slice(0, 140), riskLevel: f.riskLevel });
    }
  }
  rows.sort((a, b) => b.at.localeCompare(a.at));
  const pageSize = Math.min(200, Math.max(1, Number(str(req.query, 'pageSize') ?? 50)));
  const page = Math.max(1, Number(str(req.query, 'page') ?? 1));
  const body: HistoryPage = { items: rows.slice((page - 1) * pageSize, page * pageSize), total: rows.length, page, pageSize, users: [...users].sort() };
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
  for (const key of Object.keys(world.thresholds.values)) {
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
  void saveRealThresholds(values, res);
});

async function saveRealThresholds(values: Record<string, number>, res: Response): Promise<void> {
  const proposed = { ...world.thresholds.values, ...values };
  const n = Number(world.thresholds.version.replace(/\D/g, '')) || 1;
  const next = { version: `v${n + 1}`, updatedAt: new Date().toISOString(), values: proposed };
  const before = new Map(world.findings.map((f) => [f.id, f.modules]));
  const changed = applyModules(world.findings, proposed);
  try {
    await saveModuleThresholds(next, changed);
  } catch (e) {
    for (const f of changed) f.modules = before.get(f.id) ?? f.modules;
    log(`postgres: ${(e as Error).message}`);
    return void res.status(503).json({ error: 'Nie zapisano progów w bazie' });
  }
  world.thresholds = next;
  io.emit('thresholds:updated', world.thresholds);
  log(`progi zapisane (${world.thresholds.version}), zmiana modułów: ${changed.length} rekordów`);
  res.json(world.thresholds);
}

app.post('/api/thresholds/preview', (req, res) => {
  const values = parseValues(req.body);
  if (!values) {
    res.status(400).json({ error: 'Progi muszą być liczbami z zakresu 0–1' });
    return;
  }
  res.json(previewModules(world.findings, world.thresholds.values, { ...world.thresholds.values, ...values }));
});

app.get('/api/calibration/eval-set', (_req, res) => {
  res.json(buildEvalSet(world.findings));
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

// ---------------------------------------------------------------------------
// Socket.io + emisja nowych rekordów
// ---------------------------------------------------------------------------

const httpServer = createServer(app);
// finding:new i load:progress: kontrakt przekazany frontowi (frontend/src/api/types.ts ma finding:high_risk)
type ApiEvents = ServerToClientEvents & {
  'finding:new': (f: Finding) => void;
  'load:progress': (p: LoadProgress) => void;
};
const io = new Server<ClientToServerEvents, ApiEvents>(httpServer, {
  cors: { origin: CORS_ORIGIN },
  serveClient: false,
});

io.on('connection', (socket) => {
  log(`klient połączony (${socket.id}), aktywnych: ${io.engine.clientsCount}`);
  socket.on('disconnect', () => log(`klient rozłączony (${socket.id})`));
});

/** Zapisane progi: moduły z pewności LLM przeliczane lokalnie (calibration.ts). */
function restoreThresholds(data: RealData): void {
  world.thresholds = withModuleKeys(data.savedThresholds ?? world.thresholds);
  applyModules(world.findings, world.thresholds.values);
  if (data.savedThresholds) log(`przywrócono progi ${data.savedThresholds.version}`);
}

async function start(): Promise<void> {
  try {
    const loaded = await loadRealFile();
    real = loadRealWorld(loaded.file, loaded.state, new Date());
    world = real.world;
    cursor = loaded.cursor;
    const snapshot = await loadEntitySnapshot();
    updateEntities = registerEntityRoutes(app, snapshot);
    log(`podmioty: ${snapshot.entities.length} (rejestr KNF + rekordy z Postgresa)`);
  } catch (e) {
    process.stderr.write(`[api] ${(e as Error).message}\n`);
    process.exit(1);
  }
  app.use('/api', (_req, res) => {
    notFound(res, 'Nieznany endpoint');
  });
  restoreThresholds(real);
  httpServer.listen(PORT, () => {
    log(`API: http://localhost:${PORT}/api, ${world.findings.length} rekordów, dane z ${real.generatedAt}, model ${real.modelVersion}`);
    void pollDb();
    setInterval(() => void pollDb(), POLL_MS).unref();
  });
}

void start();

