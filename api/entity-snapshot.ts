// Mapowanie danych osi podmiotu (kształt data/entity_fixtures.json, snake_case) na kontrakt UI (src/api/entityTypes.ts).
// Używają go: build-entities.ts (plik entities.snapshot.json dla DATA_MODE=mock) i db.ts (DATA_MODE=real, dane z Postgresa).
import type {
  EntityAlert,
  EntityFinding,
  EntityItem,
  EntityModule,
  KnfEntity,
  KnfEntityDetail,
  LegibilityCheck,
  PageChange,
  PageSnapshot,
  RegistryEntry,
} from '../frontend/src/api/entityTypes';

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
  'M1.REF': 'Kod polecający / afiliacja',
  'M1.NORISK': 'Promocja przez osobę trzecią bez informacji o ryzyku',
  'M1.PAID': 'Płatne lokowanie przez osobę trzecią',
  'M3.REC': 'Rekomendacja kupna / sprzedaży',
  'M3.RET': 'Obietnica zwrotu',
  'M3.SIG': 'Sygnały / zaproszenie do zamkniętej grupy',
};

const EVIDENCE_PL: Record<string, string> = {
  'No risk information found in ad text.': 'Brak informacji o ryzyku w treści reklamy.',
  'Entity promoted by a third party; no risk information.': 'Podmiot promowany przez osobę trzecią; brak informacji o ryzyku.',
  'Platform flag: includes paid promotion.': 'Flaga platformy: zawiera płatną promocję.',
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
  'General risk disclosure': 'Ogólna informacja o ryzyku',
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

/** `mock`: wyniki i alerty z klasyfikatora mock-v0 (plik fixtures), w danych z Postgresa false. */
export function buildSnapshot(fx: Raw, entries: RegistryEntry[], source: string, fixtures: string, mock: boolean) {
  const byName = new Map(entries.map((e) => [e.name, e]));

  const findings: EntityFinding[] = (fx.findings as Raw[]).map((f) => ({
    id: f.id,
    itemId: f.item_id,
    entityId: f.entity_id,
    module: f.module,
    score: f.score,
    severity: f.severity,
    ruleHits: (f.rule_hits as Raw[]).map((h) => ({
      ruleId: h.rule_id,
      label: RULE_PL[h.rule_id] ?? h.label,
      evidence: EVIDENCE_PL[h.evidence] ?? h.evidence,
      section: h.section,
      span: h.span && h.span[1] > h.span[0] ? h.span : null,
    })),
    model: f.model,
    createdAt: f.created_at,
    // mock-v0 z pliku fixtures: atrapa LLM (reguły słownikowe), daty wyników rozłożone na 30 dni
    mock,
  }));

  const items: EntityItem[] = (fx.items as Raw[]).map((i) => ({
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

  const snapshots: PageSnapshot[] = (fx.snapshots as Raw[]).map((s) => ({
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

  const changes: PageChange[] = (fx.changes as Raw[]).map((c) => ({
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
  const findingById = new Map(findings.map((f) => [f.id, f]));

  const alerts: EntityAlert[] = (fx.alerts as Raw[]).map((a) => {
    let title = a.title as string;
    if (a.ref.finding_id) {
      const f = findingById.get(a.ref.finding_id);
      const it = f && itemById.get(f.itemId);
      const h = f?.ruleHits[0];
      if (f && it && h) title = `${/^R\d/.test(h.ruleId) ? `${h.ruleId} ` : ''}${h.label} — ${it.author} (${PLATFORM_PL[it.platform] ?? it.platform})`;
    }
    return {
      id: a.id,
      createdAt: a.created_at,
      entityId: a.entity_id,
      kind: a.kind,
      severity: a.severity,
      title,
      ref: { findingId: a.ref.finding_id, changeId: a.ref.change_id, itemId: findingById.get(a.ref.finding_id)?.itemId ?? null },
      status: a.status,
      mock,
    };
  });

  // podmioty z danymi: grupy marek z app/backend (wpisy rejestru dopasowane po nazwie)
  const grouped = new Set<string>();
  const withData: KnfEntityDetail[] = (fx.entities as Raw[]).map((e) => {
    const reg = (e.registry_entries as Raw[]).map((r) => byName.get(r.name)).filter((r): r is RegistryEntry => !!r);
    reg.forEach((r) => grouped.add(r.name));
    const primary = reg.find((r) => r.country === 'Polska') ?? reg[0];
    const modules = Object.fromEntries(
      (['M1', 'M2', 'M3'] as EntityModule[]).map((m) => [m, { findings: e.modules[m].findings, avgScore: e.modules[m].avg_score }]),
    ) as KnfEntityDetail['modules'];
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
        findingsOpen: e.kpis.findings_open,
        alertsNew: e.kpis.alerts_new,
        riskScore: e.kpis.risk_score,
        pagesChanged7d: e.kpis.pages_changed_7d,
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
    generatedAt: fx.generated_at as string,
    sources: { fixtures, registry: source, registryEntries: entries.length },
    entities: [...withData, ...rest],
    items,
    findings,
    pages,
    snapshots,
    changes,
    alerts,
    findingsByDay: ov.findings_by_day,
    itemsByPlatform: ov.items_by_platform,
  };
  return snapshot;
}
