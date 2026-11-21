# Zadanie: frontend (dashboard) InvestWatch

Budujesz aplikację webową dla analityków UKNF. Pokazuje ona wyniki klasyfikacji treści z social mediów
(posty FB/IG/TikTok/X, transkrypcje filmów YT/TikTok) wykrytych przez moduły AI. Projekt powstaje na hackathonie
i ma ok. 12h budżetu, więc liczy się działające, stabilne demo.

Zanim zaczniesz, przeczytaj:
- `pliki_dc/markdown/Opis Wyzwania HackNation UKNF 19.11.md` – wymagania organizatora (sekcja 3.3 Dashboard, sekcje 5–6),
- `pliki_dc/markdown/ZASÓB DLA UCZESTNIKÓW - InvestWatch - kryteria oceny informacji o ryzyku.md` – 18 reguł,
- `docs/plan-model.md` – co zwraca model (etykiety, flagi, prawdopodobieństwa).

**Pracuj tylko w `frontend/`.** Nie ruszaj `ml/`, `pliki_dc/` ani `docs/` poza własnym README w `frontend/`.
Backend (Node.js, robi go inna osoba) jeszcze nie istnieje. Pracujesz na mock serwerze, który jest
jednocześnie kontraktem API (sekcja 4).

---

## 1. Kontekst biznesowy (krótko)

System ma 3 moduły analityczne:
- **Moduł 1 – Finfluencerzy / podmioty trzecie:** reklamy firm inwestycyjnych publikowane przez osoby trzecie.
  Raport: firma, reklamujący, treść, URL.
- **Moduł 2 – Zgodność informacji o ryzyku:** materiały firm inwestycyjnych sprawdzane pod kątem 18 reguł
  (np. obietnica zysku bez ostrzeżenia o ryzyku).
- **Moduł 3 – Shadow advisory:** podmioty spoza rejestru KNF oferujące faktyczne doradztwo inwestycyjne.
- **Oszustwa (scam)** to przekrojowa ścieżka, ważna dla zespołu. Fałszywe reklamy inwestycyjne podszywają się pod znane
  firmy i osoby (deepfake celebrytów, „platforma AI zarabia za Ciebie”, „zostaw numer, konsultant oddzwoni”).
  Według CSIRT KNF to zdecydowana większość zgłaszanych oszukańczych domen. Scam ma własny score i sygnały, jest
  osobnym filtrem i osobną kategorią na wykresach. Wysoki scam score zawsze generuje alert CRITICAL.

Jury ocenia m.in.: działanie demo, **wpływ progu (threshold) na wyniki w panelu kalibracji**, stabilność UI,
powiadomienia real-time, **bezpieczeństwo bibliotek** i **czystość konsoli (console.log)**.

Użytkownik to analityk, nie data scientist. Interfejs ma być po polsku, rzeczowy i gęsty informacyjnie,
bez marketingowego designu.

## 2. Stack (wymagany)

- Vite + React 18 + TypeScript (strict)
- **Mantine** (UI, tabele, daty, notyfikacje) – open source, MIT
- **Recharts** (wykresy – wymieniony w specyfikacji organizatora)
- TanStack Query (stan serwerowy), react-router (**HashRouter** – aplikacja może później trafić do Electrona)
- **socket.io-client** (alerty real-time – wymienione w specyfikacji)
- **Cytoscape.js** (graf powiązań / kampanii), z własnym cienkim wrapperem komponentu (props: `graph`, `onNodeClick`, `highlightId`)
- dayjs
- Mock serwer: Node + express + socket.io w `frontend/mock-server/`

Wymagania techniczne:
- Architektura oparta na propsach: komponenty prezentacyjne (`components/`) dostają dane przez props i nie
  fetchują. Fetchują kontenery/strony (`pages/`) przez hooki z `api/`.
- `vite.config.ts`: `base: './'`, żadnych CDN, wszystko działa offline (on-premise).
- Adresy z `.env` (`VITE_API_URL`, `VITE_WS_URL`), dołącz `.env.example`. Żadnych sekretów w kodzie.
- **Zero `console.log` w kodzie.** ESLint `no-console: error`. Konsola przeglądarki na demo ma być pusta:
  bez warningów Reacta, bez błędów key, bez 404.
- Wersje zależności przypięte (bez `^`). Na koniec `npm audit` bez high/critical. Wynik zapisz w README.
- Na koniec `Dockerfile` (multi-stage build → nginx) dla frontu i osobny dla mock-servera. Docker Compose
  złoży ktoś inny, ale obrazy mają się budować.

