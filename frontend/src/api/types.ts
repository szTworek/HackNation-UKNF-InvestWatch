// Kontrakt danych InvestWatch (docs/frontend-agent.md, sekcja 3).
// Plik importuje też api/ – tylko typy, bez kodu wykonywalnego.

export type Platform = 'facebook' | 'instagram' | 'tiktok' | 'youtube' | 'x' | 'web' | 'other';
export type ContentKind = 'post' | 'transcript' | 'comment' | 'page';
export type ModuleId = 1 | 2 | 3;
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type Status = 'NEW' | 'IN_REVIEW' | 'CONFIRMED' | 'DISMISSED' | 'ESCALATED';

export type TopicLabel = 'NON_FINANCIAL' | 'FINANCIAL_OTHER' | 'INVESTMENT';
export type ContentType =
  | 'NEWS_EDU'
  | 'OPINION_DISCUSSION'
  | 'FIRM_OWN_MARKETING'
  | 'THIRD_PARTY_PROMO'
  | 'RECOMMENDATION'
  | 'SERVICE_OFFER';
export type Instrument =
  | 'CFD_FOREX'
  | 'STOCKS'
  | 'FUNDS_ETF'
  | 'BONDS'
  | 'CRYPTO'
  | 'OTHER_DERIVATIVES'
  | 'NON_INSTRUMENT';
export type FlagKey =
  // zgodność (moduł 2 / 1)
  | 'PROFIT_CLAIM'
  | 'RISK_WARNING'
  | 'AD_DISCLOSURE'
  | 'PAST_PERFORMANCE'
  | 'PAST_PERF_DISCLAIMER'
  | 'FORECAST'
  | 'FORECAST_DISCLAIMER'
  | 'TAX_CLAIM'
  | 'PRODUCT_COMPARISON'
  | 'SUPERVISOR_AS_SAFETY'
  // doradztwo (moduł 3)
  | 'PERSONALIZED_ADVICE'
  | 'PAID_ADVISORY_SERVICE'
  | 'SPECIFIC_INSTRUMENT_CALL'
  // oszustwo
  | 'GUARANTEED_PROFIT'
  | 'NO_RISK_CLAIM'
  | 'UNREALISTIC_RETURNS'
  | 'URGENCY_PRESSURE'
  | 'CELEBRITY_OR_BRAND_ENDORSEMENT'
  | 'AUTOMATED_PROFIT'
  | 'LOW_ENTRY_DEPOSIT'
  | 'OFF_PLATFORM_CONTACT'
  | 'SECRECY_CONSPIRACY'
  | 'FAKE_NEWS_FORMAT';

export type EvidenceSection = 'text' | 'transcript' | 'ocr';

export interface Evidence {
  section: EvidenceSection; // gdzie jest dowód: treść posta, transkrypcja, napis na grafice (OCR)
  start: number; // offsety w tekście danej sekcji
  end: number;
  text: string;
  t?: number; // sekunda nagrania (transkrypcja / OCR)
}

export interface FlagScore {
  p: number;
  evidence: Evidence[];
}

export type EntityRole = 'investment_firm' | 'advertiser' | 'advisor';
export type RegisterStatus = 'REGISTERED' | 'NOT_FOUND' | 'ON_WARNING_LIST';

export interface Entity {
  name: string;
  role: EntityRole;
  knfRegister: { status: RegisterStatus; matchedName?: string; score?: number };
}

export type RuleStatus = 'VIOLATION' | 'OK' | 'NOT_APPLICABLE' | 'NOT_CHECKED';

export interface RuleResult {
  // wynik reguły z 18 (oraz reguł modułu 1/3)
  ruleId: string; // '3', '12a', '15', 'M3_ADVISORY' ...
  status: RuleStatus; // NOT_CHECKED = brak danych (np. reguły 4,5,7,8 bez pomiaru wizualnego)
  score: number; // 0..1
  evidence: Evidence[];
}

export type IndicatorType =
  | 'domain'
  | 'url'
  | 'phone'
  | 'telegram'
  | 'whatsapp'
  | 'email'
  | 'wallet'
  | 'iban'
  | 'brand'
  | 'person'
  | 'author';

export interface Indicator {
  type: IndicatorType;
  value: string;
}

export type RelationReason = 'SHARES_INDICATOR' | 'SIMILAR_TEXT' | 'SAME_AUTHOR' | 'REDIRECTS_TO';

export interface RelatedFinding {
  findingId: string;
  reason: RelationReason;
  detail: string; // np. „wspólny numer +48 600 000 000”, „podobieństwo tekstu 0.94”
  score: number;
}

export type GraphNodeKind = 'finding' | IndicatorType;
export type GraphEdgeType = RelationReason | 'HAS_INDICATOR';

export interface GraphNode {
  id: string;
  kind: GraphNodeKind;
  label: string;
  riskScore?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: GraphEdgeType;
  weight: number;
}

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface HistoryEntry {
  at: string;
  status: Status;
  user: string;
  comment?: string;
}

export type AdDisclosure = 'DISCLOSED' | 'PLATFORM' | 'MISSING' | 'UNKNOWN';

