// Wzbogacenia rekordu: strony docelowe (landing) i wideo (klatki + OCR, analiza głosu).
// Zrzuty i klatki to proste SVG generowane przez mock (bez zewnętrznych obrazków).

import type { Evidence, FlagKey, LandingDomainFlag, LandingPageView, MediaView } from '../src/api/types';
import type { Draft } from './content';
import type { Rng } from './rng';

export type EvidenceSink = (flag: FlagKey, ev: Evidence) => void;

interface Seg {
  text: string;
  flags?: FlagKey[];
}

const SHORTENERS = new Set(['skroc.to']);
const hostOf = (u: string) => {
  try {
    return new URL(u).hostname.replace(/^www\./, '');
  } catch {
    return u;
  }
};

function join(segs: Seg[], sep: string, sink: EvidenceSink, extra: Partial<Evidence>, section: Evidence['section']): string {
  let text = '';
  for (const s of segs) {
    if (text) text += sep;
    const start = text.length;
    text += s.text;
    for (const f of s.flags ?? []) sink(f, { section, start, end: start + s.text.length, text: s.text, ...extra });
  }
  return text;
}

// ---------------------------------------------------------------------------
// Strona docelowa
// ---------------------------------------------------------------------------

function landingSegments(rng: Rng, d: Draft): { title: string; segs: Seg[]; form: boolean } {
  const brand = d.extraIndicators.find((i) => i.type === 'brand')?.value;
  const phone = d.extraIndicators.find((i) => i.type === 'phone')?.value;
  const firm = d.entities.find((e) => e.role === 'investment_firm')?.name;
  if (d.category === 'SCAM') {
    return {
      title: brand ? `${brand} – oficjalna platforma inwestycyjna` : 'Platforma inwestycyjna nowej generacji',
      form: true,
      segs: [
        { text: brand ? `${brand} – oficjalny program inwestycyjny dla Polaków` : 'Dołącz do tysięcy Polaków, którzy już zarabiają', flags: ['CELEBRITY_OR_BRAND_ENDORSEMENT'] },
        { text: rng.pick(['Zarabiaj do 2 400 zł dziennie', 'Średni zysk użytkowników: 30% miesięcznie']), flags: ['UNREALISTIC_RETURNS', 'PROFIT_CLAIM'] },
        { text: 'Bez ryzyka – gwarancja zwrotu wpłaty', flags: ['NO_RISK_CLAIM', 'GUARANTEED_PROFIT'] },
        { text: 'Algorytm AI inwestuje za Ciebie 24/7', flags: ['AUTOMATED_PROFIT'] },
        { text: `Zostaw numer telefonu, konsultant oddzwoni w 15 minut${phone ? ` (infolinia ${phone})` : ''}`, flags: ['OFF_PLATFORM_CONTACT'] },
        { text: `Pozostało ${rng.int(7, 19)} wolnych miejsc`, flags: ['URGENCY_PRESSURE'] },
      ],
    };
  }
  if (d.category === 'OFFER') {
    return {
      title: d.entities[0]?.name ?? 'Konsultacje inwestycyjne',
      form: true,
      segs: [
        { text: 'Umów konsultację portfelową', flags: ['PAID_ADVISORY_SERVICE'] },
        { text: 'Przygotujemy portfel akcji i obligacji pod Twoje cele i sytuację finansową', flags: ['PERSONALIZED_ADVICE'] },
        { text: 'Zostaw e-mail, odezwiemy się w ciągu doby' },
      ],
    };
  }
  const warn = rng.chance(0.6);
  const segs: Seg[] = [
    { text: firm ? `${firm} – otwórz rachunek w 10 minut` : 'Otwórz rachunek w 10 minut' },
    { text: rng.pick(['Inwestuj w akcje i ETF-y bez prowizji', 'Ponad 3000 instrumentów w jednej aplikacji']) },
  ];
  if (rng.chance(0.5)) segs.push({ text: 'Twoje pieniądze mogą pracować na 8% rocznie', flags: ['PROFIT_CLAIM'] });
  if (warn) segs.push({ text: 'Inwestowanie wiąże się z ryzykiem utraty kapitału. Zapoznaj się z dokumentem KID.', flags: ['RISK_WARNING'] });
  return { title: firm ?? 'Oferta', form: false, segs };
}

