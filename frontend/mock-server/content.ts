// Bank treści do seeda. Wszystkie firmy, osoby, domeny i numery są fikcyjne.

import type {
  CampaignStatus,
  ContentKind,
  ContentType,
  Entity,
  FlagKey,
  Indicator,
  Instrument,
  Platform,
  ScamSignal,
  TopicLabel,
} from '../src/api/types';
import type { Rng } from './rng';

export interface Seg {
  text: string;
  flags?: FlagKey[];
  weak?: FlagKey[];
}

const s = (text: string, ...flags: FlagKey[]): Seg => ({ text, flags });
const w = (text: string, ...weak: FlagKey[]): Seg => ({ text, weak });

export type Category =
  | 'NON_FIN'
  | 'FIN_OTHER'
  | 'EDU'
  | 'SCAM_AWARE'
  | 'OPINION'
  | 'FIRM'
  | 'PROMO'
  | 'RECO'
  | 'OFFER'
  | 'SCAM';

export interface Draft {
  category: Category;
  platform: Platform;
  kind: ContentKind;
  sep: string;
  segs: Seg[];
  title?: string;
  author: { handle: string; displayName?: string; followers?: number };
  links: string[];
  entities: Entity[];
  extraIndicators: Indicator[];
  topic: TopicLabel;
  contentType: ContentType;
  instruments: Instrument[];
  scam: [number, number];
  signals: ScamSignal[];
  campaignId?: string;
}

export interface Firm {
  name: string;
  short: string;
  domain: string;
  kind: 'broker' | 'fund' | 'cfd' | 'bank';
}

export const FIRMS: Firm[] = [
  { name: 'Alfa Invest Dom Maklerski S.A.', short: 'Alfa Invest', domain: 'alfainvest.pl', kind: 'broker' },
  { name: 'Beta Capital TFI S.A.', short: 'Beta Capital', domain: 'betacapital.pl', kind: 'fund' },
  { name: 'Gamma Brokers S.A.', short: 'Gamma Brokers', domain: 'gammabrokers.pl', kind: 'broker' },
  { name: 'Delta Markets Ltd', short: 'Delta Markets', domain: 'deltamarkets.com.pl', kind: 'cfd' },
  { name: 'Omega Trade Europe Ltd', short: 'Omega Trade', domain: 'omegatrade.eu', kind: 'cfd' },
  { name: 'Bank Nadwiślański S.A.', short: 'Bank Nadwiślański', domain: 'nadwislanski.pl', kind: 'bank' },
];

export interface Advisor {
  name: string;
  handle: string;
  domain: string;
  registered?: boolean;
  nonInstrument?: boolean;
}

export const ADVISORS: Advisor[] = [
  { name: 'Kowalczyk Wealth Partners', handle: '@kowalczyk.wealth', domain: 'kowalczyk-wealth.pl' },
  { name: 'Family Office Srebrny Las', handle: '@srebrnylas.fo', domain: 'srebrnylas-fo.pl' },
  { name: 'Nowacki i Wspólnicy Investment Consulting', handle: '@nowacki.consulting', domain: 'nowacki-consulting.pl' },
  { name: 'Prestige Portfolio Advisors', handle: '@prestige.portfolio', domain: 'prestigeportfolio.pl' },
  { name: 'Mentor Finansowy Sp. z o.o.', handle: '@mentor_finansowy', domain: 'mentorfinansowy.pl' },
  { name: 'Złota Przystań doradztwo majątkowe', handle: '@zlota.przystan', domain: 'zlotaprzystan.pl', nonInstrument: true },
  { name: 'Gamma Brokers S.A.', handle: '@gammabrokers', domain: 'gammabrokers.pl', registered: true },
];

export const FINFLUENCERS = [
  { handle: '@krypto_marek', displayName: 'Marek | Krypto i giełda', followers: 48200 },
  { handle: '@gielda_z_ola', displayName: 'Ola o giełdzie', followers: 112000 },
  { handle: '@inwestor_kuba', displayName: 'Kuba Inwestuje', followers: 23400 },
  { handle: '@pasywny_dochod_pl', displayName: 'Pasywny Dochód PL', followers: 76500 },
  { handle: '@trader_tomek', displayName: 'Tomek Trader', followers: 158000 },
  { handle: '@finanse_bez_nudy', displayName: 'Finanse bez nudy', followers: 34100 },
  { handle: '@mama_inwestuje', displayName: 'Mama inwestuje', followers: 19800 },
  { handle: '@etf_janek', displayName: 'Janek o ETF-ach', followers: 61300 },
];

const USERS = [
  '@ania_gotuje',
  '@podroze_z_pawlem',
  '@biegacz_wawa',
  '@kot_filemon',
  '@ogrodnik_amator',
  '@kasia.czyta',
  '@remont_u_nas',
  '@kibic_z_poznania',
  '@mlodzi_rodzice',
  '@gory_i_szlaki',
  '@foto_wroclaw',
  '@domowe_wypieki',
];

const EDU_AUTHORS = [
  { handle: '@ekonomia_w_pigulce', displayName: 'Ekonomia w pigułce', followers: 88400 },
  { handle: '@finanse_na_spokojnie', displayName: 'Finanse na Spokojnie', followers: 203000 },
  { handle: '@oszczedzam_madrze', displayName: 'Oszczędzam mądrze', followers: 41200 },
  { handle: '@rynekdzis', displayName: 'RynekDziś', followers: 15600 },
  { handle: '@stopa_procentowa', displayName: 'Stopa procentowa', followers: 9700 },
];

const SCAM_AUTHORS = [
  { handle: '@wiadomosci.dnia.24', displayName: 'Wiadomości Dnia 24' },
  { handle: '@portal.biznes.info', displayName: 'Portal Biznesowy Info' },
  { handle: '@polska.teraz.news', displayName: 'Polska Teraz' },
  { handle: '@inwestycje.dla.kazdego', displayName: 'Inwestycje Dla Każdego' },
  { handle: '@zarabiaj.online.pl', displayName: 'Zarabiaj Online' },
  { handle: '@nowe.mozliwosci.24', displayName: 'Nowe Możliwości' },
  { handle: '@okazja.inwestycyjna', displayName: 'Okazja Inwestycyjna' },
];

const COMPANIES = ['Wisłostal', 'Mazowiecka Energetyka', 'Polski Kabel', 'BioMed Kraków', 'Sudety Mining', 'Bałtycka Logistyka'];

const SHORTENER = 'skroc.to';

function kindFor(platform: Platform, rng: Rng): ContentKind {
  if (platform === 'youtube') return 'transcript';
  if (platform === 'tiktok') return rng.chance(0.7) ? 'transcript' : 'post';
  if (platform === 'web') return 'page';
  return 'post';
}

function base(
  rng: Rng,
  category: Category,
  platforms: [Platform, number][],
  rest: Omit<Draft, 'category' | 'platform' | 'kind' | 'sep'>,
): Draft {
  const platform = rng.weighted(platforms);
  const kind = kindFor(platform, rng);
  return { category, platform, kind, sep: kind === 'page' ? '\n' : ' ', ...rest };
}

