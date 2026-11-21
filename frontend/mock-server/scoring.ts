// Prosta funkcja scoringowa mocka: reguły, moduły i poziom ryzyka z prawdopodobieństw modelu i progów.
// Backend robi to przez ai-service `/rescore`; tu wystarczy deterministyczne przybliżenie.

import type {
  ContentType,
  Evidence,
  Finding,
  FlagKey,
  Instrument,
  ModuleId,
  RiskLevel,
  RuleResult,
} from '../src/api/types';
import { RULES, VISUAL_RULES } from './rules';

export const FLAG_KEYS: FlagKey[] = [
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
  'PERSONALIZED_ADVICE',
  'PAID_ADVISORY_SERVICE',
  'SPECIFIC_INSTRUMENT_CALL',
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

export const CONTENT_TYPE_KEYS: ContentType[] = [
  'NEWS_EDU',
  'OPINION_DISCUSSION',
  'FIRM_OWN_MARKETING',
  'THIRD_PARTY_PROMO',
  'RECOMMENDATION',
  'SERVICE_OFFER',
];

export const RISK_KEYS: Exclude<RiskLevel, 'LOW'>[] = ['MEDIUM', 'HIGH', 'CRITICAL'];

const FINANCIAL_INSTRUMENTS: Instrument[] = ['CFD_FOREX', 'STOCKS', 'FUNDS_ETF', 'BONDS', 'OTHER_DERIVATIVES'];

export function defaultThresholdValues(): Record<string, number> {
  const values: Record<string, number> = {};
  for (const f of FLAG_KEYS) values[`flags.${f}`] = 0.5;
  values['flags.RISK_WARNING'] = 0.45;
  values['flags.AD_DISCLOSURE'] = 0.45;
  values['flags.SPECIFIC_INSTRUMENT_CALL'] = 0.55;
  for (const c of CONTENT_TYPE_KEYS) values[`contentType.${c}`] = 0.4;
  values['risk.MEDIUM'] = 0.4;
  values['risk.HIGH'] = 0.65;
  values['risk.CRITICAL'] = 0.85;
  values['scam.p'] = 0.6;
  return values;
}

export const THRESHOLD_KEYS = Object.keys(defaultThresholdValues());

/** Waga flagi w riskScore. Flagi „pozytywne” (ostrzeżenia, oznaczenia) nie podnoszą ryzyka. */
const FLAG_WEIGHT: Partial<Record<FlagKey, number>> = {
  GUARANTEED_PROFIT: 0.9,
  NO_RISK_CLAIM: 0.85,
  UNREALISTIC_RETURNS: 0.85,
  SUPERVISOR_AS_SAFETY: 0.75,
  AUTOMATED_PROFIT: 0.7,
  CELEBRITY_OR_BRAND_ENDORSEMENT: 0.7,
  OFF_PLATFORM_CONTACT: 0.6,
  SECRECY_CONSPIRACY: 0.6,
  FAKE_NEWS_FORMAT: 0.6,
  PERSONALIZED_ADVICE: 0.6,
  PAID_ADVISORY_SERVICE: 0.55,
  URGENCY_PRESSURE: 0.5,
  LOW_ENTRY_DEPOSIT: 0.5,
  SPECIFIC_INSTRUMENT_CALL: 0.4,
  PROFIT_CLAIM: 0.35,
  PRODUCT_COMPARISON: 0.3,
  FORECAST: 0.3,
  PAST_PERFORMANCE: 0.3,
  TAX_CLAIM: 0.25,
};

const RULE_WEIGHT: Record<string, number> = {
  '1': 0.45,
  '2': 0.7,
  '3': 0.95,
  '6': 0.6,
  '9': 0.4,
  '10': 0.75,
  '11': 0.55,
  '12a': 0.45,
  '12b': 0.45,
  '13': 0.5,
  '14': 0.75,
  '15': 0.7,
  '16': 0.6,
  '17': 0.85,
  '18': 0.9,
  M1_PROMO: 0.8,
  M3_ADVISORY: 0.95,
};

type Scorable = Pick<Finding, 'text' | 'transcript' | 'landingPages' | 'flags' | 'contentType' | 'instruments' | 'entities' | 'scam'>;

/** Długość tekstu sekcji, do której odnosi się dowód. */
function sectionLength(f: Scorable, ev: Evidence): number {
  if (ev.section === 'transcript') return f.transcript?.length ?? 0;
  if (ev.section === 'landing') return f.landingPages[ev.landingIndex ?? 0]?.text.length ?? 0;
  if (ev.section === 'ocr') return ev.text.length;
  return f.text.length;
}

export interface Rescore {
  rules: RuleResult[];
  modules: ModuleId[];
  riskScore: number;
  riskLevel: RiskLevel;
}

const r3 = (x: number) => Math.round(x * 1000) / 1000;

export function rescore(f: Scorable, t: Record<string, number>): Rescore {
  const th = (key: string, fallback = 0.5) => t[key] ?? fallback;
  const p = (flag: FlagKey) => f.flags[flag]?.p ?? 0;
  const has = (flag: FlagKey) => p(flag) >= th(`flags.${flag}`);
  const ev = (...flags: FlagKey[]): Evidence[] => flags.flatMap((fl) => (has(fl) ? f.flags[fl].evidence : []));
  const ct = (c: ContentType) => f.contentType[c] >= th(`contentType.${c}`, 0.4);

  const isScam = f.scam.p >= th('scam.p', 0.6);
  const firmRegistered = f.entities.some(
    (e) => e.role === 'investment_firm' && e.knfRegister.status === 'REGISTERED',
  );
  const anyRegistered = f.entities.some(
    (e) => (e.role === 'investment_firm' || e.role === 'advisor') && e.knfRegister.status === 'REGISTERED',
  );
  const financialInstrument = FINANCIAL_INSTRUMENTS.some((i) => f.instruments[i] >= 0.5);

  const modules: ModuleId[] = [];
  if (!isScam && ct('THIRD_PARTY_PROMO') && firmRegistered) modules.push(1);
  if (!isScam && ct('FIRM_OWN_MARKETING') && firmRegistered) modules.push(2);
  const advisory = has('PERSONALIZED_ADVICE') || has('PAID_ADVISORY_SERVICE');
  if (!isScam && ct('SERVICE_OFFER') && advisory && financialInstrument && !anyRegistered) modules.push(3);

  const isAd = modules.includes(1) || modules.includes(2);
  const text = [f.text, f.transcript ?? '', ...f.landingPages.map((l) => l.text)].join('\n').toLowerCase();
  const rules: RuleResult[] = [];
  const push = (ruleId: string, status: RuleResult['status'], score = 0, evidence: Evidence[] = []) =>
    rules.push({ ruleId, status, score: r3(score), evidence });

  for (const def of RULES) {
    const id = def.id;
    if (def.module === null && !isAd) {
      push(id, 'NOT_APPLICABLE');
      continue;
    }
    if (VISUAL_RULES.has(id)) {
      // reguły wizualne da się sprawdzić tylko na zrzucie strony docelowej
      const landing = f.landingPages.find((l) => l.screenshotUrl);
      if (!landing) {
        push(id, 'NOT_CHECKED');
        continue;
      }
      const landingWarn = f.flags.RISK_WARNING.evidence.filter((e) => e.section === 'landing');
      if (id === '8') push(id, 'OK', 0.1);
      else if (landingWarn.length) push(id, 'OK', 0.1, landingWarn);
      else push(id, 'VIOLATION', id === '7' ? 0.7 : 0.5);
      continue;
    }
    switch (id) {
      case '1': {
        const named = f.entities.some((e) => e.role === 'investment_firm' && text.includes(e.name.toLowerCase()));
        push(id, named ? 'OK' : 'VIOLATION', named ? 0.1 : 0.6);
        break;
      }
      case '2': {
        const disclosed = has('AD_DISCLOSURE');
        push(id, disclosed ? 'OK' : 'VIOLATION', 1 - p('AD_DISCLOSURE'), disclosed ? ev('AD_DISCLOSURE') : []);
        break;
      }
      case '3': {
        if (!has('PROFIT_CLAIM')) {
          push(id, 'NOT_APPLICABLE');
          break;
        }
        const warned = has('RISK_WARNING');
        const score = p('PROFIT_CLAIM') * (1 - p('RISK_WARNING'));
        push(id, warned ? 'OK' : 'VIOLATION', score, ev('PROFIT_CLAIM', 'RISK_WARNING'));
        break;
      }
      case '6': {
        if (!has('RISK_WARNING')) {
          push(id, 'NOT_APPLICABLE');
          break;
        }
        const w = f.flags.RISK_WARNING.evidence[0];
        const len = w ? sectionLength(f, w) : 0;
        const hidden = w !== undefined && len > 200 && w.start > len * 0.75;
        push(id, hidden ? 'VIOLATION' : 'OK', hidden ? 0.6 : 0.1, ev('RISK_WARNING'));
        break;
      }
      case '9': {
        if (!has('RISK_WARNING')) push(id, 'NOT_APPLICABLE');
        else push(id, 'OK', 0.15, ev('RISK_WARNING'));
        break;
      }
      case '10': {
        if (!has('RISK_WARNING')) {
          push(id, 'NOT_APPLICABLE');
          break;
        }
        const english = f.flags.RISK_WARNING.evidence.some((e) => /\b(lose|money|risk|leverage)\b/i.test(e.text));
        push(id, english ? 'VIOLATION' : 'OK', english ? 0.85 : 0.05, ev('RISK_WARNING'));
        break;
      }
      case '11':
        if (!has('PRODUCT_COMPARISON')) push(id, 'NOT_APPLICABLE');
        else {
          const sourced = /źródło|zrodlo|według|wg /.test(text);
          push(id, sourced ? 'OK' : 'VIOLATION', p('PRODUCT_COMPARISON') * (sourced ? 0.2 : 0.8), ev('PRODUCT_COMPARISON'));
        }
        break;
      case '12a':
      case '12b':
      case '13':
      case '14': {
        if (!has('PAST_PERFORMANCE')) {
          push(id, 'NOT_APPLICABLE');
          break;
        }
        const pp = p('PAST_PERFORMANCE');
        const evidence = ev('PAST_PERFORMANCE');
        if (id === '12a') {
          const ok = /5 lat|pięciu lat|piec lat|pięć lat/.test(text);
          push(id, ok ? 'OK' : 'VIOLATION', ok ? 0.1 : pp * 0.7, evidence);
        } else if (id === '12b') {
          const ok = /walut|opłat|oplat|prowizj/.test(text);
          push(id, ok ? 'OK' : 'VIOLATION', ok ? 0.1 : pp * 0.65, evidence);
        } else if (id === '13') {
          const first = f.flags.PAST_PERFORMANCE.evidence[0];
          const dominant = first !== undefined && first.section === 'text' && first.start < f.text.length * 0.2;
          push(id, dominant ? 'VIOLATION' : 'OK', dominant ? pp * 0.7 : 0.1, evidence);
        } else {
          const ok = has('PAST_PERF_DISCLAIMER');
          push(id, ok ? 'OK' : 'VIOLATION', pp * (1 - p('PAST_PERF_DISCLAIMER')), ev('PAST_PERFORMANCE', 'PAST_PERF_DISCLAIMER'));
        }
        break;
      }
      case '15': {
        if (!has('FORECAST')) {
          push(id, 'NOT_APPLICABLE');
          break;
        }
        const ok = has('FORECAST_DISCLAIMER');
        push(id, ok ? 'OK' : 'VIOLATION', p('FORECAST') * (1 - p('FORECAST_DISCLAIMER')), ev('FORECAST', 'FORECAST_DISCLAIMER'));
        break;
      }
      case '16': {
        if (!has('TAX_CLAIM')) {
          push(id, 'NOT_APPLICABLE');
          break;
        }
        const ok = /indywidualnej sytuacji|może ulec zmian|moze ulec zmian/.test(text);
        push(id, ok ? 'OK' : 'VIOLATION', ok ? 0.1 : p('TAX_CLAIM') * 0.8, ev('TAX_CLAIM'));
        break;
      }
      case '17':
      case '18': {
        if (!/knf|nadzor|komisj/.test(text)) {
          push(id, 'NOT_APPLICABLE');
          break;
        }
        const s = p('SUPERVISOR_AS_SAFETY');
        const violated =
          has('SUPERVISOR_AS_SAFETY') && (id === '17' ? /zatwierdz|aprob|licencj|rekomend/.test(text) : /bezpieczn|gwaranc|pewn/.test(text));
        push(id, violated ? 'VIOLATION' : 'OK', violated ? s : s * 0.2, ev('SUPERVISOR_AS_SAFETY'));
        break;
      }
      case 'M1_PROMO': {
        if (!modules.includes(1)) {
          push(id, 'NOT_APPLICABLE');
          break;
        }
        const hiddenAd = has('AD_DISCLOSURE') ? 0 : 1 - p('AD_DISCLOSURE');
        const noRisk = has('PROFIT_CLAIM') && !has('RISK_WARNING') ? p('PROFIT_CLAIM') * (1 - p('RISK_WARNING')) : 0;
        const score = Math.max(hiddenAd, noRisk);
        push(id, score > 0 ? 'VIOLATION' : 'OK', score, ev('PROFIT_CLAIM', 'AD_DISCLOSURE'));
        break;
      }
      case 'M3_ADVISORY': {
        if (modules.includes(3)) {
          push(id, 'VIOLATION', Math.max(p('PERSONALIZED_ADVICE'), p('PAID_ADVISORY_SERVICE')), ev('PERSONALIZED_ADVICE', 'PAID_ADVISORY_SERVICE', 'SPECIFIC_INSTRUMENT_CALL'));
        } else if (ct('SERVICE_OFFER') && advisory) {
          push(id, 'OK', 0.1, ev('PERSONALIZED_ADVICE', 'PAID_ADVISORY_SERVICE'));
        } else {
          push(id, 'NOT_APPLICABLE');
        }
        break;
      }
      default:
        push(id, 'NOT_APPLICABLE');
    }
  }

  let riskScore = isScam ? f.scam.p : f.scam.p * 0.5;
  for (const r of rules) {
    if (r.status === 'VIOLATION') riskScore = Math.max(riskScore, r.score * (RULE_WEIGHT[r.ruleId] ?? 0.5));
  }
  for (const [flag, w] of Object.entries(FLAG_WEIGHT) as [FlagKey, number][]) {
    if (has(flag)) riskScore = Math.max(riskScore, p(flag) * w);
  }
  riskScore = r3(Math.min(1, riskScore));

  let riskLevel: RiskLevel = 'LOW';
  if (riskScore >= th('risk.MEDIUM', 0.4)) riskLevel = 'MEDIUM';
  if (riskScore >= th('risk.HIGH', 0.65)) riskLevel = 'HIGH';
  if (riskScore >= th('risk.CRITICAL', 0.85) || isScam) riskLevel = 'CRITICAL';

  return { rules, modules, riskScore, riskLevel };
}