## 3. Model danych (TypeScript – trzymaj się tych nazw)

```ts
type Platform = 'facebook' | 'instagram' | 'tiktok' | 'youtube' | 'x' | 'web' | 'other';
type ContentKind = 'post' | 'transcript' | 'comment' | 'page';
type ModuleId = 1 | 2 | 3;
type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
type Status = 'NEW' | 'IN_REVIEW' | 'CONFIRMED' | 'DISMISSED' | 'ESCALATED';

type TopicLabel = 'NON_FINANCIAL' | 'FINANCIAL_OTHER' | 'INVESTMENT';
type ContentType = 'NEWS_EDU' | 'OPINION_DISCUSSION' | 'FIRM_OWN_MARKETING' | 'THIRD_PARTY_PROMO' | 'RECOMMENDATION' | 'SERVICE_OFFER';
type Instrument = 'CFD_FOREX' | 'STOCKS' | 'FUNDS_ETF' | 'BONDS' | 'CRYPTO' | 'OTHER_DERIVATIVES' | 'NON_INSTRUMENT';
type FlagKey =
  // zgodność (moduł 2 / 1)
  | 'PROFIT_CLAIM' | 'RISK_WARNING' | 'AD_DISCLOSURE' | 'PAST_PERFORMANCE' | 'PAST_PERF_DISCLAIMER'
  | 'FORECAST' | 'FORECAST_DISCLAIMER' | 'TAX_CLAIM' | 'PRODUCT_COMPARISON' | 'SUPERVISOR_AS_SAFETY'
  // doradztwo (moduł 3)
  | 'PERSONALIZED_ADVICE' | 'PAID_ADVISORY_SERVICE' | 'SPECIFIC_INSTRUMENT_CALL'
  // oszustwo
  | 'GUARANTEED_PROFIT' | 'NO_RISK_CLAIM' | 'UNREALISTIC_RETURNS' | 'URGENCY_PRESSURE'
  | 'CELEBRITY_OR_BRAND_ENDORSEMENT' | 'AUTOMATED_PROFIT' | 'LOW_ENTRY_DEPOSIT'
  | 'OFF_PLATFORM_CONTACT' | 'SECRECY_CONSPIRACY' | 'FAKE_NEWS_FORMAT';

// sygnały scamu spoza tekstu (lookupy backendu)
type ScamSignal =
  | 'IMPERSONATION'          // tekst wymienia zarejestrowaną markę, link prowadzi poza jej oficjalne domeny
  | 'CERT_LIST_DOMAIN'       // domena na liście ostrzeżeń CERT Polska
  | 'KNF_WARNING_LIST'       // podmiot / domena na liście ostrzeżeń publicznych KNF
  | 'NOT_IN_REGISTER'        // oferuje usługi inwestycyjne, brak w rejestrze KNF
  | 'TEXT_MODEL';            // wysoki wynik modelu tekstowego

type EvidenceSection = 'text' | 'transcript' | 'ocr' | 'landing';
interface Evidence {
  section: EvidenceSection;   // gdzie jest dowód: treść posta, transkrypcja, napis na ekranie (OCR), strona docelowa
  start: number; end: number; // offsety w tekście danej sekcji
  text: string;
  t?: number;                 // sekunda nagrania (transkrypcja / OCR)
  landingIndex?: number;      // która strona docelowa
}

interface LandingPageView {
  requestedUrl: string; finalUrl: string; redirectChain: string[];
  title?: string; text: string;
  screenshotUrl?: string; mobileScreenshotUrl?: string;
  hasContactForm: boolean;                 // formularz z telefonem / e-mailem
  domainFlags: ('CERT_LIST_DOMAIN' | 'KNF_WARNING_LIST' | 'IMPERSONATION' | 'NEW_DOMAIN')[];
}

interface MediaView {
  durationS?: number;
  asrUsed: boolean;                        // transkrypcja z naszego ASR (brak napisów platformy)
  keyframes: { t: number; imageUrl: string; ocrText: string }[];
  syntheticVoice?: { score: number; segments: { startS: number; endS: number; score: number }[]; experimental: true };
}

interface FlagScore { p: number; evidence: Evidence[] }

interface Entity {
  name: string;
  role: 'investment_firm' | 'advertiser' | 'advisor';
  knfRegister: { status: 'REGISTERED' | 'NOT_FOUND' | 'ON_WARNING_LIST'; matchedName?: string; score?: number };
}

interface RuleResult {                     // wynik reguły z 18 (oraz reguł modułu 1/3)
  ruleId: string;                          // '3', '12a', '15', 'M3_ADVISORY' ...
  status: 'VIOLATION' | 'OK' | 'NOT_APPLICABLE' | 'NOT_CHECKED';  // NOT_CHECKED = brak danych (np. reguły 4,5,7,8 bez landingu / zrzutu)
  score: number;                           // 0..1
  evidence: Evidence[];
}

type IndicatorType = 'domain' | 'url' | 'phone' | 'telegram' | 'whatsapp' | 'email' | 'wallet' | 'iban'
  | 'brand' | 'person' | 'author';
interface Indicator { type: IndicatorType; value: string }

interface RelatedFinding {
  findingId: string;
  reason: 'SHARES_INDICATOR' | 'SIMILAR_TEXT' | 'SAME_AUTHOR' | 'REDIRECTS_TO';
  detail: string;                          // np. „wspólny numer +48 600 000 000”, „podobieństwo tekstu 0.94”
  score: number;
}

interface Campaign {
  id: string;
  name: string;                            // auto, np. „Fałszywa platforma AI – marka X (tel. +48…)”
  size: number;
  scamShare: number;                       // udział potwierdzonych / wysokich scamów
  avgScam: number;
  firstSeen: string; lastSeen: string;
  platforms: Platform[];
  topIndicators: Indicator[];
  status: 'ACTIVE' | 'MONITORED' | 'CLOSED';
}

interface GraphNode { id: string; kind: 'finding' | IndicatorType; label: string; scamP?: number; campaignId?: string }
interface GraphEdge { source: string; target: string; type: RelatedFinding['reason'] | 'HAS_INDICATOR' | 'IMPERSONATES'; weight: number }
interface Graph { nodes: GraphNode[]; edges: GraphEdge[] }

interface Finding {
  id: string;
  url: string;
  platform: Platform;
  kind: ContentKind;
  author: { handle: string; displayName?: string; followers?: number };
  title?: string;
  text: string;                            // treść posta / transkrypcja
  publishedAt?: string;                    // ISO
  fetchedAt: string;                       // ISO
  modules: ModuleId[];                     // do których modułów trafił
  topic: Record<TopicLabel, number>;
  contentType: Record<ContentType, number>;
  instruments: Record<Instrument, number>;
  flags: Record<FlagKey, FlagScore>;
  rules: RuleResult[];
  entities: Entity[];
  outboundLinks: string[];                 // linki z posta (landing pages)
  scam: { p: number; signals: ScamSignal[] };   // ścieżka oszustw – niezależna od modułów 1–3
  transcript?: string;                     // gdy wideo
  landingPages: LandingPageView[];         // wzbogacenie: odwiedzone strony docelowe
  media?: MediaView;                       // wzbogacenie: klatki + OCR, analiza głosu
  indicators: Indicator[];
  campaignId?: string;
  related: RelatedFinding[];               // top 5 najsilniej powiązanych
  riskScore: number;                       // 0..1, liczony przez backend z progów
  riskLevel: RiskLevel;
  status: Status;
  history: { at: string; status: Status; user: string; comment?: string }[];
  modelVersion: string;
}

interface Thresholds {                     // klucze: 'flags.PROFIT_CLAIM', 'contentType.ADVISORY_OFFER', 'risk.HIGH' ...
  version: string;
  updatedAt: string;
  values: Record<string, number>;
}

interface EvalItem {                       // zbiór walidacyjny z ręcznymi etykietami (gold)
  id: string;
  probs: Record<string, number>;           // te same klucze co Thresholds.values
  gold: Record<string, 0 | 1>;
}
```