const code = (rng: Rng) => rng.pick(['ZYSK', 'START', 'OLA', 'KUBA', 'TOMEK', 'JANEK', 'MAREK']) + rng.int(10, 99);
const slug = (rng: Rng, n = 6) =>
  Array.from({ length: n }, () => 'abcdefghijkmnpqrstuvwxyz23456789'[Math.floor(rng.next() * 32)]).join('');

const firmEntity = (f: Firm, rng: Rng): Entity => ({
  name: f.name,
  role: 'investment_firm',
  knfRegister: { status: 'REGISTERED', matchedName: f.name, score: Math.round(rng.range(0.88, 1) * 100) / 100 },
});

const NON_FIN_POSTS = [
  'Niedzielny obiad u mamy 🍲 rosół jak zawsze najlepszy #niedziela #rodzina',
  'Pierwszy półmaraton zaliczony! 🏃‍♂️ 2:04:31, nogi bolą, ale było warto #bieganie #półmaraton',
  'Zachód słońca nad Bałtykiem 🌅 Jastarnia w listopadzie ma swój klimat #morze #podróże',
  'Kot znowu zajął klawiaturę 😹 praca zdalna level hard #kot #pracazdalna',
  'Szakszuka w 15 minut 🍳 przepis w komentarzu #przepis #śniadanie',
  'Ktoś poleci dobrego mechanika na Pradze? Skrzynia biegów do ogarnięcia 🚗',
  'Co za mecz! 2:2 w doliczonym czasie ⚽ #ekstraklasa',
  'Sadzimy cebulki tulipanów na wiosnę 🌷 #ogród #działka',
  'Skończyłam nową powieść Wiśniewskiej, polecam na długie wieczory 📚 #książki',
  'Remont łazienki, dzień 14… płytki wreszcie położone 🛁 #remont',
  'Szlak na Turbacz w mgle, ale schronisko i szarlotka wynagrodziły wszystko ⛰️ #góry',
  'Wrocławskie krasnale nocą 📸 #wrocław #fotografia',
  'Pierwszy ząbek! 👶 nie spaliśmy całą noc, ale radość ogromna #rodzicielstwo',
  'Domowy chleb na zakwasie, trzecie podejście w końcu udane 🍞 #pieczenie',
];

const NON_FIN_TRANSCRIPTS = [
  'Hej, dzisiaj pokażę wam, jak zrobić najprostsze ciasto ze śliwkami. Potrzebujecie tylko mąki, jajek i cukru, a cała reszta to formalność.',
  'Siema, zabieram was na szybki spacer po Gdańsku. Zaczynamy od Długiego Targu, potem Motława i najlepsze gofry w mieście.',
  'Dzień dobry, w tym odcinku sprawdzamy, czy da się zrobić porządny trening w domu bez sprzętu. Spoiler: da się, ale boli.',
  'Słuchajcie, mój pies nauczył się otwierać lodówkę i nie wiem, czy mam się cieszyć, czy bać.',
];

export function nonFinancial(rng: Rng): Draft {
  const d = base(rng, 'NON_FIN', [['instagram', 3], ['facebook', 3], ['tiktok', 2], ['x', 1]], {
    segs: [],
    author: { handle: rng.pick(USERS), followers: rng.int(80, 9000) },
    links: [],
    entities: [],
    extraIndicators: [],
    topic: 'NON_FINANCIAL',
    contentType: 'OPINION_DISCUSSION',
    instruments: [],
    scam: [0.01, 0.05],
    signals: [],
  });
  d.segs = d.kind === 'transcript' ? [s(rng.pick(NON_FIN_TRANSCRIPTS))] : [s(rng.pick(NON_FIN_POSTS))];
  if (d.kind !== 'transcript' && rng.chance(0.3)) d.segs.push(s(rng.pick(['Miłego weekendu!', 'Dajcie znać w komentarzach 👇', '❤️', 'Zdjęcie: własne.'])));
  return d;
}

const FIN_OTHER_POSTS = [
  'Raty kredytu znowu w dół o 140 zł 🙌 ktoś jeszcze nadpłaca, czy odpuszczacie?',
  'Jak ogarnąć budżet domowy? Ja zapisuję każdy wydatek w arkuszu i po trzech miesiącach widzę, gdzie uciekają pieniądze.',
  'Nowa lokata w moim banku 5,5% na 3 miesiące, tylko dla nowych środków. Sprawdzaliście?',
  'Czy warto brać kartę kredytową tylko dla okresu bezodsetkowego? Pytam poważnie 😅',
  'Ceny w sklepach znowu wyżej. Paragon z dzisiaj: masło 9,99 zł…',
];

export function financialOther(rng: Rng): Draft {
  return base(rng, 'FIN_OTHER', [['facebook', 3], ['x', 3], ['instagram', 1]], {
    segs: [s(rng.pick(FIN_OTHER_POSTS))],
    author: { handle: rng.pick([...USERS, ...EDU_AUTHORS.map((a) => a.handle)]), followers: rng.int(200, 30000) },
    links: [],
    entities: [],
    extraIndicators: [],
    topic: 'FINANCIAL_OTHER',
    contentType: rng.pick(['NEWS_EDU', 'OPINION_DISCUSSION'] as const),
    instruments: [],
    scam: [0.01, 0.06],
    signals: [],
  });
}

// Edukacja, dyskusje, ostrzeżenia przed oszustwami (trudne negatywy)