export function buildLanding(rng: Rng, d: Draft, findingId: string, sink: EvidenceSink): LandingPageView[] {
  const first = d.links[0];
  if (!first) return [];
  const final = d.links.find((l) => !SHORTENERS.has(hostOf(l))) ?? first;
  const chain = [first];
  if (first !== final) chain.push(`https://trk-${rng.int(10, 99)}.adclick.net/c?id=${rng.int(1e5, 9e5)}`, final);
  const { title, segs, form } = landingSegments(rng, d);
  const text = join(segs, '\n', sink, { landingIndex: 0 }, 'landing');
  const domainFlags: LandingDomainFlag[] = [];
  for (const s of d.signals) if (s === 'CERT_LIST_DOMAIN' || s === 'KNF_WARNING_LIST' || s === 'IMPERSONATION') domainFlags.push(s);
  if (d.category === 'SCAM') domainFlags.push('NEW_DOMAIN');
  return [
    {
      requestedUrl: first,
      finalUrl: final,
      redirectChain: chain,
      title,
      text,
      screenshotUrl: `/api/assets/landing/${findingId}/0/desktop.svg`,
      mobileScreenshotUrl: `/api/assets/landing/${findingId}/0/mobile.svg`,
      hasContactForm: form,
      domainFlags,
    },
  ];
}

// ---------------------------------------------------------------------------
// Wideo
// ---------------------------------------------------------------------------

export function buildMedia(rng: Rng, d: Draft, findingId: string, transcriptLength: number, sink: EvidenceSink): MediaView {
  const durationS = Math.max(20, Math.round(transcriptLength / 14));
  const phone = d.extraIndicators.find((i) => i.type === 'phone')?.value;
  const firm = d.entities.find((e) => e.role === 'investment_firm')?.name;
  const scam = d.category === 'SCAM';
  const texts: Seg[] = scam
    ? [
        { text: 'WYWIAD NA ŻYWO', flags: ['FAKE_NEWS_FORMAT'] },
        { text: 'ZYSK DO 30% MIESIĘCZNIE', flags: ['UNREALISTIC_RETURNS'] },
        { text: phone ? `ZADZWOŃ ${phone}` : 'ZOSTAW NUMER – ODDZWONIMY', flags: ['OFF_PLATFORM_CONTACT'] },
        { text: 'TYLKO DZIŚ', flags: ['URGENCY_PRESSURE'] },
      ]
    : [
        { text: '#REKLAMA', flags: d.category === 'PROMO' || d.category === 'FIRM' ? ['AD_DISCLOSURE'] : [] },
        { text: firm ?? 'Mój portfel' },
        { text: 'Inwestowanie wiąże się z ryzykiem', flags: ['RISK_WARNING'] },
      ];
  const keyframes = texts.map((s, i) => {
    const t = Math.round(((i + 0.5) * durationS) / texts.length);
    for (const f of s.flags ?? []) sink(f, { section: 'ocr', start: 0, end: s.text.length, text: s.text, t });
    return { t, imageUrl: `/api/assets/frame/${findingId}/${i}.svg`, ocrText: s.text };
  });
  const hasPerson = d.extraIndicators.some((i) => i.type === 'person');
  const media: MediaView = { durationS, asrUsed: rng.chance(0.5), keyframes };
  if (scam || rng.chance(0.3)) {
    const base = scam && hasPerson ? rng.range(0.6, 0.85) : rng.range(0.05, 0.25);
    const segments = [];
    for (let s = 0; s < durationS; s += 6) {
      segments.push({ startS: s, endS: Math.min(durationS, s + 6), score: Math.round(Math.min(0.99, Math.max(0.01, base + rng.range(-0.2, 0.15))) * 100) / 100 });
    }
    media.syntheticVoice = { score: Math.round(base * 100) / 100, segments, experimental: true };
  }
  return media;
}

// ---------------------------------------------------------------------------
// SVG
// ---------------------------------------------------------------------------

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