## 4. API (mock serwer = kontrakt)

REST, prefiks `/api`:

| Metoda | Ścieżka | Opis |
|---|---|---|
| GET | `/findings?from&to&platform[]&module[]&riskLevel[]&status[]&flag[]&q&sort&page&pageSize` | lista + `total` |
| GET | `/findings/:id` | szczegóły |
| PATCH | `/findings/:id/status` | `{ status, comment? }` → zaktualizowany Finding |
| GET | `/stats/overview?from&to` | KPI: liczby per moduł, poziom ryzyka, platforma, status |
| GET | `/stats/timeseries?from&to&bucket=day&groupBy=module\|platform\|riskLevel` | dane do wykresu trendu |
| GET | `/rules` | definicje reguł (id, nazwa, opis, podstawa prawna, `detectableByText: boolean`) |
| GET | `/thresholds` | aktualne progi |
| PUT | `/thresholds` | zapis progów → backend przelicza `riskLevel`, emituje `thresholds:updated` |
| GET | `/calibration/eval-set` | `EvalItem[]` do liczenia metryk po stronie klienta |
| GET | `/reports/module/:id.csv?…filtry` | eksport raportu (moduł 1 i 3: podmiot, treść, URL) |
| GET | `/campaigns?from&to&minSize&status[]&sort` | lista kampanii |
| GET | `/campaigns/:id` | `Campaign` + `Graph` + lista członków |
| GET | `/findings/:id/graph?depth=1\|2` | ego-graf rekordu |
| GET | `/indicators/:type/:value` | wszystkie rekordy z danym wskaźnikiem (np. numer telefonu) |