const EDU_TEMPLATES: { segs: Seg[]; instruments: Instrument[]; title?: string }[] = [
  {
    title: 'Czym jest ETF? Podstawy w 5 minut',
    segs: [
      s('Cześć, w dzisiejszym odcinku tłumaczę, czym jest ETF. To fundusz notowany na giełdzie, który odwzorowuje indeks, na przykład S&P 500 albo WIG20.'),
      s('Największe zalety to niskie opłaty i szeroka dywersyfikacja.'),
      s('Pamiętajcie, że wartość jednostek może spadać i możecie stracić część zainwestowanych pieniędzy.', 'RISK_WARNING'),
    ],
    instruments: ['FUNDS_ETF'],
  },
  {
    segs: [
      s('Inflacja w październiku 4,1% r/r. Co to oznacza dla Twoich oszczędności? 🧵'),
      s('Pieniądze na nieoprocentowanym koncie realnie tracą na wartości, ale to nie znaczy, że trzeba od razu kupować akcje.'),
    ],
    instruments: [],
  },
  {
    title: 'Obligacje skarbowe EDO czy lokata? Porównanie na spokojnie',
    segs: [
      s('Porównajmy obligacje skarbowe EDO i lokatę bankową.'),
      w('Obligacje indeksowane inflacją w długim terminie często wypadały lepiej niż lokaty,', 'PRODUCT_COMPARISON', 'PAST_PERFORMANCE'),
      s('ale wcześniejszy wykup kosztuje i trzeba to uwzględnić.'),
      s('Według danych Ministerstwa Finansów marża w pierwszym roku zmienia się co miesiąc, więc sprawdzajcie aktualne warunki.'),
    ],
    instruments: ['BONDS'],
  },
  {
    title: 'IKE i IKZE w praktyce',
    segs: [
      s('IKE i IKZE to konta, które pozwalają legalnie ograniczyć podatek od zysków kapitałowych.'),
      w('Na IKE po spełnieniu warunków nie płacisz podatku Belki,', 'TAX_CLAIM'),
      s('ale zasady zależą od indywidualnej sytuacji i mogą się zmienić, więc czytajcie regulaminy.'),
    ],
    instruments: ['FUNDS_ETF', 'STOCKS'],
  },
  {
    segs: [
      s('Rynek akcji w listopadzie: WIG20 traci 2%, inwestorzy czekają na decyzję RPP.'),
      s('Najmocniej tracą banki, zyskuje sektor energetyczny.'),
      s('Analitycy są podzieleni co do kierunku na koniec roku.'),
    ],
    instruments: ['STOCKS'],
  },
  {
    title: 'Procent składany – dlaczego warto zacząć wcześnie',
    segs: [
      s('W tym odcinku omówimy procent składany i to, dlaczego czas jest Twoim największym sprzymierzeńcem.'),
      w('Historycznie szeroki rynek akcji dawał kilka procent rocznie ponad inflację,', 'PAST_PERFORMANCE'),
      s('ale wyniki z przeszłości nie gwarantują przyszłych.', 'PAST_PERF_DISCLAIMER'),
      s('Inwestowanie wiąże się z ryzykiem utraty części kapitału.', 'RISK_WARNING'),
    ],
    instruments: ['STOCKS', 'FUNDS_ETF'],
  },
  {
    segs: [
      s('Czym różni się kontrakt CFD od akcji? Kupując CFD nie jesteś właścicielem spółki, tylko zakładasz się o zmianę ceny.'),
      s('Dźwignia działa w obie strony i straty mogą przekroczyć to, czego się spodziewasz.', 'RISK_WARNING'),
    ],
    instruments: ['CFD_FOREX'],
  },
];

const SCAM_AWARE_TEMPLATES: Seg[][] = [
  [
    s('⚠️ Uważajcie na reklamy z wizerunkiem znanych osób,'),
    w('które obiecują gwarantowany zysk 30% miesięcznie.', 'GUARANTEED_PROFIT', 'UNREALISTIC_RETURNS'),
    s('To oszustwo. CERT Polska i KNF regularnie publikują listy takich domen.'),
  ],
  [
    s('Moja ciocia prawie dała się nabrać na „platformę AI”,'),
    w('która miała zarabiać za nią 24/7.', 'AUTOMATED_PROFIT'),
    w('Konsultant dzwonił codziennie i mówił, że zostały ostatnie miejsca.', 'URGENCY_PRESSURE'),
    s('Jeśli ktoś obiecuje zysk bez ryzyka, to znak ostrzegawczy. Przekażcie dalej starszym w rodzinie 🙏'),
  ],
  [
    s('Fałszywe artykuły o tym, że znany sportowiec „inwestuje w nową platformę”, krążą znowu po Facebooku.'),
    w('Schemat jest zawsze ten sam: wpłać 1000 zł, a konsultant oddzwoni.', 'LOW_ENTRY_DEPOSIT', 'OFF_PLATFORM_CONTACT'),
    s('Nie podawajcie numeru telefonu i zgłaszajcie takie reklamy. #oszustwo #bezpieczeństwo'),
  ],
];

const OPINION_POSTS = [
  'Co sądzicie o obligacjach indeksowanych inflacją? Ja trzymam część oszczędności, ale zastanawiam się nad ETF-ami 🤔',
  'Kupiłem pierwsze akcje i od razu -8% 😅 ktoś też tak zaczynał?',
  'Krypto to dla mnie kasyno. Zmieńcie zdanie.',
  'Trzymacie gotówkę na koncie oszczędnościowym czy wszystko w fundusze? Szukam inspiracji, nie porad.',
  'Po roku z ETF-ami: nudno, spokojnie i bez emocji. I chyba o to chodzi.',
];

export function education(rng: Rng): Draft {
  const t = rng.pick(EDU_TEMPLATES);
  const author = rng.pick(EDU_AUTHORS);
  const d = base(rng, 'EDU', [['youtube', 3], ['x', 2], ['facebook', 2], ['web', 2]], {
    segs: t.segs,
    title: t.title,
    author,
    links: [],
    entities: [],
    extraIndicators: [],
    topic: rng.chance(0.85) ? 'INVESTMENT' : 'FINANCIAL_OTHER',
    contentType: 'NEWS_EDU',
    instruments: t.instruments,
    scam: [0.02, 0.12],
    signals: [],
  });
  if (d.kind === 'page' && !d.title) d.title = 'Komentarz rynkowy';
  return d;
}

export function scamAwareness(rng: Rng): Draft {
  return base(rng, 'SCAM_AWARE', [['facebook', 3], ['x', 2], ['instagram', 1], ['tiktok', 1]], {
    segs: rng.pick(SCAM_AWARE_TEMPLATES),
    author: rng.chance(0.5) ? rng.pick(EDU_AUTHORS) : { handle: rng.pick(USERS), followers: rng.int(100, 5000) },
    links: [],
    entities: [],
    extraIndicators: [],
    topic: 'INVESTMENT',
    contentType: 'NEWS_EDU',
    instruments: ['CRYPTO'],
    scam: [0.18, 0.5],
    signals: [],
  });
}

export function opinion(rng: Rng): Draft {
  return base(rng, 'OPINION', [['x', 3], ['facebook', 2], ['instagram', 1]], {
    segs: [s(rng.pick(OPINION_POSTS))],
    author: { handle: rng.pick(USERS), followers: rng.int(50, 4000) },
    links: [],
    entities: [],
    extraIndicators: [],
    topic: 'INVESTMENT',
    contentType: 'OPINION_DISCUSSION',
    instruments: [rng.pick(['STOCKS', 'BONDS', 'CRYPTO', 'FUNDS_ETF'] as const)],
    scam: [0.01, 0.08],
    signals: [],
  });
}

const RISK_CFD_PL = (pct: number) =>
  `CFD są złożonymi instrumentami i wiążą się z dużym ryzykiem szybkiej utraty środków pieniężnych z powodu dźwigni finansowej. ${pct}% rachunków inwestorów detalicznych odnotowuje straty pieniężne w wyniku handlu kontraktami CFD u tego dostawcy.`;
const RISK_CFD_EN = (pct: number) =>
  `CFDs are complex instruments and come with a high risk of losing money rapidly due to leverage. ${pct}% of retail investor accounts lose money when trading CFDs with this provider.`;
