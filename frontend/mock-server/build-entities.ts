// Buduje mock-server/entities.snapshot.json: oś podmiotu (rejestr KNF) + zebrane rekordy.
// Źródła (prawdziwe pliki repo):
//   - data/entity_fixtures.json: wynik app/backend/scripts/build_fixtures.py
//     (data/export/*/records.jsonl, data/monitor/*, linkowanie z app/backend/inwestwatch_api/entities.py);
//     rekordy `mock` i wyniki klasyfikatora mock-v0 są pomijane,
//   - wyniki: werdykty LLM z mock-server/data/findings.real.json, a dla pozostałych rekordów POST /ingest w ai-service
//     (AI_URL, domyślnie http://localhost:8000; pamięć podręczna w ml/data/entity_scores.json),
//   - rejestr KNF: ../data/knf_entities.json (760 wpisów), uzupełniany z ml/src/investwatch_ml/knf_register.json.
// Uruchom: npm run entities:build
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import type {
  EntityAlert,
  EntityFinding,
  EntityItem,
  EntityModule,
  KnfCategory,
  KnfEntity,
  KnfEntityDetail,
  LegibilityCheck,
  PageChange,
  PageSnapshot,
  RegistryEntry,
} from '../src/api/entityTypes';

const FRONT = process.cwd();
const REPO = join(FRONT, '..');
const FIXTURES = process.env.ENTITY_FIXTURES ?? join(REPO, 'data', 'entity_fixtures.json');
const KNF_FULL = process.env.KNF_FILE ?? join(REPO, '..', 'data', 'knf_entities.json');
const KNF_ML = join(REPO, 'ml', 'src', 'investwatch_ml', 'knf_register.json');
const OUT = join(FRONT, 'mock-server', 'entities.snapshot.json');
const REAL_FINDINGS = process.env.REAL_DATA_PATH ?? join(FRONT, 'mock-server', 'data', 'findings.real.json');
const SCORE_CACHE = join(REPO, 'ml', 'data', 'entity_scores.json');
const AI_URL = (process.env.AI_URL ?? 'http://localhost:8000').replace(/\/$/, '');
const BATCH_SIZE = 16;

/* eslint-disable @typescript-eslint/no-explicit-any */
type Raw = Record<string, any>;

const RULE_PL: Record<string, string> = {
  R01: 'Brak identyfikacji firmy',
  R02: 'Brak oznaczenia reklamy',
  R03: 'Twierdzenie o zysku bez informacji o ryzyku',
  R04: 'Rozmiar czcionki ostrzeżenia',
  R05: 'Ekspozycja i kontrast ostrzeżenia',
  R06: 'Ryzyko ukryte w przypisach',
  R07: 'Informacja o ryzyku dalej niż 1 kliknięcie',
  R08: 'Responsywność na urządzeniach',
  R09: 'Zrozumiałość dla odbiorcy',
  R10: 'Ostrzeżenie w innym języku',
  R11: 'Porównanie produktów bez źródła',
  R12: 'Wyniki historyczne: okres i waluta',
  R13: 'Dominacja wyników historycznych',
  R14: 'Brak zastrzeżenia przy wynikach historycznych',
  R15: 'Prognoza bez zastrzeżenia',
  R16: 'Informacja podatkowa bez zastrzeżenia',
  R17: 'Sugerowanie aprobaty organu nadzoru',
  R18: 'Nadzór jako argument bezpieczeństwa',
  'M1.PROMO': 'Reklama firmy przez podmiot trzeci',
  'M3.ADV': 'Możliwe doradztwo bez zezwolenia',
  'M1.REF': 'Kod polecający / afiliacja',
  'M1.NORISK': 'Promocja przez osobę trzecią bez informacji o ryzyku',
  'M1.PAID': 'Płatne lokowanie przez osobę trzecią',
  'M3.REC': 'Rekomendacja kupna / sprzedaży',
  'M3.RET': 'Obietnica zwrotu',
  'M3.SIG': 'Sygnały / zaproszenie do zamkniętej grupy',
};