Socket.io (namespace `/`):
- `finding:new` → `Finding` (każdy nowy rekord),
- `finding:high_risk` → `Finding` (riskLevel HIGH/CRITICAL) → **alert**,
- `finding:updated` → `Finding`,
- `thresholds:updated` → `Thresholds`,
- `campaign:new_member` → `{ campaign: Campaign, finding: Finding }`. To alert „nowy element znanej kampanii”, wyższy priorytet niż zwykły.

Mock serwer:
- Fixture: ok. 300 rekordów z ostatnich 30 dni. Mają być **realistyczne, po polsku i w stylu social mediów**:
  krótkie posty z hashtagami i emoji, transkrypcje bez interpunkcji (styl ASR). Rozkład: ok. 40% nieinwestycyjnych
  lub edukacyjnych, reszta to reklamy, promocje finfluencerów, oferty „konsultacji portfelowych”, scamy typu
  „gwarantowane 30% miesięcznie”. Generuj je skryptem (`mock-server/seed.ts`), nie ręcznie.
- **Używaj wyłącznie fikcyjnych nazw firm i osób** (np. „Alfa Invest Dom Maklerski S.A.”, „@krypto_marek”).
  Nie używaj prawdziwych podmiotów ani prawdziwych influencerów.
- Evidence ma wskazywać prawdziwe offsety w tekście swojej sekcji.
- Ok. 40% rekordów inwestycyjnych ma `landingPages`, a ok. 30% wideo ma `media`.
  Zrzuty i klatki generuj jako proste obrazki SVG serwowane przez mock (np. makieta fałszywego artykułu z formularzem),
  bez zewnętrznych obrazków.
- Co 15–30 s emituj nowy rekord, a część z nich jako `finding:high_risk`. Interwał ustaw w env, żeby na demo dało się go przyspieszyć.
- `PUT /thresholds` naprawdę przelicza `riskLevel` rekordów. Prosta funkcja: risk = max po naruszonych regułach
  i flagach przekraczających progi.
- **Kampanie w seedzie:** ok. 8 kampanii scamowych po 5–40 rekordów. W ramach kampanii rekordy mają wspólny szablon tekstu
  (z wariacjami), rotujące domeny, wspólne numery telefonów i kanały Telegram. Dodaj 2–3 „klastry” legalne
  (np. seria reklam jednego fikcyjnego brokera), żeby było widać, że graf to nie tylko scamy. Nowe rekordy emitowane przez
  socket czasem dołączają do istniejącej kampanii (`campaign:new_member`).
- `eval-set`: ok. 200 elementów z prawdopodobieństwami skorelowanymi z gold, żeby krzywe PR wyglądały wiarygodnie.

Typy z sekcji 3 trzymaj w jednym pliku `frontend/src/api/types.ts`. Mock serwer też je importuje.

## 5. Ekrany

### 5.1 Przegląd (`/`)
- Kafelki KPI: nowe dziś, HIGH+CRITICAL, liczba per moduł, % potwierdzonych (CONFIRMED / zweryfikowane).
- **Wykres trendu** (Recharts): liczba incydentów w czasie, z przełącznikiem grupowania moduł / platforma / poziom ryzyka.
  Scam jest osobną serią przy grupowaniu po module.