const RISK_GENERIC = 'Inwestowanie wiąże się z ryzykiem utraty części lub całości zainwestowanego kapitału.';

export interface FirmOptions {
  firm?: Firm;
  campaignId?: string;
  platforms?: [Platform, number][];
  /** wymuszenia dla serii reklam (klastrów legalnych) */
  forceRisk?: boolean;
  forceTax?: boolean;
}

export function firmMarketing(rng: Rng, opts: FirmOptions = {}): Draft {
  const firm = opts.firm ?? rng.pick(FIRMS);
  const segs: Seg[] = [];
  const cfd = firm.kind === 'cfd';
  const instruments: Instrument[] =
    firm.kind === 'cfd' ? ['CFD_FOREX'] : firm.kind === 'fund' ? ['FUNDS_ETF', 'BONDS'] : ['STOCKS', 'FUNDS_ETF'];

  const withRisk = opts.forceRisk ?? rng.chance(0.55);
  const riskEnglish = cfd && withRisk && rng.chance(0.3);
  const riskAtEnd = rng.chance(0.5);
  const riskPct = rng.int(68, 82);
  const riskSeg = s(cfd ? (riskEnglish ? RISK_CFD_EN(riskPct) : RISK_CFD_PL(riskPct)) : RISK_GENERIC, 'RISK_WARNING');

  if (withRisk && !riskAtEnd) segs.push(riskSeg);

  segs.push(
    s(
      rng.pick(
        cfd
          ? [`${firm.short}: handluj na ponad 3000 instrumentach CFD z dźwignią do 1:30.`, `Platforma ${firm.short} – forex, indeksy i surowce w jednej aplikacji.`]
          : firm.kind === 'fund'
            ? [`Fundusz ${firm.short} Akcji Polskich – inwestuj w liderów GPW.`, `${firm.name} – fundusze dopasowane do Twojego horyzontu.`]
            : [`Otwórz konto w ${firm.short} i inwestuj w akcje z 0 zł prowizji do 100 tys. euro obrotu miesięcznie.`, `${firm.name}: akcje, ETF-y i obligacje w jednym miejscu.`],
      ),
    ),
  );

  if (rng.chance(0.7)) {
    segs.push(
      s(
        rng.pick([
          'Zarabiaj na wzrostach i spadkach kursów! 📈',
          'Twoje oszczędności mogą pracować na 8% rocznie.',
          'Pomnażaj kapitał szybciej niż na lokacie.',
          'Zyskaj więcej z każdej złotówki.',
        ]),
        'PROFIT_CLAIM',
      ),
    );
  }

  if (!cfd && rng.chance(0.45)) {
    const pp = rng.pick(['Fundusz zyskał 23,4% w 2024 roku.', 'Stopa zwrotu 41% w ostatnich 3 latach!', 'Nasi klienci zarobili średnio 17% w zeszłym roku.']);
    // wyniki historyczne na samej górze materiału = reguła 13
    if (rng.chance(0.4)) segs.unshift(s(pp, 'PAST_PERFORMANCE', 'PROFIT_CLAIM'));
    else segs.push(s(pp, 'PAST_PERFORMANCE', 'PROFIT_CLAIM'));
    if (rng.chance(0.5)) segs.push(s('Wyniki osiągnięte w przeszłości nie stanowią gwarancji osiągnięcia podobnych wyników w przyszłości.', 'PAST_PERF_DISCLAIMER'));
    if (rng.chance(0.4)) segs.push(s(`Wyniki za ostatnie 5 lat (2020–2024), źródło: ${firm.short}, w PLN, po potrąceniu opłat; zmiany kursów walut mogą wpłynąć na wynik.`));
  }

  if (rng.chance(0.25)) {
    segs.push(s(`Analitycy ${firm.short} prognozują wzrost WIG20 o 15% w przyszłym roku.`, 'FORECAST'));
    if (rng.chance(0.4)) segs.push(s('Prognozy nie są wiarygodnym wskaźnikiem przyszłych wyników.', 'FORECAST_DISCLAIMER'));
  }

  if (opts.forceTax || (!cfd && rng.chance(0.25))) {
    segs.push(s(rng.pick(['Z IKE nie zapłacisz podatku Belki! 💸', 'Odlicz wpłaty na IKZE od podatku i odzyskaj nawet 2 tys. zł.']), 'TAX_CLAIM'));
    if (rng.chance(0.5)) segs.push(s('Sposób opodatkowania zależy od indywidualnej sytuacji klienta i może ulec zmianie.'));
  }

  if (rng.chance(0.2)) {
    segs.push(s(rng.pick(['Nawet 3 razy taniej niż w innych biurach maklerskich.', 'Najniższe spready na rynku – sprawdź porównanie.']), 'PRODUCT_COMPARISON'));
  }

  if (rng.chance(0.18)) {
    segs.push(
      s(
        rng.pick([
          'Jesteśmy nadzorowani przez KNF – Twoje środki są w pełni bezpieczne.',
          'Produkt zatwierdzony przez KNF, inwestujesz bez obaw.',
          'Spełniamy rygorystyczne wymogi nadzorcze KNF, dlatego to bezpieczna inwestycja.',
        ]),
        'SUPERVISOR_AS_SAFETY',
      ),
    );
  }

  segs.push(s(rng.pick([`Sprawdź na ${firm.domain} 👉`, 'Otwórz konto w 10 minut.', `Więcej informacji: ${firm.domain}`])));
  if (rng.chance(0.55)) segs.push(s(rng.pick(['Materiał reklamowy.', '#reklama', 'Komunikat marketingowy.']), 'AD_DISCLOSURE'));
  if (rng.chance(0.4)) segs.push(s(`${firm.name} podlega nadzorowi Komisji Nadzoru Finansowego.`));
  if (withRisk && riskAtEnd) segs.push(riskSeg);

  return base(rng, 'FIRM', opts.platforms ?? [['web', 3], ['facebook', 3], ['instagram', 2], ['youtube', 1]], {
    segs,
    title: undefined,
    author: { handle: '@' + firm.short.toLowerCase().replace(/[^a-z]/g, ''), displayName: firm.short, followers: rng.int(5000, 90000) },
    links: [`https://${firm.domain}/${rng.pick(['promocja', 'konto', 'oferta', 'fundusze'])}?utm_source=social`],
    entities: [firmEntity(firm, rng)],
    extraIndicators: [],
    topic: 'INVESTMENT',
    contentType: 'FIRM_OWN_MARKETING',
    instruments,
    scam: cfd ? [0.06, 0.28] : [0.01, 0.12],
    signals: [],
    campaignId: opts.campaignId,
  });
}

export interface PromoOptions {
  firm?: Firm;
  author?: (typeof FINFLUENCERS)[number];
  campaignId?: string;
  promoCode?: string;
}