const PAGE_LABEL_PL: Record<string, string> = {
  'Home (PL)': 'Strona główna',
  'Forex CFD': 'CFD na forex',
  'Index CFD': 'CFD na indeksy',
  'Commodity CFD': 'CFD na surowce',
  'Interest on cash (promo)': 'Oprocentowanie gotówki (promocja)',
  'Instrument specification / fees': 'Specyfikacja instrumentów / opłaty',
  'CFD trading': 'Handel CFD',
  'Interest on balance (promo)': 'Oprocentowanie salda (promocja)',
  Fees: 'Opłaty',
  Crypto: 'Kryptowaluty',
  'General risk disclosure': 'Ogólne ujawnienie ryzyka',
  'Crypto CFD': 'CFD na kryptowaluty',
  'Promotion (Chicago Bulls)': 'Promocja (Chicago Bulls)',
  'Disclosures / legal': 'Dokumenty prawne',
  Invest: 'Inwestowanie',
  'Pricing / fees': 'Cennik / opłaty',
  'Legal documentation': 'Dokumentacja prawna',
  'Help centre: What is CFD (EN)': 'Centrum pomocy: czym jest CFD (EN)',
  'Help centre: CFD losses (EN)': 'Centrum pomocy: straty na CFD (EN)',
  'Help centre: fees (EN)': 'Centrum pomocy: opłaty (EN)',
  'Stock trading': 'Handel akcjami',
  Legal: 'Dokumenty prawne',
};

const PLATFORM_PL: Record<string, string> = {
  google_ads: 'Google Ads',
  meta_ads: 'Meta Ads',
  bing_ads: 'Bing Ads',
  youtube: 'YouTube',
  tiktok: 'TikTok',
  website: 'Strona WWW',
};

function legibilityCheck(raw: Raw | null | undefined): LegibilityCheck | null {
  if (!raw) return null;
  return {
    status: raw.status,
    failures: (raw.failures as Raw[]).map((f) => ({ rule: f.rule, metric: f.metric, value: f.value, threshold: f.threshold, text: f.text })),
  };
}

function summaryPl(s: string): string {
  return s.replace(/(\d+) lines? added, (\d+) removed(?:, (\d+) style changes)?/g, (_m, a, r, st) => `+${a} / −${r} linii${st ? `, ${st} zmian stylu` : ''}`);
}

const LIST_CATEGORY: Record<string, KnfCategory> = {
  BROKERAGE_HOUSE: 'domy_maklerskie',
  BANK: 'banki_maklerskie',
  FOREIGN_BRANCH: 'zagraniczne_oddzialy',
  CROSS_BORDER: 'zagraniczne_bez_oddzialu',
};

const read = (p: string): Raw => JSON.parse(readFileSync(p, 'utf8'));

function slug(s: string): string {
  return (
    s
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '') || 'podmiot'
  );
}

function loadRegistry(): { entries: RegistryEntry[]; source: string } {
  // pełny plik rejestru nie jest w repo: bez niego zachowujemy wpisy z poprzedniego snapshotu
  if (!existsSync(KNF_FULL) && existsSync(OUT)) {
    const seen = new Map<string, RegistryEntry>();
    for (const e of read(OUT).entities as Raw[]) for (const r of e.registryEntries as RegistryEntry[]) seen.set(r.name, r);
    if (seen.size) return { entries: [...seen.values()], source: 'entities.snapshot.json' };
  }
  const ml = read(KNF_ML).entities as Raw[];
  const mlByName = new Map(ml.map((r) => [String(r.name), r]));
  if (existsSync(KNF_FULL)) {
    const rows = read(KNF_FULL) as unknown as Raw[];
    const entries = rows.map((r): RegistryEntry => {
      const m = mlByName.get(r.name);
      return {
        name: r.name,
        aliases: r.aliases?.length ? r.aliases : (m?.aliases ?? []),
        category: r.category,
        country: r.country,
        supervisor: m?.supervisor ?? null,
        registeredAt: r.details?.['Data zezwolenia'] ?? m?.registeredAt ?? null,
        address: r.address ?? null,
        sourceUrl: r.source_url ?? null,
      };
    });
    return { entries, source: 'data/knf_entities.json' };
  }
  const entries = ml.map(
    (r): RegistryEntry => ({
      name: r.name,
      aliases: r.aliases ?? [],
      category: LIST_CATEGORY[(r.lists as string[]).find((l) => l !== 'CROSS_BORDER') ?? 'CROSS_BORDER'] ?? 'zagraniczne_bez_oddzialu',
      country: r.country,
      supervisor: r.supervisor ?? null,
      registeredAt: r.registeredAt ?? null,
      address: null,
      sourceUrl: null,
    }),
  );
  return { entries, source: 'ml/src/investwatch_ml/knf_register.json' };
}

