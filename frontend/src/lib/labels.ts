import type {
  ContentKind,
  ContentType,
  EntityRole,
  FlagKey,
  GraphEdgeType,
  IndicatorType,
  Instrument,
  ModuleId,
  Platform,
  RegisterStatus,
  RiskLevel,
  RuleStatus,
  AdDisclosure,
  Status,
  TopicLabel,
} from '../api/types';
import type { Channel, EntityModule, KnfCategory, Severity, SourcePlatform } from '../api/entityTypes';

export const PLATFORMS: Platform[] = ['facebook', 'instagram', 'tiktok', 'youtube', 'x', 'web', 'other'];
export const MODULES: ModuleId[] = [1, 2, 3];
export const RISK_LEVELS: RiskLevel[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
export const STATUSES: Status[] = ['NEW', 'IN_REVIEW', 'CONFIRMED', 'DISMISSED', 'ESCALATED'];
export const CONTENT_TYPES: ContentType[] = [
  'NEWS_EDU',
  'OPINION_DISCUSSION',
  'FIRM_OWN_MARKETING',
  'THIRD_PARTY_PROMO',
  'RECOMMENDATION',
  'SERVICE_OFFER',
];
export const TOPICS: TopicLabel[] = ['NON_FINANCIAL', 'FINANCIAL_OTHER', 'INVESTMENT'];
export const INSTRUMENTS: Instrument[] = [
  'CFD_FOREX',
  'STOCKS',
  'FUNDS_ETF',
  'BONDS',
  'CRYPTO',
  'OTHER_DERIVATIVES',
  'NON_INSTRUMENT',
];

export const COMPLIANCE_FLAGS: FlagKey[] = [
  'PROFIT_CLAIM',
  'RISK_WARNING',
  'AD_DISCLOSURE',
  'PAST_PERFORMANCE',
  'PAST_PERF_DISCLAIMER',
  'FORECAST',
  'FORECAST_DISCLAIMER',
  'TAX_CLAIM',
  'PRODUCT_COMPARISON',
  'SUPERVISOR_AS_SAFETY',
];
export const ADVISORY_FLAGS: FlagKey[] = ['PERSONALIZED_ADVICE', 'PAID_ADVISORY_SERVICE', 'SPECIFIC_INSTRUMENT_CALL'];
export const SCAM_FLAGS: FlagKey[] = [
  'GUARANTEED_PROFIT',
  'NO_RISK_CLAIM',
  'UNREALISTIC_RETURNS',
  'URGENCY_PRESSURE',
  'CELEBRITY_OR_BRAND_ENDORSEMENT',
  'AUTOMATED_PROFIT',
  'LOW_ENTRY_DEPOSIT',
  'OFF_PLATFORM_CONTACT',
  'SECRECY_CONSPIRACY',
  'FAKE_NEWS_FORMAT',
];
export const ALL_FLAGS: FlagKey[] = [...COMPLIANCE_FLAGS, ...ADVISORY_FLAGS, ...SCAM_FLAGS];

/** Flagi, których obecność jest pożądana (ostrzeżenia, oznaczenia). Nie są „czerwonymi flagami”. */
export const POSITIVE_FLAGS: ReadonlySet<FlagKey> = new Set<FlagKey>([
  'RISK_WARNING',
  'AD_DISCLOSURE',
  'PAST_PERF_DISCLAIMER',
  'FORECAST_DISCLAIMER',
]);

export const PLATFORM_LABEL: Record<Platform, string> = {
  facebook: 'Facebook',
  instagram: 'Instagram',
  tiktok: 'TikTok',
  youtube: 'YouTube',
  x: 'X',
  web: 'Strona WWW',
  other: 'Inne',
};

export const KIND_LABEL: Record<ContentKind, string> = {
  post: 'Post',
  transcript: 'Transkrypcja',
  comment: 'Komentarz',
  page: 'Strona',
};

export const MODULE_SHORT: Record<ModuleId, string> = { 1: 'Finfluencerzy', 2: 'Informacja o ryzyku', 3: 'Shadow advisory' };
export const MODULE_LABEL: Record<ModuleId, string> = {
  1: 'Finfluencerzy',
  2: 'Informacja o ryzyku',
  3: 'Shadow advisory',
};

export const RISK_LABEL: Record<RiskLevel, string> = {
  LOW: 'Niski',
  MEDIUM: 'Średni',
  HIGH: 'Wysoki',
  CRITICAL: 'Krytyczny',
};
export const RISK_COLOR: Record<RiskLevel, string> = {
  LOW: 'gray',
  MEDIUM: 'yellow',
  HIGH: 'orange',
  CRITICAL: 'red',
};

export const STATUS_LABEL: Record<Status, string> = {
  NEW: 'Nowy',
  IN_REVIEW: 'W analizie',
  CONFIRMED: 'Potwierdzony',
  DISMISSED: 'Odrzucony',
  ESCALATED: 'Eskalowany',
};
export const STATUS_COLOR: Record<Status, string> = {
  NEW: 'blue',
  IN_REVIEW: 'violet',
  CONFIRMED: 'red',
  DISMISSED: 'gray',
  ESCALATED: 'orange',
};

export const TOPIC_LABEL: Record<TopicLabel, string> = {
  NON_FINANCIAL: 'Niefinansowy',
  FINANCIAL_OTHER: 'Finanse – inne',
  INVESTMENT: 'Inwestycje',
};

export const CONTENT_TYPE_LABEL: Record<ContentType, string> = {
  NEWS_EDU: 'Informacja / edukacja',
  OPINION_DISCUSSION: 'Opinia / dyskusja',
  FIRM_OWN_MARKETING: 'Marketing firmy',
  THIRD_PARTY_PROMO: 'Promocja przez osobę trzecią',
  RECOMMENDATION: 'Rekomendacja',
  SERVICE_OFFER: 'Oferta usług',
};

export const INSTRUMENT_LABEL: Record<Instrument, string> = {
  CFD_FOREX: 'CFD / forex',
  STOCKS: 'Akcje',
  FUNDS_ETF: 'Fundusze / ETF',
  BONDS: 'Obligacje',
  CRYPTO: 'Kryptoaktywa',
  OTHER_DERIVATIVES: 'Inne derywaty',
  NON_INSTRUMENT: 'Poza instrumentami finansowymi',
};

export const FLAG_LABEL: Record<FlagKey, string> = {
  PROFIT_CLAIM: 'Obietnica zysku',
  RISK_WARNING: 'Ostrzeżenie o ryzyku',
  AD_DISCLOSURE: 'Oznaczenie reklamy',
  PAST_PERFORMANCE: 'Wyniki historyczne',
  PAST_PERF_DISCLAIMER: 'Zastrzeżenie do wyników historycznych',
  FORECAST: 'Prognoza wyników',
  FORECAST_DISCLAIMER: 'Zastrzeżenie do prognozy',
  TAX_CLAIM: 'Korzyść podatkowa',
  PRODUCT_COMPARISON: 'Porównanie produktów',
  SUPERVISOR_AS_SAFETY: 'Nadzór KNF jako gwarancja',
  PERSONALIZED_ADVICE: 'Porada spersonalizowana',
  PAID_ADVISORY_SERVICE: 'Płatna usługa doradcza',
  SPECIFIC_INSTRUMENT_CALL: 'Wezwanie do zakupu lub sprzedaży',
  GUARANTEED_PROFIT: 'Gwarantowany zysk',
  NO_RISK_CLAIM: 'Zapewnienie o braku ryzyka',
  UNREALISTIC_RETURNS: 'Nierealne stopy zwrotu',
  URGENCY_PRESSURE: 'Presja czasu',
  CELEBRITY_OR_BRAND_ENDORSEMENT: 'Wizerunek znanej osoby lub marki',
  AUTOMATED_PROFIT: 'Automatyczny zysk (bot, AI)',
  LOW_ENTRY_DEPOSIT: 'Niski próg wejścia',
  OFF_PLATFORM_CONTACT: 'Kontakt poza platformą',
  SECRECY_CONSPIRACY: 'Tajemnica, spisek',
  FAKE_NEWS_FORMAT: 'Format fałszywego artykułu',
};

/** Kolor podświetlenia (nazwa koloru Mantine) – każda flaga ma własny. */
export const FLAG_COLOR: Record<FlagKey, string> = {
  PROFIT_CLAIM: 'orange',
  RISK_WARNING: 'teal',
  AD_DISCLOSURE: 'cyan',
  PAST_PERFORMANCE: 'grape',
  PAST_PERF_DISCLAIMER: 'lime',
  FORECAST: 'violet',
  FORECAST_DISCLAIMER: 'green',
  TAX_CLAIM: 'indigo',
  PRODUCT_COMPARISON: 'blue',
  SUPERVISOR_AS_SAFETY: 'pink',
  PERSONALIZED_ADVICE: 'violet',
  PAID_ADVISORY_SERVICE: 'grape',
  SPECIFIC_INSTRUMENT_CALL: 'indigo',
  GUARANTEED_PROFIT: 'red',
  NO_RISK_CLAIM: 'pink',
  UNREALISTIC_RETURNS: 'orange',
  URGENCY_PRESSURE: 'yellow',
  CELEBRITY_OR_BRAND_ENDORSEMENT: 'grape',
  AUTOMATED_PROFIT: 'cyan',
  LOW_ENTRY_DEPOSIT: 'lime',
  OFF_PLATFORM_CONTACT: 'blue',
  SECRECY_CONSPIRACY: 'violet',
  FAKE_NEWS_FORMAT: 'indigo',
};

export const ENTITY_ROLE_LABEL: Record<EntityRole, string> = {
  investment_firm: 'Firma inwestycyjna',
  advertiser: 'Reklamujący',
  advisor: 'Podmiot doradczy',
};

export const REGISTER_LABEL: Record<RegisterStatus, string> = {
  REGISTERED: 'W rejestrze KNF',
  NOT_FOUND: 'Brak w rejestrze KNF',
  ON_WARNING_LIST: 'Lista ostrzeżeń KNF',
};
export const REGISTER_COLOR: Record<RegisterStatus, string> = {
  REGISTERED: 'green',
  NOT_FOUND: 'orange',
  ON_WARNING_LIST: 'red',
};

export const AD_DISCLOSURE_LABEL: Record<AdDisclosure, string> = {
  DISCLOSED: 'Oznaczona w treści',
  PLATFORM: 'Płatna reklama (oznacza platforma)',
  MISSING: 'Brak oznaczenia',
  UNKNOWN: 'Nie ustalono',
};
export const AD_DISCLOSURE_COLOR: Record<AdDisclosure, string> = {
  DISCLOSED: 'green',
  PLATFORM: 'blue',
  MISSING: 'red',
  UNKNOWN: 'gray',
};

export const RULE_STATUS_LABEL: Record<RuleStatus, string> = {
  VIOLATION: 'Do weryfikacji',
  OK: 'Spełniona',
  NOT_APPLICABLE: 'Nie dotyczy',
  NOT_CHECKED: 'Wymaga analizy wizualnej',
};
export const RULE_STATUS_COLOR: Record<RuleStatus, string> = {
  VIOLATION: 'red',
  OK: 'green',
  NOT_APPLICABLE: 'gray',
  NOT_CHECKED: 'blue',
};

export const INDICATOR_LABEL: Record<IndicatorType, string> = {
  domain: 'Domena',
  url: 'URL',
  phone: 'Telefon',
  telegram: 'Telegram',
  whatsapp: 'WhatsApp',
  email: 'E-mail',
  wallet: 'Portfel krypto',
  iban: 'IBAN',
  brand: 'Marka',
  person: 'Osoba publiczna',
  author: 'Autor',
};

export const EDGE_LABEL: Record<GraphEdgeType, string> = {
  SHARES_INDICATOR: 'Wspólny wskaźnik',
  SIMILAR_TEXT: 'Podobny tekst',
  SAME_AUTHOR: 'Ten sam autor',
  REDIRECTS_TO: 'Przekierowanie',
  HAS_INDICATOR: 'Zawiera wskaźnik',
};

// ---------------------------------------------------------------------------
// Progi kalibracji
// ---------------------------------------------------------------------------

export type ThresholdGroup = 'flags' | 'contentType' | 'risk';

export const THRESHOLD_GROUP_LABEL: Record<ThresholdGroup, string> = {
  risk: 'Poziomy ryzyka',
  flags: 'Flagi',
  contentType: 'Typ treści',
};

export const THRESHOLD_GROUP_ORDER: ThresholdGroup[] = ['risk', 'flags', 'contentType'];

export function thresholdGroup(key: string): ThresholdGroup | null {
  const prefix = key.split('.')[0];
  return prefix === 'flags' || prefix === 'contentType' || prefix === 'risk' ? prefix : null;
}

export function thresholdLabel(key: string): string {
  const [prefix, name] = key.split('.');
  if (prefix === 'flags' && name in FLAG_LABEL) return FLAG_LABEL[name as FlagKey];
  if (prefix === 'contentType' && name in CONTENT_TYPE_LABEL) return CONTENT_TYPE_LABEL[name as ContentType];
  if (prefix === 'risk' && name in RISK_LABEL) return `Poziom: ${RISK_LABEL[name as RiskLevel].toLowerCase()}`;
  return key;
}

/** Kolejność wyświetlania progów w grupie zgodna z listami powyżej. */
export function thresholdOrder(key: string): number {
  const [prefix, name] = key.split('.');
  if (prefix === 'flags') return ALL_FLAGS.indexOf(name as FlagKey);
  if (prefix === 'contentType') return CONTENT_TYPES.indexOf(name as ContentType);
  if (prefix === 'risk') return RISK_LEVELS.indexOf(name as RiskLevel);
  return 0;
}

// ---------------------------------------------------------------------------
// Oś podmiotu (rejestr KNF)
// ---------------------------------------------------------------------------

export const ENTITY_MODULES: EntityModule[] = ['M1', 'M2', 'M3'];

export const ENTITY_MODULE_LABEL: Record<EntityModule, string> = {
  M1: 'Finfluencerzy',
  M2: 'Informacja o ryzyku',
  M3: 'Shadow advisory',
};

export const ENTITY_MODULE_DESC: Record<EntityModule, string> = {
  M1: 'Podmiot reklamowany przez finfluencerów i osoby trzecie',
  M2: 'Materiały własne podmiotu wobec 18 reguł (art. 44 rozp. 2017/565)',
  M3: 'Rekomendacje autorów spoza rejestru KNF',
};

export const ENTITY_MODULE_SHORT: Record<EntityModule, string> = { M1: 'Finfluencerzy', M2: 'Informacja o ryzyku', M3: 'Shadow advisory' };

export const ENTITY_MODULE_COLOR: Record<EntityModule, string> = { M1: '#113b6f', M2: '#1e6ac8', M3: '#4b5f7c' };

export const KNF_CATEGORY_LABEL: Record<KnfCategory, string> = {
  domy_maklerskie: 'Dom maklerski',
  banki_maklerskie: 'Bank prowadzący działalność maklerską',
  zagraniczne_oddzialy: 'Oddział firmy zagranicznej',
  zagraniczne_bez_oddzialu: 'Firma zagraniczna bez oddziału',
};

export const SOURCE_PLATFORM_LABEL: Record<SourcePlatform, string> = {
  google_ads: 'Google Ads',
  meta_ads: 'Meta Ads',
  bing_ads: 'Bing Ads',
  youtube: 'YouTube',
  tiktok: 'TikTok',
  website: 'Strona WWW',
};

export const CHANNEL_LABEL: Record<Channel, string> = { ad: 'Reklama', social: 'Social media', website: 'Strona WWW' };

export const SEVERITY_LABEL: Record<Severity, string> = { low: 'Niska', medium: 'Średnia', high: 'Wysoka' };
export const SEVERITY_COLOR: Record<Severity, string> = { low: 'gray', medium: 'yellow', high: 'red' };

export const TEXT_SECTION_LABEL: Record<string, string> = {
  title: 'Tytuł',
  ad_body: 'Treść reklamy',
  link_description: 'Opis linku',
  cta: 'Wezwanie do działania',
  ocr: 'Tekst z obrazu (OCR)',
  post: 'Post',
  transcript: 'Transkrypcja',
  description: 'Opis',
  page: 'Tekst strony',
};

/** Reguły R01–R18 z numerem (art. 44), reguły finfluencerów i advisory samą nazwą. */
export const ruleText = (ruleId: string, label: string) => (/^R\d/.test(ruleId) ? `${ruleId} · ${label}` : label);

export const ruleModule = (ruleId: string): EntityModule => (ruleId.startsWith('M1') ? 'M1' : ruleId.startsWith('M3') ? 'M3' : 'M2');
