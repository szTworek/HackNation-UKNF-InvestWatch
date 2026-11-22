// Oś podmiotu: endpointy /api/entities*, /api/items/:id, /api/changes/:id, /api/entity-stats/overview.
// Dane z entities.snapshot.json (npm run entities:build). Rekordy, strony i rejestr są prawdziwe;
// wyniki klasyfikatora (mock-v0) i część historii stron to atrapy oznaczone `mock: true`.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import express, { type Express } from 'express';
import type {
  EntityAlert,
  EntityFinding,
  EntityItem,
  EntityModule,
  EntityOverview,
  KnfEntity,
  KnfEntityDetail,
  LegibilityStatus,
  MonitoredPage,
  PageChange,
  PageSnapshot,
} from '../src/api/entityTypes';

interface Snapshot {
  generatedAt: string;
  sources: { registryEntries: number };
  entities: KnfEntityDetail[];
  items: EntityItem[];
  findings: EntityFinding[];
  pages: { pageId: string; entityId: string; url: string; label: string }[];
  snapshots: PageSnapshot[];
  changes: PageChange[];
  alerts: EntityAlert[];
  findingsByDay: EntityOverview['findingsByDay'];
  itemsByPlatform: EntityOverview['itemsByPlatform'];
}

const MODULES: EntityModule[] = ['M1', 'M2', 'M3'];

export function registerEntityRoutes(app: Express, path = join(process.cwd(), 'mock-server', 'entities.snapshot.json')): number {
  const s = JSON.parse(readFileSync(path, 'utf8')) as Snapshot;
  const entityById = new Map(s.entities.map((e) => [e.id, e]));
  const itemById = new Map(s.items.map((i) => [i.id, i]));
  const findingsByItem = new Map<string, EntityFinding[]>();
  for (const f of s.findings) findingsByItem.set(f.itemId, [...(findingsByItem.get(f.itemId) ?? []), f]);
  const withFindings = (i: EntityItem) => ({ ...i, findings: findingsByItem.get(i.id) ?? [] });
  const listRow = (e: KnfEntityDetail): KnfEntity => ({
    id: e.id,
    name: e.name,
    category: e.category,
    country: e.country,
    registryEntries: e.registryEntries,
    domains: e.domains,
    hasData: e.hasData,
    monitoredPages: e.monitoredPages,
    socialHandles: e.socialHandles,
    kpis: e.kpis,
  });

  app.get('/api/entities', (_req, res) => {
    res.json(s.entities.map(listRow));
  });

  app.get('/api/entities/:id', (req, res) => {
    const e = entityById.get(req.params.id);
    if (!e) return res.status(404).json({ error: 'Nie znaleziono podmiotu' });
    res.json(e.hasData ? e : { ...e, modules: Object.fromEntries(MODULES.map((m) => [m, { findings: 0, avgScore: 0 }])), platforms: {} });
  });

  app.get('/api/entities/:id/items', (req, res) => {
    const id = req.params.id;
    if (!entityById.has(id)) return res.status(404).json({ error: 'Nie znaleziono podmiotu' });
    const q = req.query;
    let rows = s.items.filter((i) => i.entityIds.includes(id));
    if (q.channel) rows = rows.filter((i) => i.channel === q.channel);
    if (q.platform) rows = rows.filter((i) => i.platform === q.platform);
    let out = rows.map(withFindings);
    if (q.module) out = out.filter((i) => i.findings.some((f) => f.entityId === id && f.module === q.module));
    out.sort((a, b) => (b.publishedAt ?? '').localeCompare(a.publishedAt ?? '') || a.id.localeCompare(b.id));
    const offset = Math.max(0, Number(q.offset ?? 0));
    const limit = Math.min(1000, Math.max(1, Number(q.limit ?? 50)));
    res.json({ total: out.length, items: out.slice(offset, offset + limit) });
  });

  app.get('/api/entities/:id/pages', (req, res) => {
    const id = req.params.id;
    if (!entityById.has(id)) return res.status(404).json({ error: 'Nie znaleziono podmiotu' });
    const body: MonitoredPage[] = s.pages
      .filter((p) => p.entityId === id)
      .map((p) => ({
        pageId: p.pageId,
        url: p.url,
        label: p.label,
        lastSnapshot: s.snapshots.filter((x) => x.pageId === p.pageId).sort((a, b) => b.fetchedAt.localeCompare(a.fetchedAt))[0] ?? null,
        changes: s.changes.filter((c) => c.pageId === p.pageId).sort((a, b) => b.detectedAt.localeCompare(a.detectedAt)),
      }));
    res.json(body);
  });

  app.get('/api/entities/:id/alerts', (req, res) => {
    res.json(s.alerts.filter((a) => a.entityId === req.params.id));
  });

  app.get('/api/items/:id', (req, res) => {
    const it = itemById.get(req.params.id);
    if (!it) return res.status(404).json({ error: 'Nie znaleziono rekordu' });
    res.json(withFindings(it));
  });

  app.use('/api/screens', express.static(join(process.cwd(), '..', 'data', 'monitor', 'screens')));
  app.use('/api/media', express.static(join(process.cwd(), '..', 'data', 'media')));

  app.get('/api/changes/:id', (req, res) => {
    const c = s.changes.find((x) => x.id === req.params.id);
    if (!c) return res.status(404).json({ error: 'Nie znaleziono zmiany' });
    res.json({ ...c, from: s.snapshots.find((x) => x.id === c.fromSnapshot), to: s.snapshots.find((x) => x.id === c.toSnapshot) });
  });

  app.get('/api/entity-stats/overview', (_req, res) => {
    const withData = s.entities.filter((e) => e.hasData);
    const rules = new Map<string, { label: string; count: number }>();
    for (const f of s.findings)
      for (const h of f.ruleHits) {
        const r = rules.get(h.ruleId) ?? { label: h.label, count: 0 };
        r.count++;
        rules.set(h.ruleId, r);
      }
    const body: EntityOverview = {
      generatedAt: s.generatedAt,
      totals: {
        knfEntries: s.sources.registryEntries,
        entities: s.entities.length,
        entitiesWithData: withData.length,
        items: s.items.length,
        findings: s.findings.length,
        alertsNew: s.alerts.filter((a) => a.status === 'new').length,
        pages: s.pages.length,
        pageChanges30d: s.changes.length,
      },
      findingsByDay: s.findingsByDay,
      itemsByPlatform: s.itemsByPlatform,
      legibility: s.items.reduce(
        (acc, i) => (i.legibilityCheck ? { ...acc, [i.legibilityCheck.status]: acc[i.legibilityCheck.status] + 1 } : acc),
        { ok: 0, problem: 0, no_disclosure: 0 } as Record<LegibilityStatus, number>,
      ),
      heatmap: withData.map((e) => ({
        entityId: e.id,
        name: e.name,
        ...(Object.fromEntries(MODULES.map((m) => [m, e.modules[m].findings ? e.modules[m].avgScore : 0])) as Record<EntityModule, number>),
      })),
      topRules: [...rules.entries()]
        .map(([ruleId, r]) => ({ ruleId, ...r }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 10),
      recentChanges: [...s.changes]
        .sort((a, b) => b.detectedAt.localeCompare(a.detectedAt))
        .map((c) => {
          const p = s.pages.find((x) => x.pageId === c.pageId);
          return { ...c, pageLabel: p?.label ?? c.pageId, url: p?.url ?? '', entityName: entityById.get(c.entityId)?.name ?? c.entityId };
        }),
      recentAlerts: s.alerts.filter((a) => a.status === 'new').slice(0, 8),
    };
    res.json(body);
  });

  return s.entities.length;
}