export function thirdPartyPromo(rng: Rng, opts: PromoOptions = {}): Draft {
  const firm = opts.firm ?? rng.pick(FIRMS.filter((f) => f.kind !== 'bank'));
  const author = opts.author ?? rng.pick(FINFLUENCERS);
  const promoCode = opts.promoCode ?? code(rng);
  const segs: Seg[] = [];
  const disclosed = rng.chance(0.5);

  if (disclosed && rng.chance(0.5)) {
    segs.push(s(rng.pick([`Materiał powstał we współpracy z ${firm.short}.`, `Odcinek sponsorowany przez ${firm.short}.`]), 'AD_DISCLOSURE'));
  }
  segs.push(
    s(
      rng.pick([
        `Od pół roku inwestuję przez ${firm.short} i powiem Wam szczerze: najlepsza aplikacja, jakiej używałem 🔥`,
        `Dużo pytaliście, gdzie trzymam swój portfel. Odpowiedź: ${firm.short}.`,
        `Testuję ${firm.short} od miesiąca i jestem w szoku, jakie to proste.`,
      ]),
    ),
  );
  if (rng.chance(0.65)) {
    segs.push(
      s(
        rng.pick(['Mój portfel w tym roku +34% 📈', 'Spokojnie da się wyciągnąć 10% rocznie.', 'Na samym złocie i S&P zrobiłem w tym roku więcej niż na lokacie przez 5 lat.']),
        'PROFIT_CLAIM',
        ...(rng.chance(0.5) ? (['PAST_PERFORMANCE'] as FlagKey[]) : []),
      ),
    );
  }
  if (rng.chance(0.35)) segs.push(s(rng.pick(['Ja dokupiłem ETF na S&P 500 i Wam też polecam.', 'Teraz jest moment na złoto, ja kupuję.']), 'SPECIFIC_INSTRUMENT_CALL'));
  segs.push(s(`Z kodem ${promoCode} dostajesz darmowe akcje o wartości do 200 zł 🎁 link w bio.`));
  if (rng.chance(0.35)) segs.push(s('Pamiętajcie, inwestowanie wiąże się z ryzykiem.', 'RISK_WARNING'));
  if (disclosed && !segs.some((x) => x.flags?.includes('AD_DISCLOSURE'))) segs.push(s('#reklama #współpraca', 'AD_DISCLOSURE'));
  else if (!disclosed) segs.push(s(rng.pick(['#inwestowanie #giełda #pasywnydochód', '#finanse #etf', '#trading #money'])));

  return base(rng, 'PROMO', [['instagram', 3], ['tiktok', 2], ['youtube', 2], ['facebook', 1]], {
    segs,
    author,
    links: [`https://${SHORTENER}/${slug(rng)}`, `https://${firm.domain}/polecam?ref=${promoCode.toLowerCase()}`],
    entities: [
      firmEntity(firm, rng),
      { name: author.displayName, role: 'advertiser', knfRegister: { status: 'NOT_FOUND' } },
    ],
    extraIndicators: [],
    topic: 'INVESTMENT',
    contentType: 'THIRD_PARTY_PROMO',
    instruments: firm.kind === 'cfd' ? ['CFD_FOREX'] : ['STOCKS', 'FUNDS_ETF'],
    scam: [0.03, 0.25],
    signals: [],
    campaignId: opts.campaignId,
  });
}

export function recommendation(rng: Rng): Draft {
  const company = rng.pick(COMPANIES);
  const author = rng.chance(0.6) ? rng.pick(FINFLUENCERS) : { handle: rng.pick(USERS), followers: rng.int(300, 6000) };
  const segs = rng.pick<Seg[]>([
    [
      s(`Kupuję akcje ${company}, cena docelowa 120 zł 🚀`, 'SPECIFIC_INSTRUMENT_CALL', 'FORECAST'),
      s('Moim zdaniem okazja dekady.', 'PROFIT_CLAIM'),
      s('To nie jest rekomendacja, tylko moja opinia.'),
    ],
    [
      s(`Sprzedajcie ${company} póki czas, wyniki kwartalne będą fatalne.`, 'SPECIFIC_INSTRUMENT_CALL', 'FORECAST'),
      s('Ja wyszedłem całą pozycją.'),
    ],
    [
      s(`Mój typ na grudzień: ${company}.`),
      s('Kurs może podwoić się do wiosny,', 'FORECAST', 'PROFIT_CLAIM'),
      s('wchodzę za 20% portfela.', 'SPECIFIC_INSTRUMENT_CALL'),
    ],
  ]);
  return base(rng, 'RECO', [['x', 3], ['youtube', 2], ['tiktok', 1], ['facebook', 1]], {
    segs,
    author,
    links: [],
    entities: [],
    extraIndicators: [],
    topic: 'INVESTMENT',
    contentType: 'RECOMMENDATION',
    instruments: ['STOCKS'],
    scam: [0.03, 0.2],
    signals: [],
  });
}

export function serviceOffer(rng: Rng): Draft {
  const advisor = rng.weighted(ADVISORS.map((a) => [a, a.registered ? 1 : a.nonInstrument ? 1.5 : 3] as const));
  const segs: Seg[] = [];
  if (advisor.nonInstrument) {
    segs.push(s(`${advisor.name}: doradzę, jak bezpiecznie ulokować oszczędności w złocie inwestycyjnym i nieruchomościach.`, 'PERSONALIZED_ADVICE'));
    segs.push(s('Konsultacja 300 zł, pierwsza rozmowa gratis.', 'PAID_ADVISORY_SERVICE'));
  } else if (advisor.registered) {
    segs.push(s(`${advisor.name}: usługa doradztwa inwestycyjnego dla klientów detalicznych.`));
    segs.push(s('Doradca przygotuje rekomendację dopasowaną do Twojego profilu ryzyka.', 'PERSONALIZED_ADVICE'));
    segs.push(s(RISK_GENERIC, 'RISK_WARNING'));
  } else {
    segs.push(
      s(
        rng.pick([
          `${advisor.name} – profesjonalne doradztwo inwestycyjne. Dobierzemy portfel akcji i obligacji do Twojej sytuacji i celów.`,
          `Konsultacja portfelowa 1:1 z ${advisor.name}. Przeanalizuję Twoje inwestycje i powiem, co kupić, a co sprzedać.`,
          `${advisor.name}: zarządzamy portfelami klientów od 500 tys. zł, indywidualna strategia dla każdej rodziny.`,
        ]),
        'PERSONALIZED_ADVICE',
      ),
    );
    segs.push(
      s(
        rng.pick(['Konsultacja 490 zł.', 'Abonament VIP 199 zł/mies.: co tydzień konkretne spółki z GPW pod Twój profil.', 'Wynagrodzenie: 1,5% wartości portfela rocznie.']),
        'PAID_ADVISORY_SERVICE',
      ),
    );
    if (rng.chance(0.5)) segs.push(s('Powiem Ci wprost, które fundusze sprzedać, a które ETF-y dokupić.', 'SPECIFIC_INSTRUMENT_CALL'));
    if (rng.chance(0.4)) segs.push(s('Moi klienci zarabiają średnio 18% rocznie.', 'PROFIT_CLAIM'));
  }
  segs.push(s(rng.pick(['Napisz na priv albo umów bezpłatną rozmowę.', `Zapisy: ${advisor.domain}/konsultacja`, 'Link do kalendarza w bio.'])));

  return base(rng, 'OFFER', [['web', 3], ['facebook', 2], ['instagram', 2], ['youtube', 1]], {
    segs,
    title: undefined,
    author: { handle: advisor.handle, displayName: advisor.name, followers: rng.int(400, 25000) },
    links: [`https://${advisor.domain}/konsultacja`],
    entities: [
      {
        name: advisor.name,
        role: 'advisor',
        knfRegister: advisor.registered
          ? { status: 'REGISTERED', matchedName: advisor.name, score: 0.97 }
          : { status: 'NOT_FOUND' },
      },
    ],
    extraIndicators: [],
    topic: 'INVESTMENT',
    contentType: 'SERVICE_OFFER',
    instruments: advisor.nonInstrument ? ['NON_INSTRUMENT'] : ['STOCKS', 'BONDS', 'FUNDS_ETF'],
    scam: [0.06, 0.35],
    signals: advisor.registered || advisor.nonInstrument ? [] : ['NOT_IN_REGISTER'],
  });
}