- Kafelek „Podejrzenia oszustwa (24h)” i top podszywanych marek.
- Rozkład per platforma i per typ treści.
- Lista 10 najnowszych HIGH/CRITICAL z linkiem do szczegółów.
- Globalny filtr zakresu dat w headerze, wspólny dla wszystkich ekranów i zapisywany w URL.

### 5.2 Wyniki (`/findings`)
- Tabela: data, platforma (ikona), autor, fragment treści, moduły, typ treści, top flagi (chipy), poziom ryzyka (kolor), status.
- Filtry wymagane przez organizatora: **data, źródło (platforma), poziom ryzyka, moduł**. Dodatkowo: **„podejrzenie oszustwa” (scam ≥ próg)**, status, flaga, wyszukiwanie pełnotekstowe.
- Kolumna/badge „Scam” z wartością p. Wiersze z wysokim scam score wyróżnione wizualnie.
- Filtry trzymaj w query string, żeby dało się wysłać link.
- Sortowanie i paginacja po stronie serwera.
- Zmiana statusu z poziomu wiersza (menu) oraz akcja zbiorcza na zaznaczonych.
- Eksport CSV dla aktualnych filtrów.
- Nowe rekordy z socketu: pasek „N nowych wyników – odśwież”, bez skakania tabeli.

### 5.3 Szczegóły (`/findings/:id`)
To kluczowy ekran do demo, bo pokazuje explainability.
- Pełny tekst z **podświetlonymi fragmentami-dowodami**. Każda flaga ma swój kolor, a hover pokazuje flagę i p.
  Kliknięcie flagi na liście przewija do jej fragmentu.
- Panel wyników: temat, typ treści, instrumenty, flagi jako paski prawdopodobieństwa z zaznaczonym aktualnym progiem.
- **Checklista reguł** (`/rules` + `finding.rules`): VIOLATION / OK / N/A / NOT_CHECKED. NOT_CHECKED to reguły wizualne,
  oznaczone jako „wymaga analizy wizualnej”. Przy każdej regule podaj podstawę prawną.
- Podmioty i status w rejestrze KNF (REGISTERED / NOT_FOUND / ON_WARNING_LIST), wyraźnie zaznaczone dla modułu 1 i 3.
- **Sekcja „Ocena oszustwa”** na górze, jeśli scam ≥ próg:
  - score,
  - lista sygnałów po polsku, np. „Podszywanie się: wymienia markę X, link prowadzi do domeny Y”,
  - podświetlone fragmenty scamowe,
  - linki wychodzące z zaznaczeniem domen podejrzanych.
- Język ostrożny: „cechy oszustwa”, „podejrzenie”, a nie „oszustwo”. To narzędzie wspierające analityka, nie rozstrzygające.
- Metadane: URL (otwierany w nowej karcie z `rel="noopener noreferrer"`), autor, platforma, daty, wersja modelu.
- Zmiana statusu z komentarzem i historia zmian.

- **Zakładka „Strona docelowa”** (gdy są `landingPages`):
  - łańcuch przekierowań jako „breadcrumb” z wyróżnionymi podejrzanymi domenami,
  - zrzuty desktop i mobile obok siebie (lightbox po kliknięciu),
  - badge „Formularz kontaktowy (telefon)”,
  - tekst strony z podświetlonymi dowodami (`section: 'landing'`).
- **Zakładka „Wideo”** (gdy jest `media`):
  - pasek osi czasu z klatkami (miniatury) i napisami z OCR,
  - kliknięcie dowodu z `t` przewija oś czasu,
  - wykres „prawdopodobieństwo syntetycznego głosu” per segment (Recharts, area) z wyraźną etykietą
    „sygnał eksperymentalny – wymaga weryfikacji”,
  - badge, jeśli transkrypcja pochodzi z naszego ASR.
- **Zakładka „Powiązania”:**
  - ego-graf (depth 1/2) z węzłami-rekordami pokolorowanymi wg scam p i węzłami-wskaźnikami (ikony: domena, telefon, Telegram…),
  - lista `related` z powodem („wspólny numer telefonu”, „ten sam szablon tekstu 0.94”),
  - link do kampanii,
  - kliknięcie wskaźnika pokazuje wszystkie rekordy z tym wskaźnikiem.