export interface Finding {
  adDisclosure?: AdDisclosure; // oznaczenie reklamy wyliczone z reguły 2 i typu materiału
  id: string;
  url: string;
  platform: Platform;
  kind: ContentKind;
  author: { handle: string; displayName?: string; followers?: number };
  title?: string;
  text: string; // treść posta / transkrypcja
  publishedAt?: string; // ISO
  fetchedAt: string; // ISO
  modules: ModuleId[]; // do których modułów trafił
  topic: Record<TopicLabel, number>;
  contentType: Record<ContentType, number>;
  instruments: Record<Instrument, number>;
  flags: Record<FlagKey, FlagScore>;
  rules: RuleResult[];
  entities: Entity[];
  outboundLinks: string[]; // linki z posta
  transcript?: string; // gdy wideo
  indicators: Indicator[];
  related: RelatedFinding[]; // top 5 najsilniej powiązanych
  riskScore: number; // 0..1, liczony przez backend z progów
  riskLevel: RiskLevel;
  status: Status;
  history: HistoryEntry[];
  modelVersion: string;
  blockedUrls?: string[]; // adresy bez aktywnego linku: domeny z listy ostrzeżeń CERT Polska
  revisions?: Revision[]; // wcześniejsze wersje tego samego materiału (edycja po publikacji), od najnowszej
}

/** Wcześniejsza wersja treści wykryta przy ponownym skanie. added/removed: zdania względem tej wersji. */
export interface Revision {
  findingId?: string;
  fetchedAt: string;
  text: string;
  added: string[];
  removed: string[];
  riskLevel?: RiskLevel;
  modules?: ModuleId[];
}

export interface Thresholds {
  // klucze: 'flags.PROFIT_CLAIM', 'contentType.SERVICE_OFFER', 'risk.HIGH'
  version: string;
  updatedAt: string;
  values: Record<string, number>;
}

export interface EvalItem {
  // zbiór walidacyjny z ręcznymi etykietami (gold)
  id: string;
  probs: Record<string, number>; // te same klucze co Thresholds.values
  gold: Record<string, 0 | 1>;
}

// ---------------------------------------------------------------------------
// Odpowiedzi REST (założenia kontraktu – opisane w frontend/README.md)
// ---------------------------------------------------------------------------

export interface ApiHealth {
  status: string;
  findings: number;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

/**
 * Lekki wiersz listy (GET /findings). Pełny Finding pobiera się dopiero w szczegółach,
 * żeby lista nie ciągnęła tekstów, flag i reguł.
 */
export interface FindingSummary {
  id: string;
  url: string;
  platform: Platform;
  kind: ContentKind;
  author: { handle: string; displayName?: string };
  title?: string;
  snippet: string; // początek treści, ok. 200 znaków
  publishedAt?: string;
  fetchedAt: string;
  modules: ModuleId[];
  contentType: ContentType; // dominujący typ treści
  topFlags: { flag: FlagKey; p: number }[]; // flagi powyżej progu, max 3
  riskScore: number;
  riskLevel: RiskLevel;
  status: Status;
  // pola raportów modułów (żeby lista modułu nie potrzebowała pełnego rekordu)
  firm?: { name: string; register: RegisterStatus }; // M1, M2: firma inwestycyjna
  advertiser?: string; // M1: reklamujący (finfluencer, podmiot trzeci)
  adDisclosed: boolean; // M1: materiał oznaczony jako reklama
  adDisclosure: AdDisclosure;
  advisor?: { name: string; register: RegisterStatus }; // M3: podmiot oferujący doradztwo
  instruments: Instrument[]; // instrumenty z p >= 0,5
  violations: string[]; // M2: id naruszonych reguł
  brand?: string; // marka wskazana w treści
  domains: string[]; // domeny z linków
  contacts: string[]; // telefon, Telegram, WhatsApp
}

export interface RuleDef {
  id: string;
  name: string;
  description: string;
  legalBasis: string;
  detectableByText: boolean;
  module: ModuleId | null; // null = reguły z 18 (moduł 2, częściowo moduł 1)
}

export interface StatsOverview {
  total: number;
  newToday: number;
  highCritical: number;
  byModule: Record<'1' | '2' | '3', number>;
  byRiskLevel: Record<RiskLevel, number>;
  byPlatform: Record<Platform, number>;
  byStatus: Record<Status, number>;
  byContentType: Record<ContentType, number>;
  confirmed: number;
  verified: number; // CONFIRMED + DISMISSED + ESCALATED
}

export type TimeseriesGroupBy = 'module' | 'platform' | 'riskLevel';

export interface Timeseries {
  bucket: 'day';
  groupBy: TimeseriesGroupBy;
  keys: string[]; // module: '1' | '2' | '3'
  points: { date: string; counts: Record<string, number> }[];
}

export interface IndicatorFindings {
  indicator: Indicator;
  findings: FindingSummary[];
}

/** Wpis dziennika zmian statusów (strona „Historia”, GET /history). */
export interface HistoryRow extends HistoryEntry {
  findingId: string;
  platform: Platform;
  author: string;
  snippet: string;
  riskLevel: RiskLevel;
}

export interface StatusUpdate {
  status: Status;
  comment?: string;
}

export interface BulkStatusUpdate extends StatusUpdate {
  ids: string[];
}

export interface ThresholdsPreview {
  current: Record<RiskLevel, number>;
  proposed: Record<RiskLevel, number>;
}

export interface FindingsQuery {
  from?: string;
  to?: string;
  platform?: Platform[];
  module?: ModuleId[];
  riskLevel?: RiskLevel[];
  status?: Status[];
  flag?: FlagKey[];
  q?: string;
  sort?: string; // 'fetchedAt:desc' | 'riskScore:desc' | 'publishedAt:asc' ...
  page?: number;
  pageSize?: number;
}

// Zdarzenia socket.io
export interface ServerToClientEvents {
  'finding:updated': (f: Finding) => void;
  'thresholds:updated': (t: Thresholds) => void;
}

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
export interface ClientToServerEvents {}