export interface CampaignDef {
  id: string;
  name: string;
  scam: boolean;
  size: number;
  daysAgoStart: number;
  daysAgoEnd: number;
  status: CampaignStatus;
  platforms: [Platform, number][];
  brand?: string;
  brandEntity?: Entity;
  person?: string;
  phone?: string;
  telegram?: string;
  whatsapp?: string;
  domains: string[];
  operator?: string;
  signals: ScamSignal[];
  template: (rng: Rng, c: CampaignDef, domain: string) => Seg[];
  /** dla klastrów legalnych */
  legit?: (rng: Rng) => Draft;
}

const pickV = (rng: Rng, items: string[]) => rng.pick(items);

export const CAMPAIGNS: CampaignDef[] = [
  {
    id: 'C-01',
    name: 'Fałszywa platforma AI – marka Orzeł Energia (tel. +48 732…)',
    scam: true,
    size: 24,
    daysAgoStart: 27,
    daysAgoEnd: 0,
    status: 'ACTIVE',
    platforms: [['facebook', 4], ['instagram', 2], ['youtube', 1], ['web', 2]],
    brand: 'Orzeł Energia',
    person: 'Jerzy Bogacki',
    phone: '+48 732 118 404',
    telegram: 't.me/orzel_zysk_pl',
    domains: ['orzel-energia-ai.online', 'orzelenergia-inwest.top', 'oe-platforma.click', 'energia-zysk24.site'],
    operator: 'Quantum Profit AI',
    signals: ['IMPERSONATION', 'CERT_LIST_DOMAIN', 'KNF_WARNING_LIST', 'TEXT_MODEL'],
    template: (rng, c) => [
      s(pickV(rng, [`PILNE: ${c.brand} uruchamia platformę inwestycyjną dla Polaków!`, `Wiadomości: nowa platforma ${c.brand} zmienia życie zwykłych ludzi.`]), 'FAKE_NEWS_FORMAT', 'CELEBRITY_OR_BRAND_ENDORSEMENT'),
      s(pickV(rng, [`${c.person} potwierdza: sztuczna inteligencja handluje za Ciebie 24/7.`, 'Algorytm AI sam zawiera transakcje, Ty tylko wypłacasz zyski.']), 'AUTOMATED_PROFIT', 'CELEBRITY_OR_BRAND_ENDORSEMENT'),
      s(pickV(rng, ['Wystarczy wpłata 250 USD (ok. 1000 zł).', 'Zacznij już od 1000 zł.']), 'LOW_ENTRY_DEPOSIT'),
      s(pickV(rng, ['Zysk nawet 2 400 zł dziennie', 'Średnio 30% miesięcznie']), 'UNREALISTIC_RETURNS', 'PROFIT_CLAIM'),
      s(pickV(rng, ['gwarantowany od pierwszego dnia.', 'gwarantowany umową.']), 'GUARANTEED_PROFIT'),
      s(`Zostaw numer, konsultant oddzwoni w 15 minut lub zadzwoń: ${c.phone}`, 'OFF_PLATFORM_CONTACT'),
      ...(rng.chance(0.5) ? [s(`Kanał z wynikami: ${c.telegram}`, 'OFF_PLATFORM_CONTACT')] : []),
      s(pickV(rng, ['Rejestracja tylko do północy!', 'Zostało ostatnie 17 miejsc!']), 'URGENCY_PRESSURE'),
    ],
  },
  {
    id: 'C-02',
    name: 'Fałszywy wywiad – Kamil Bramski „inwestuje” (domeny .online/.top)',
    scam: true,
    size: 15,
    daysAgoStart: 22,
    daysAgoEnd: 2,
    status: 'ACTIVE',
    platforms: [['facebook', 3], ['web', 3], ['youtube', 1]],
    person: 'Kamil Bramski',
    phone: '+48 571 220 913',
    domains: ['bramski-wywiad.online', 'sekret-bramskiego.top', 'wywiad-dnia.click'],
    operator: 'EuroCapital Prime',
    signals: ['CERT_LIST_DOMAIN', 'TEXT_MODEL'],
    template: (rng, c) => [
      s(pickV(rng, [`Skandal w studiu! ${c.person} zdradził na antenie, jak zarabia 50 000 zł miesięcznie.`, `${c.person} w szczerym wywiadzie: „To zmieniło moje życie”.`]), 'FAKE_NEWS_FORMAT', 'CELEBRITY_OR_BRAND_ENDORSEMENT'),
      s(pickV(rng, ['Banki nie chcą, żebyś o tym wiedział.', 'Stacja próbowała usunąć ten materiał.']), 'SECRECY_CONSPIRACY'),
      s('Z 1000 zł w miesiąc zrobił 15 000 zł,', 'UNREALISTIC_RETURNS', 'PROFIT_CLAIM'),
      s(pickV(rng, ['bez żadnego ryzyka.', 'a Twoje pieniądze są w 100% bezpieczne.']), 'NO_RISK_CLAIM'),
      s('Kliknij, zanim artykuł zostanie usunięty.', 'URGENCY_PRESSURE'),
    ],
  },
  {
    id: 'C-03',
    name: 'Podszywanie się – Bank Nadwiślański „program dla klientów” (tel. +48 669…)',
    scam: true,
    size: 12,
    daysAgoStart: 18,
    daysAgoEnd: 1,
    status: 'ACTIVE',
    platforms: [['facebook', 3], ['instagram', 2], ['tiktok', 1]],
    brand: 'Bank Nadwiślański',
    brandEntity: {
      name: 'Bank Nadwiślański S.A.',
      role: 'investment_firm',
      knfRegister: { status: 'REGISTERED', matchedName: 'Bank Nadwiślański S.A.', score: 0.93 },
    },
    phone: '+48 669 402 155',
    whatsapp: 'wa.me/48669402155',
    domains: ['nadwislanski-program.online', 'bank-nadwislanski-inwestycje.site'],
    signals: ['IMPERSONATION', 'CERT_LIST_DOMAIN', 'TEXT_MODEL'],
    template: (rng, c) => [
      s(`${c.brand} ogłasza program inwestycyjny dla swoich klientów.`, 'CELEBRITY_OR_BRAND_ENDORSEMENT'),
      s(pickV(rng, ['Gwarantowany zysk 12% w skali miesiąca.', 'Zysk gwarantowany przez bank.']), 'GUARANTEED_PROFIT', 'UNREALISTIC_RETURNS', 'PROFIT_CLAIM'),
      s('Program zatwierdzony przez KNF, środki w pełni bezpieczne.', 'SUPERVISOR_AS_SAFETY', 'NO_RISK_CLAIM'),
      s(`Napisz na WhatsApp ${c.whatsapp} albo zostaw numer, doradca oddzwoni.`, 'OFF_PLATFORM_CONTACT'),
      s(pickV(rng, ['Oferta ważna tylko 48 godzin.', 'Liczba miejsc ograniczona.']), 'URGENCY_PRESSURE'),
    ],
  },
  {
    id: 'C-04',
    name: 'Krypto-bot „30% miesięcznie” (t.me/kryptobot_30)',
    scam: true,
    size: 9,
    daysAgoStart: 14,
    daysAgoEnd: 0,
    status: 'ACTIVE',
    platforms: [['tiktok', 3], ['instagram', 2], ['youtube', 1]],
    telegram: 't.me/kryptobot_30',
    domains: ['kryptobot30.app', 'bot-zysk.site'],
    operator: 'BitPolska Trade',
    signals: ['KNF_WARNING_LIST', 'TEXT_MODEL'],
    template: (rng, c) => [
      s(pickV(rng, ['Mój bot krypto robi za mnie 30% miesięcznie 🤖💰', 'Ten bot handluje bitcoinem lepiej niż fundusze.']), 'AUTOMATED_PROFIT', 'UNREALISTIC_RETURNS', 'PROFIT_CLAIM'),
      s('Zero wiedzy, zero ryzyka.', 'NO_RISK_CLAIM'),
      s('Start od 500 zł.', 'LOW_ENTRY_DEPOSIT'),
      s(`Dostęp tylko przez ${c.telegram}`, 'OFF_PLATFORM_CONTACT'),
      s('#krypto #pasywnydochód #bitcoin'),
    ],
  },
  {
    id: 'C-05',
    name: 'Fałszywy opiekun konta – marka Alfa Invest (WhatsApp)',
    scam: true,
    size: 8,
    daysAgoStart: 12,
    daysAgoEnd: 3,
    status: 'MONITORED',
    platforms: [['facebook', 2], ['instagram', 2]],
    brand: 'Alfa Invest',
    brandEntity: {
      name: 'Alfa Invest Dom Maklerski S.A.',
      role: 'investment_firm',
      knfRegister: { status: 'REGISTERED', matchedName: 'Alfa Invest Dom Maklerski S.A.', score: 0.91 },
    },
    whatsapp: 'wa.me/48790331208',
    phone: '+48 790 331 208',
    domains: ['alfa-invest-pl.online', 'alfainvest-opiekun.top'],
    signals: ['IMPERSONATION', 'NOT_IN_REGISTER', 'TEXT_MODEL'],
    template: (rng, c) => [
      s(`Jestem opiekunem klienta w ${c.brand}.`, 'CELEBRITY_OR_BRAND_ENDORSEMENT'),
      s('Dobiorę strategię do Twojej sytuacji i będę prowadzić Twoje inwestycje.', 'PERSONALIZED_ADVICE'),
      s(pickV(rng, ['Klienci zarabiają u nas 20% miesięcznie.', 'Średni zysk klienta to 8 000 zł w pierwszym miesiącu.']), 'UNREALISTIC_RETURNS', 'PROFIT_CLAIM'),
      s(`Kontakt tylko przez WhatsApp: ${c.whatsapp}`, 'OFF_PLATFORM_CONTACT'),
    ],
  },
  {
    id: 'C-06',
    name: 'Złoto „bez ryzyka” – niski próg wejścia (tel. +48 512…)',
    scam: true,
    size: 6,
    daysAgoStart: 25,
    daysAgoEnd: 9,
    status: 'MONITORED',
    platforms: [['facebook', 2], ['web', 2], ['youtube', 1]],
    phone: '+48 512 774 690',
    domains: ['zloto-bez-ryzyka.site', 'inwestuj-w-zloto24.online'],
    signals: ['CERT_LIST_DOMAIN', 'TEXT_MODEL'],
    template: (rng, c) => [
      s('Inwestycja w złoto, która zawsze zarabia.', 'GUARANTEED_PROFIT', 'PROFIT_CLAIM'),
      s('Bez żadnego ryzyka i bez wiedzy.', 'NO_RISK_CLAIM'),
      s(pickV(rng, ['Wystarczy 800 zł na start.', 'Minimalna wpłata 250 euro.']), 'LOW_ENTRY_DEPOSIT'),
      s(`Zadzwoń: ${c.phone}`, 'OFF_PLATFORM_CONTACT'),
    ],
  },
  {
    id: 'C-07',
    name: 'Podszywanie się – Telekom Wisła „akcje dla obywateli”',
    scam: true,
    size: 5,
    daysAgoStart: 8,
    daysAgoEnd: 0,
    status: 'ACTIVE',
    platforms: [['facebook', 3], ['web', 1]],
    brand: 'Telekom Wisła',
    person: 'Ewa Rybińska',
    phone: '+48 881 093 417',
    domains: ['telekom-wisla-akcje.online', 'akcje-dla-polakow.top'],
    signals: ['IMPERSONATION', 'CERT_LIST_DOMAIN', 'TEXT_MODEL'],
    template: (rng, c) => [
      s(`Wiadomości: ${c.brand} rozdaje akcje obywatelom, ${c.person} pokazuje, jak je odebrać.`, 'FAKE_NEWS_FORMAT', 'CELEBRITY_OR_BRAND_ENDORSEMENT'),
      s(pickV(rng, ['Każdy może zarobić 5 000 zł miesięcznie.', 'Z 700 zł robi się 9 000 zł.']), 'UNREALISTIC_RETURNS', 'PROFIT_CLAIM'),
      s('Program kończy się jutro.', 'URGENCY_PRESSURE'),
      s(`Infolinia: ${c.phone}`, 'OFF_PLATFORM_CONTACT'),
    ],
  },
  {
    id: 'C-08',
    name: 'Grupa „Sygnały VIP” na Telegramie',
    scam: true,
    size: 5,
    daysAgoStart: 20,
    daysAgoEnd: 6,
    status: 'MONITORED',
    platforms: [['tiktok', 2], ['instagram', 2], ['x', 1]],
    telegram: 't.me/sygnaly_vip_pl',
    domains: ['sygnaly-vip.site'],
    signals: ['TEXT_MODEL'],
    template: (rng, c) => [
      s(pickV(rng, ['Moi ludzie z grupy VIP zgarnęli wczoraj +300% na jednym sygnale 🚀', 'Sygnały, które dają 90% skuteczności.']), 'UNREALISTIC_RETURNS', 'PROFIT_CLAIM'),
      s('Tego nie pokażą Ci w banku.', 'SECRECY_CONSPIRACY'),
      s('Zysk pewny jak w banku.', 'GUARANTEED_PROFIT'),
      s(`Wejście tylko dziś: ${c.telegram}`, 'URGENCY_PRESSURE', 'OFF_PLATFORM_CONTACT'),
    ],
  },
  // --- klastry legalne ---
  {
    id: 'C-09',
    name: 'Delta Markets – seria reklam CFD',
    scam: false,
    size: 7,
    daysAgoStart: 26,
    daysAgoEnd: 4,
    status: 'MONITORED',
    platforms: [['web', 2], ['facebook', 2], ['instagram', 1]],
    domains: ['deltamarkets.com.pl'],
    signals: [],
    template: () => [],
    legit: (rng) => firmMarketing(rng, { firm: FIRMS[3], campaignId: 'C-09', platforms: [['web', 2], ['facebook', 2], ['instagram', 1]] }),
  },
  {
    id: 'C-10',
    name: 'Beta Capital – kampania IKE/IKZE',
    scam: false,
    size: 6,
    daysAgoStart: 15,
    daysAgoEnd: 2,
    status: 'CLOSED',
    platforms: [['facebook', 2], ['youtube', 1], ['web', 1]],
    domains: ['betacapital.pl'],
    signals: [],
    template: () => [],
    legit: (rng) =>
      firmMarketing(rng, { firm: FIRMS[1], campaignId: 'C-10', forceTax: true, platforms: [['facebook', 2], ['youtube', 1], ['web', 1]] }),
  },
  {
    id: 'C-11',
    name: '@trader_tomek × Omega Trade – kod polecający',
    scam: false,
    size: 6,
    daysAgoStart: 21,
    daysAgoEnd: 1,
    status: 'MONITORED',
    platforms: [['instagram', 2], ['tiktok', 2], ['youtube', 1]],
    domains: ['omegatrade.eu'],
    signals: [],
    template: () => [],
    legit: (rng) =>
      thirdPartyPromo(rng, { firm: FIRMS[4], author: FINFLUENCERS[4], campaignId: 'C-11', promoCode: 'TOMEK30' }),
  },
];