function wrap(text: string, max: number): string[] {
  const lines: string[] = [];
  let cur = '';
  for (const w of text.split(/\s+/)) {
    if ((cur + ' ' + w).trim().length > max) {
      if (cur) lines.push(cur);
      cur = w;
    } else cur = (cur + ' ' + w).trim();
  }
  if (cur) lines.push(cur);
  return lines;
}

export function landingSvg(page: LandingPageView, variant: 'desktop' | 'mobile'): string {
  const mobile = variant === 'mobile';
  const W = mobile ? 360 : 1024;
  const H = mobile ? 720 : 640;
  const pad = mobile ? 16 : 48;
  const lines = page.text.split('\n');
  let y = mobile ? 120 : 150;
  const parts: string[] = [];
  parts.push(`<rect width="${W}" height="${H}" fill="#ffffff"/>`);
  parts.push(`<rect width="${W}" height="40" fill="#e9ecef"/><rect x="${pad}" y="9" width="${W - 2 * pad}" height="22" rx="11" fill="#fff"/>`);
  parts.push(`<text x="${pad + 12}" y="25" font-size="12" fill="#495057" font-family="Arial">${esc(hostOf(page.finalUrl))}</text>`);
  for (const l of wrap(page.title ?? '', mobile ? 26 : 60)) {
    parts.push(`<text x="${pad}" y="${y - 40}" font-size="${mobile ? 20 : 30}" font-weight="bold" fill="#212529" font-family="Arial">${esc(l)}</text>`);
    y += mobile ? 24 : 36;
  }
  for (const line of lines) {
    for (const l of wrap(line, mobile ? 38 : 90)) {
      parts.push(`<text x="${pad}" y="${y}" font-size="${mobile ? 13 : 16}" fill="#343a40" font-family="Arial">${esc(l)}</text>`);
      y += mobile ? 18 : 24;
    }
    y += 8;
  }
  if (page.hasContactForm) {
    const fw = mobile ? W - 2 * pad : 360;
    const fx = mobile ? pad : W - pad - fw;
    const fy = mobile ? y + 10 : 120;
    parts.push(`<rect x="${fx}" y="${fy}" width="${fw}" height="200" rx="6" fill="#fff4e6" stroke="#fd7e14"/>`);
    ['Imię i nazwisko', 'Numer telefonu'].forEach((label, i) => {
      parts.push(`<text x="${fx + 16}" y="${fy + 30 + i * 56}" font-size="12" fill="#495057" font-family="Arial">${label}</text>`);
      parts.push(`<rect x="${fx + 16}" y="${fy + 38 + i * 56}" width="${fw - 32}" height="28" rx="4" fill="#fff" stroke="#ced4da"/>`);
    });
    parts.push(`<rect x="${fx + 16}" y="${fy + 152}" width="${fw - 32}" height="34" rx="4" fill="#e8590c"/>`);
    parts.push(`<text x="${fx + fw / 2}" y="${fy + 174}" font-size="14" fill="#fff" text-anchor="middle" font-family="Arial" font-weight="bold">Oddzwońcie do mnie</text>`);
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${parts.join('')}</svg>`;
}

export function frameSvg(ocrText: string, t: number): string {
  const W = 320;
  const H = 568;
  const mm = String(Math.floor(t / 60)).padStart(2, '0');
  const ss = String(t % 60).padStart(2, '0');
  const lines = wrap(ocrText, 18);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
<rect width="${W}" height="${H}" fill="#343a40"/>
<circle cx="160" cy="210" r="70" fill="#868e96"/><rect x="70" y="290" width="180" height="200" rx="90" fill="#868e96"/>
<rect x="16" y="${380 - lines.length * 16}" width="288" height="${lines.length * 32 + 16}" rx="6" fill="#ffd43b"/>
${lines.map((l, i) => `<text x="160" y="${405 - lines.length * 16 + i * 32}" font-size="22" font-weight="bold" fill="#212529" text-anchor="middle" font-family="Arial">${esc(l)}</text>`).join('')}
<text x="300" y="550" font-size="14" fill="#f8f9fa" text-anchor="end" font-family="Arial">${mm}:${ss}</text>
</svg>`;
}
