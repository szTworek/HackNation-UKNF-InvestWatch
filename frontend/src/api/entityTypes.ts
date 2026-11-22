// Oś podmiotu (rejestr KNF): kontrakt endpointów /api/entities*, /api/items, /api/changes, /api/entity-stats.
// Kształt z contracts/app_api.md, klucze w camelCase.

export type EntityModule = 'M1' | 'M2' | 'M3';
export type Severity = 'low' | 'medium' | 'high';
export type Channel = 'ad' | 'social' | 'website';
export type SourcePlatform = 'google_ads' | 'meta_ads' | 'bing_ads' | 'youtube' | 'tiktok' | 'website';
export type KnfCategory = 'domy_maklerskie' | 'banki_maklerskie' | 'zagraniczne_oddzialy' | 'zagraniczne_bez_oddzialu';

export interface RegistryEntry {
  name: string;
  aliases: string[];
  category: KnfCategory;
  country: string;
  supervisor: string | null;
  registeredAt: string | null;
  address: string | null;
  sourceUrl: string | null;
}

export interface EntityKpis {
  items: number;
  findingsOpen: number;
  alertsNew: number;
  riskScore: number;
  pagesChanged7d: number;
}

/** Podmiot: grupa wpisów rejestru KNF pod jedną marką albo pojedynczy wpis. */
export interface KnfEntity {
  id: string;
  name: string;
  category: KnfCategory;
  country: string;
  registryEntries: RegistryEntry[];
  domains: string[];
  hasData: boolean;
  monitoredPages: number;
  socialHandles: Record<string, string>;
  kpis: EntityKpis | null;
}

export interface KnfEntityDetail extends KnfEntity {
  modules: Record<EntityModule, { findings: number; avgScore: number }>;
  platforms: Partial<Record<SourcePlatform, number>>;
}

export interface RuleHit {
  ruleId: string;
  label: string;
  evidence: string;
  section: string;
  span: [number, number] | null;
}

export interface EntityFinding {
  id: string;
  itemId: string;
  entityId: string;
  module: EntityModule;
  score: number;
  severity: Severity;
  ruleHits: RuleHit[];
  model: string;
  createdAt: string;
  mock: boolean;
}

export interface EntityItem {
  id: string;
  entityIds: string[];
  channel: Channel;
  platform: SourcePlatform;
  sourceUrl: string;
  author: string;
  authorIsEntity: boolean;
  publishedAt: string | null;
  fetchedAt: string;
  text: Record<string, string>;
  mock: boolean;
}

export interface EntityItemWithFindings extends EntityItem {
  findings: EntityFinding[];
}

export interface ItemsPage {
  total: number;
  items: EntityItemWithFindings[];
}

export interface RiskWarning {
  present: boolean;
  cfdLossPct: number | null;
  text: string | null;
  aboveFold: boolean;
}

export interface PageSnapshot {
  id: string;
  pageId: string;
  entityId: string;
  url: string;
  fetchedAt: string;
  textSha256: string;
  text: string;
  riskWarning: RiskWarning;
  mock: boolean;
}

export type ChangeKind = 'text' | 'risk_warning_changed' | 'risk_warning_removed' | 'page_removed';

export interface PageChange {
  id: string;
  pageId: string;
  entityId: string;
  fromSnapshot: string;
  toSnapshot: string;
  detectedAt: string;
  kinds: ChangeKind[];
  summary: string;
  addedLines: string[];
  removedLines: string[];
  mock: boolean;
}

export interface PageChangeDetail extends PageChange {
  from: PageSnapshot;
  to: PageSnapshot;
}

export interface MonitoredPage {
  pageId: string;
  url: string;
  label: string;
  lastSnapshot: PageSnapshot | null;
  changes: PageChange[];
}

export interface EntityAlert {
  id: string;
  createdAt: string;
  entityId: string;
  kind: 'finding' | 'page_change';
  severity: Severity;
  title: string;
  ref: { findingId: string | null; changeId: string | null; itemId: string | null };
  status: 'new' | 'ack' | 'closed';
  mock: boolean;
}

export interface RecentChange extends PageChange {
  pageLabel: string;
  url: string;
  entityName: string;
}

export interface EntityOverview {
  generatedAt: string;
  totals: {
    knfEntries: number;
    entities: number;
    entitiesWithData: number;
    items: number;
    findings: number;
    alertsNew: number;
    pages: number;
    pageChanges30d: number;
  };
  findingsByDay: ({ date: string } & Record<EntityModule, number>)[];
  itemsByPlatform: Partial<Record<SourcePlatform, number>>;
  heatmap: ({ entityId: string; name: string } & Record<EntityModule, number>)[];
  topRules: { ruleId: string; label: string; count: number }[];
  recentChanges: RecentChange[];
  recentAlerts: EntityAlert[];
}