export function campaignDraft(rng: Rng, c: CampaignDef): Draft {
  if (c.legit) return c.legit(rng);
  const domain = rng.pick(c.domains);
  const author = rng.chance(0.6)
    ? rng.pick(SCAM_AUTHORS)
    : { handle: `@${rng.pick(['anna', 'pawel', 'kasia', 'marek', 'ewa', 'jan'])}.${rng.int(1960, 2001)}`, displayName: undefined };
  const extra: Indicator[] = [];
  if (c.brand) extra.push({ type: 'brand', value: c.brand });
  if (c.person) extra.push({ type: 'person', value: c.person });
  if (c.phone) extra.push({ type: 'phone', value: c.phone });
  if (c.telegram) extra.push({ type: 'telegram', value: c.telegram });
  if (c.whatsapp) extra.push({ type: 'whatsapp', value: c.whatsapp });

  const entities: Entity[] = [];
  if (c.brandEntity) entities.push(c.brandEntity);
  if (c.operator) entities.push({ name: c.operator, role: 'investment_firm', knfRegister: { status: 'ON_WARNING_LIST', matchedName: c.operator, score: 0.96 } });

  const path = rng.pick(['rejestracja', 'start', 'wywiad', 'promo', 'pl']);
  const links = [`https://${domain}/${path}?src=${rng.pick(['fb', 'ig', 'yt', 'tt'])}`];
  if (rng.chance(0.4)) links.unshift(`https://${SHORTENER}/${slug(rng)}`);

  const d = base(rng, 'SCAM', c.platforms, {
    segs: c.template(rng, c, domain),
    author: { ...author, followers: rng.int(20, 4000) },
    links,
    entities,
    extraIndicators: extra,
    topic: 'INVESTMENT',
    contentType: rng.pick(['THIRD_PARTY_PROMO', 'SERVICE_OFFER', 'FIRM_OWN_MARKETING'] as const),
    instruments: c.id === 'C-04' ? ['CRYPTO'] : c.id === 'C-06' ? ['NON_INSTRUMENT'] : ['CFD_FOREX', 'CRYPTO'],
    scam: [0.78, 0.99],
    signals: c.signals,
    campaignId: c.id,
  });
  if (d.kind === 'page') d.title = rng.pick(['Wywiad, który poruszył Polskę', 'Nowa platforma inwestycyjna', 'Rejestracja – ostatnie miejsca']);
  if (d.kind === 'transcript') d.title = rng.pick(['WYWIAD NA ŻYWO', 'Jak zarabiam bez pracy', 'Ten sposób działa']);
  return d;
}