interface Verdict {
  modules: number[];
  rules: Raw[];
  riskLevel: string;
  model: string;
}

const SOURCE_BY_PLATFORM: Record<string, string> = {
  google_ads: 'google_ads_transparency',
  meta_ads: 'meta_ad_library',
  bing_ads: 'microsoft_ad_library',
  youtube: 'youtube',
  tiktok: 'tiktok',
  website: 'web',
};
const SEVERITY_BY_RISK: Record<string, EntityFinding['severity']> = { CRITICAL: 'high', HIGH: 'high', MEDIUM: 'medium', LOW: 'low' };
const RULE_KEY: Record<string, string> = { M1_PROMO: 'M1.PROMO', M3_ADVISORY: 'M3.ADV', M3_RECOMMENDATION: 'M3.REC' };

function ruleKey(id: string): string {
  const n = /^(\d+)/.exec(id);
  return n ? `R${n[1].padStart(2, '0')}` : (RULE_KEY[id] ?? id);
}

async function ai<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${AI_URL}${path}`, {
    method: body ? 'POST' : 'GET',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(900_000),
  });
  if (!res.ok) throw new Error(`ai-service ${path}: HTTP ${res.status}`);
  return (await res.json()) as T;
}

/** Werdykt dla każdego rekordu: LLM z głównego zbioru, inaczej model ai-service. Bez ai-service build się przerywa. */
async function loadVerdicts(rawItems: Raw[], ownerName: Map<string, string>): Promise<{ verdicts: Map<string, Verdict>; llm: number; model: number }> {
  const reviewed = new Map<string, Raw>();
  if (existsSync(REAL_FINDINGS)) for (const f of read(REAL_FINDINGS).findings as Raw[]) if (f.llm) reviewed.set(f.url, f);
  const { modelVersion } = await ai<{ modelVersion: string }>('/health');
  const stored = existsSync(SCORE_CACHE) ? read(SCORE_CACHE) : null;
  const cache: Record<string, Verdict> = stored?.modelVersion === modelVersion ? stored.verdicts : {};
  const verdicts = new Map<string, Verdict>();
  const todo: Raw[] = [];
  let llm = 0;
  for (const i of rawItems) {
    const f = reviewed.get(i.source_url);
    if (f) {
      verdicts.set(i.id, { modules: f.modules, rules: f.rules, riskLevel: f.riskLevel, model: f.llm.model ?? f.modelVersion });
      llm++;
    } else if (cache[i.id]) verdicts.set(i.id, cache[i.id]);
    else todo.push(i);
  }
  for (let n = 0; n < todo.length; n += BATCH_SIZE) {
    const batch = todo.slice(n, n + BATCH_SIZE);
    const records = batch.map((i) => ({
      source: SOURCE_BY_PLATFORM[i.platform] ?? 'web',
      source_url: i.source_url,
      author: i.author,
      // własna reklama firmy: wydawcą jest wpis rejestru, nawet gdy strona ma inną nazwę handlową
      sponsor: i.author_is_entity ? ownerName.get(i.entity_ids[0]) : i.channel === 'ad' ? i.author : undefined,
      published_at: i.published_at,
      fetched_at: i.fetched_at,
      text: i.text,
      links: [],
      content_type: i.channel === 'ad' ? 'ad' : 'post',
    }));
    const { results } = await ai<{ results: { item: Raw; analysis: Raw }[] }>('/ingest', { records });
    const byUrl = new Map(results.map((r) => [r.item.url as string, r.analysis]));
    for (const i of batch) {
      const a = byUrl.get(i.source_url);
      // rekord bez treści do analizy nie ma wyniku
      const v: Verdict = a
        ? { modules: a.modules, rules: a.rules, riskLevel: a.riskLevel, model: a.modelVersion }
        : { modules: [], rules: [], riskLevel: 'LOW', model: modelVersion };
      cache[i.id] = v;
      verdicts.set(i.id, v);
    }
    writeFileSync(SCORE_CACHE, JSON.stringify({ modelVersion, verdicts: cache }));
    process.stderr.write(`ai-service: ${Math.min(n + BATCH_SIZE, todo.length)}/${todo.length}\n`);
  }
  return { verdicts, llm, model: rawItems.length - llm };
}

function ruleHit(rule: Raw, text: Record<string, string>): EntityFinding['ruleHits'][number] {
  const ruleId = ruleKey(rule.ruleId);
  const quote = rule.evidence?.[0]?.text as string | undefined;
  const sections = Object.entries(text);
  const found = quote ? sections.find(([, t]) => t.includes(quote)) : undefined;
  return {
    ruleId,
    label: RULE_PL[ruleId] ?? ruleId,
    evidence: quote ?? 'Brak wymaganej informacji w treści.',
    section: found?.[0] ?? sections[0]?.[0] ?? 'text',
    span: found && quote ? [found[1].indexOf(quote), found[1].indexOf(quote) + quote.length] : null,
  };
}

/** Wyniki modułów: M2 tylko dla własnych materiałów podmiotu, M1 i M3 tylko dla autorów trzecich. */
function buildFindings(rawItems: Raw[], verdicts: Map<string, Verdict>): { findings: EntityFinding[]; skipped: number } {
  const findings: EntityFinding[] = [];
  let skipped = 0;
  for (const i of rawItems) {
    const v = verdicts.get(i.id);
    if (!v) continue;
    for (const n of v.modules) {
      const module = `M${n}` as EntityModule;
      if ((module === 'M2') !== Boolean(i.author_is_entity)) {
        skipped++;
        continue;
      }
      const rules = v.rules.filter((r) => {
        const numeric = /^\d/.test(r.ruleId);
        if (module === 'M3') return (r.ruleId === 'M3_ADVISORY' && r.status === 'VIOLATION') || (r.ruleId === 'M3_RECOMMENDATION' && r.status === 'NOT_CHECKED');
        return r.status === 'VIOLATION' && (numeric || (module === 'M1' && r.ruleId === 'M1_PROMO'));
      });
      if (!rules.length) continue;
      const byRule = new Map(rules.map((r) => [ruleKey(r.ruleId), ruleHit(r, i.text)]));
      for (const entityId of i.entity_ids as string[]) {
        findings.push({
          id: `fnd_${createHash('sha256').update(`${i.id}|${entityId}|${module}`).digest('hex').slice(0, 10)}`,
          itemId: i.id,
          entityId,
          module,
          score: Math.round(Math.max(...rules.map((r) => Number(r.score) || 0)) * 1000) / 1000,
          severity: SEVERITY_BY_RISK[v.riskLevel] ?? 'low',
          ruleHits: [...byRule.values()],
          model: v.model,
          createdAt: i.published_at ?? i.fetched_at,
          mock: false,
        });
      }
    }
  }
  return { findings, skipped };
}

function findingsByDay(findings: EntityFinding[], now: Date): { date: string; M1: number; M2: number; M3: number }[] {
  const days = Array.from({ length: 30 }, (_, k) => ({
    date: new Date(now.getTime() - (29 - k) * 86_400_000).toISOString().slice(0, 10),
    M1: 0,
    M2: 0,
    M3: 0,
  }));
  const byDate = new Map(days.map((d) => [d.date, d]));
  for (const f of findings) {
    const d = byDate.get(new Date(f.createdAt).toISOString().slice(0, 10));
    if (d) d[f.module]++;
  }
  return days;
}

async function main(): Promise<void> {
  const fx = read(FIXTURES);
  const { entries, source } = loadRegistry();
  const byName = new Map(entries.map((e) => [e.name, e]));
  const now = new Date();
  const realItems = (fx.items as Raw[]).filter((i) => !i.mock);
  const ownerName = new Map((fx.entities as Raw[]).map((e) => [e.id as string, e.registry_entries[0]?.name as string]));
  const { verdicts, llm, model } = await loadVerdicts(realItems, ownerName);
  const { findings, skipped } = buildFindings(realItems, verdicts);

  const items: EntityItem[] = realItems.map((i) => ({
    id: i.id,
    entityIds: i.entity_ids,
    channel: i.channel,
    platform: i.platform,
    sourceUrl: i.source_url,
    author: i.author,
    authorIsEntity: i.author_is_entity,
    publishedAt: i.published_at,
    fetchedAt: i.fetched_at,
    text: i.text,
    media: i.media ?? [],
    ocrLines: ((i.ocr_lines ?? []) as Raw[]).map((l) => ({
      text: l.text,
      box: l.box,
      boxHeightPx: l.box_height_px,
      relFontSize: l.rel_font_size,
      contrastRatio: l.contrast_ratio ?? null,
      isDisclosure: l.is_disclosure,
    })),
    legibility: i.legibility
      ? {
          disclosureInText: i.legibility.disclosure_in_text,
          disclosureOnImage: i.legibility.disclosure_on_image ?? null,
          imageWidth: i.legibility.image_width ?? null,
          imageHeight: i.legibility.image_height ?? null,
          dominantLinePx: i.legibility.dominant_line_px ?? null,
          lines: i.legibility.lines ?? null,
          disclosureLines: i.legibility.disclosure_lines ?? null,
        }
      : null,
    legibilityCheck: legibilityCheck(i.legibility_check),
    mock: i.mock,
  }));
  const itemById = new Map(items.map((i) => [i.id, i]));

  const pages = (fx.pages as Raw[]).map((p) => ({
    pageId: p.page_id as string,
    entityId: p.entity_id as string,
    url: p.url as string,
    label: PAGE_LABEL_PL[p.label] ?? (p.label as string),
  }));

  const snapshots: PageSnapshot[] = (fx.snapshots as Raw[]).filter((s) => !s.mock).map((s) => ({
    id: s.id,
    pageId: s.page_id,
    entityId: s.entity_id,
    url: s.url,
    fetchedAt: s.fetched_at,
    textSha256: s.text_sha256,
    text: s.text,
    riskWarning: {
      present: s.risk_warning.present,
      cfdLossPct: s.risk_warning.cfd_loss_pct,
      text: s.risk_warning.text,
      aboveFold: s.risk_warning.above_fold,
    },
    screenshots: s.screenshots ?? null,
    legibility: s.legibility
      ? Object.fromEntries(
          Object.entries(s.legibility as Record<string, Raw>).map(([vp, l]) => [
            vp,
            {
              dominantFontPx: l.dominant_font_px,
              disclosureBlocks: ((l.disclosure_blocks ?? []) as Raw[]).map((b) => ({
                text: b.text,
                fontSizePx: b.font_size_px,
                relFontSize: b.rel_font_size,
                contrastRatio: b.contrast_ratio ?? null,
                contrastSource: b.contrast_source,
                y: b.y,
                aboveFold: b.above_fold,
              })),
            },
          ]),
        )
      : null,
    legibilityCheck: legibilityCheck(s.legibility_check),
    mock: s.mock,
  }));

  const changes: PageChange[] = (fx.changes as Raw[]).filter((c) => !c.mock).map((c) => ({
    id: c.id,
    pageId: c.page_id,
    entityId: c.entity_id,
    fromSnapshot: c.from_snapshot,
    toSnapshot: c.to_snapshot,
    detectedAt: c.detected_at,
    summary: summaryPl(c.summary),
    addedLines: c.added_lines,
    removedLines: c.removed_lines,
    styleChanges: ((c.style_changes ?? []) as Raw[]).map((x) => ({
      text: x.text,
      viewport: x.viewport,
      field: x.field,
      before: x.before,
      after: x.after,
      contrastBefore: x.contrast_before ?? null,
      contrastAfter: x.contrast_after ?? null,
      relSizeBefore: x.rel_size_before ?? null,
      relSizeAfter: x.rel_size_after ?? null,
    })),
    assessment: c.assessment ?? null,
    mock: c.mock,
  }));

  const alerts: EntityAlert[] = findings
    .filter((f) => f.severity === 'high')
    .sort((x, y) => y.createdAt.localeCompare(x.createdAt))
    .map((f) => {
      const it = itemById.get(f.itemId);
      const h = f.ruleHits[0];
      return {
        id: `alr_${f.id.slice(4)}`,
        createdAt: f.createdAt,
        entityId: f.entityId,
        kind: 'finding',
        severity: 'high',
        title: `${/^R\d/.test(h.ruleId) ? `${h.ruleId} ` : ''}${h.label} — ${it?.author ?? f.itemId} (${PLATFORM_PL[it?.platform ?? ''] ?? it?.platform ?? ''})`,
        ref: { findingId: f.id, changeId: null, itemId: f.itemId },
        status: 'new',
        mock: false,
      };
    });

  // podmioty z danymi: grupy marek z app/backend (wpisy rejestru dopasowane po nazwie)
  const grouped = new Set<string>();
  const withData: KnfEntityDetail[] = (fx.entities as Raw[]).map((e) => {
    const reg = (e.registry_entries as Raw[]).map((r) => byName.get(r.name)).filter((r): r is RegistryEntry => !!r);
    reg.forEach((r) => grouped.add(r.name));
    const primary = reg.find((r) => r.country === 'Polska') ?? reg[0];
    const own = findings.filter((f) => f.entityId === e.id);
    const avg = (rows: EntityFinding[]) => (rows.length ? Math.round((rows.reduce((t, f) => t + f.score, 0) / rows.length) * 100) / 100 : 0);
    const modules = Object.fromEntries(
      (['M1', 'M2', 'M3'] as EntityModule[]).map((m) => {
        const rows = own.filter((f) => f.module === m);
        return [m, { findings: rows.length, avgScore: avg(rows) }];
      }),
    ) as KnfEntityDetail['modules'];
    const weekAgo = now.getTime() - 7 * 86_400_000;
    return {
      id: e.id,
      name: e.name,
      category: primary?.category ?? 'zagraniczne_bez_oddzialu',
      country: primary?.country ?? '',
      registryEntries: reg,
      domains: e.domains,
      hasData: true,
      monitoredPages: pages.filter((p) => p.entityId === e.id).length,
      socialHandles: e.social_handles,
      kpis: {
        items: e.kpis.items,
        findingsOpen: own.length,
        alertsNew: alerts.filter((a) => a.entityId === e.id).length,
        riskScore: avg(own),
        pagesChanged7d: new Set(changes.filter((c) => c.entityId === e.id && new Date(c.detectedAt).getTime() >= weekAgo).map((c) => c.pageId)).size,
      },
      modules,
      platforms: e.platforms,
    };
  });

  const used = new Set(withData.map((e) => e.id));
  const rest: KnfEntity[] = entries
    .filter((r) => !grouped.has(r.name))
    .map((r) => {
      let id = slug(r.name);
      for (let n = 2; used.has(id); n++) id = `${slug(r.name)}-${n}`;
      used.add(id);
      return {
        id,
        name: r.name,
        category: r.category,
        country: r.country,
        registryEntries: [r],
        domains: [],
        hasData: false,
        monitoredPages: 0,
        socialHandles: {},
        kpis: null,
      };
    });

  const ov = fx.overview as Raw;
  const snapshot = {
    generatedAt: now.toISOString(),
    sources: { fixtures: 'data/entity_fixtures.json', registry: source, registryEntries: entries.length },
    entities: [...withData, ...rest],
    items,
    findings,
    pages,
    snapshots,
    changes,
    alerts,
    findingsByDay: findingsByDay(findings, now),
    itemsByPlatform: ov.items_by_platform,
  };
  writeFileSync(OUT, JSON.stringify(snapshot));
  process.stdout.write(
    `entities.snapshot.json: ${snapshot.entities.length} podmiotów (${withData.length} z danymi, rejestr ${entries.length} z ${source}), ` +
      `${items.length} rekordów, ${findings.length} wyników (werdykty: ${llm} LLM, ${model} ai-service; pominięte niezgodne z autorem: ${skipped}), ${pages.length} stron, ${changes.length} zmian, ${alerts.length} alertów\n`,
  );
}

main().catch((e: unknown) => {
  process.stderr.write(`entities:build: ${(e as Error).message}\n`);
  process.exit(1);
});