### 5.3a Kampanie (`/campaigns`)
Ekran „wow” na demo.
- Tabela kampanii: nazwa, rozmiar, udział scamów, platformy, pierwsze i ostatnie wystąpienie, trend (sparkline), status.
- Szczegóły kampanii:
  - **graf sił** (Cytoscape.js, MIT, layout `cose`) z rekordami i wskaźnikami, zoomem i podświetleniem sąsiadów po hoverze,
  - oś czasu pojawiania się elementów kampanii,
  - wspólne wskaźniki,
  - akcja „oznacz kampanię jako scam”, która zmienia status członków (PATCH zbiorczy).
- Nowy członek kampanii z socketu pojawia się w grafie na żywo z krótką animacją.
- Graf bywa duży. Limit ok. 300 węzłów, a powyżej tego agregacja wskaźników. Interakcja ma być płynna.

### 5.4 Panel kalibracji (`/calibration`)
To wymóg jury: „zmiana threshold bezpośrednio wpływa na FP vs FN”.
- Lista progów pogrupowana: flagi, typ treści, poziomy ryzyka. Każdy próg ma suwak i pole liczbowe.
- Dla wybranego progu, **na żywo, po stronie klienta** z `eval-set`:
  macierz pomyłek (TP/FP/FN/TN), precision, recall, F1, **krzywa PR z markerem bieżącego progu**
  oraz wykres precision i recall w funkcji progu.
- Podgląd wpływu na produkcję: „przy tych progach HIGH+CRITICAL: X (było Y)”. Liczone lokalnie z prawdopodobieństw rekordów
  z ostatnich 30 dni albo osobnym endpointem, wybierz prostsze.
- Presety: „Wysoka czułość (recall)”, „Zbalansowany”, „Wysoka precyzja”. Każdy ustawia progi wg F-beta (β=2 / 1 / 0.5) policzonego na eval-set.
- Przyciski „Zapisz” (PUT) i „Przywróć”. Wskaźnik niezapisanych zmian.
- Logikę metryk (confusion matrix, PR, F-beta, wybór progu) umieść w czystych funkcjach w `src/lib/metrics.ts` z testami (Vitest).

### 5.5 Alerty
- Socket `finding:high_risk` pokazuje toast (Mantine notifications) z autorem, platformą, top flagą i linkiem do szczegółów.
- Dzwonek w headerze z licznikiem nieprzeczytanych i dropdownem ostatnich alertów (stan lokalny).
- Wskaźnik połączenia WebSocket (połączono / rozłączono / ponawianie) z automatycznym reconnectem i bez spamowania konsoli.

## 6. Struktura

```
frontend/
  src/
    api/          types.ts, client.ts, hooks (useFindings, useFinding, useThresholds, ...), socket.ts
    components/   prezentacyjne: RiskBadge, PlatformIcon, FlagChips, HighlightedText, ProbBar,
                  RulesChecklist, TrendChart, ConfusionMatrix, PrCurve, ThresholdSlider, ...
    pages/        Overview, Findings, FindingDetail, Calibration
    lib/          metrics.ts (+ testy), format.ts, labels.ts (polskie nazwy etykiet/flag/reguł)
    app/          router, layout, providers
  mock-server/    server.ts, seed.ts, data/
  .env.example  Dockerfile  README.md
```

`lib/labels.ts` zawiera polskie nazwy wyświetlane, np. `PROFIT_CLAIM` → „Obietnica zysku”, `RISK_WARNING` → „Ostrzeżenie o ryzyku”.
Klucze techniczne nie mogą się pojawiać w UI.

## 7. Kolejność i definicja „gotowe”

1. Szkielet, typy, mock serwer z seedem i socketem.
2. Wyniki + Szczegóły (z podświetlaniem evidence).
3. Panel kalibracji z metrykami na żywo.
4. Przegląd z wykresami, alerty.
4a. Powiązania w szczegółach + ekran Kampanie z grafem.
5. Lint, testy metrics, `npm audit`, Dockerfile, README (Quick Start w 5 linijkach, bez lania wody).

Gotowe, gdy:
- `npm run dev:all` uruchamia mock serwer i front,
- wszystkie ekrany działają na danych z mocka,
- przesunięcie suwaka zmienia metryki natychmiast,
- zapis progów zmienia poziomy ryzyka na liście,
- alert pojawia się bez odświeżania,
- konsola przeglądarki jest czysta,
- `npm run lint`, `npm test` i `npm audit --audit-level=high` przechodzą,
- `docker build` dla obu obrazów przechodzi.

Nie commituj. Na koniec wypisz, co zrobiłeś, co zostało i jakie założenia przyjąłeś w kontrakcie API.