/** Pojedynczy scam spoza kampanii. */
export function standaloneScam(rng: Rng): Draft {
  const domain = `${rng.pick(['szybki-zysk', 'inwest-pro', 'kapital-plus', 'zarobek-dzis'])}${rng.int(1, 99)}.${rng.pick(['online', 'top', 'site'])}`;
  const segs = rng.pick<Seg[]>([
    [s('Zarabiaj 1000 zł dziennie z telefonu.', 'UNREALISTIC_RETURNS', 'PROFIT_CLAIM'), s('Bez ryzyka, bez doświadczenia.', 'NO_RISK_CLAIM'), s(`Szczegóły: ${domain}`)],
    [s('Platforma AI, która sama inwestuje Twoje pieniądze.', 'AUTOMATED_PROFIT'), s('Zysk gwarantowany.', 'GUARANTEED_PROFIT'), s('Zostaw numer, oddzwonimy.', 'OFF_PLATFORM_CONTACT')],
  ]);
  return base(rng, 'SCAM', [['facebook', 2], ['instagram', 1], ['tiktok', 1]], {
    segs,
    author: { handle: `@user${rng.int(100000, 999999)}`, followers: rng.int(0, 300) },
    links: [`https://${domain}/`],
    entities: [],
    extraIndicators: [],
    topic: 'INVESTMENT',
    contentType: 'SERVICE_OFFER',
    instruments: ['CRYPTO', 'CFD_FOREX'],
    scam: [0.62, 0.9],
    signals: ['TEXT_MODEL'],
  });
}

export const ANALYSTS = ['a.nowicka', 'k.mazur', 'p.zielinski', 'm.wojcik'];
