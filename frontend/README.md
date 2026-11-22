# InvestWatch – frontend

Dashboard dla analityków UKNF: wyniki klasyfikacji, explainability, kalibracja progów, kampanie scamowe, alerty real-time.
Działa na mock serwerze, który jest kontraktem API dla backendu.

## Quick Start

```bash
cd frontend
cp .env.example .env        # opcjonalnie
npm ci
npm run dev:all             # mock API :4000 + front :5173 (nowe rekordy co 15–30 s)
npm run dev:demo            # to samo, nowe rekordy co 3–6 s
```

Front: http://localhost:5173 · API: http://localhost:4000/api

## Wymagania

Node.js 20.19+ (testowane na 24), npm 10+. Docker do obrazów. Przeglądarka: Chrome/Firefox/Edge (aktualne).

## Konfiguracja

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `VITE_API_URL` | `http://localhost:4000/api` | adres REST (wkompilowany przy buildzie) |
| `VITE_WS_URL` | `http://localhost:4000` | adres socket.io |
| `MOCK_PORT` | `4000` | port mocka |
| `MOCK_EMIT_MIN_MS` / `MOCK_EMIT_MAX_MS` | `15000` / `30000` | odstęp nowych rekordów |
| `MOCK_SEED` | `42` | seed generatora danych |
| `MOCK_CORS_ORIGIN` | `*` | CORS mocka |

Przełączenie na prawdziwy backend: zmiana `VITE_API_URL` i `VITE_WS_URL`.

## Skrypty

| | |
|---|---|
| `npm run lint` | ESLint (`no-console: error`) |
| `npm test` | Vitest: `src/lib/metrics.ts` |
| `npm run typecheck` | TypeScript strict (front + mock) |
| `npm run build` | build produkcyjny do `dist/` |
| `npm run seed` | zrzut danych mocka do `mock-server/data/seed.json` |

## Docker

```bash
docker build -t investwatch-frontend --build-arg VITE_API_URL=http://localhost:4000/api --build-arg VITE_WS_URL=http://localhost:4000 .
docker build -f mock-server/Dockerfile -t investwatch-mock .
docker run -p 8080:8080 investwatch-frontend
docker run -p 4000:4000 investwatch-mock
```

## Struktura

```
src/api         types.ts (kontrakt), client.ts, hooks.ts (TanStack Query), socket.ts
src/components  komponenty prezentacyjne (dane tylko przez props)
src/pages       ekrany; pobierają dane przez hooki z api/
src/lib         metrics.ts (+ testy), labels.ts (polskie nazwy), format.ts, url.ts (filtry w URL)
src/app         router (HashRouter), layout, alerty real-time
mock-server     server.ts, seed.ts, content.ts (fikcyjne treści), scoring.ts, graph.ts, rules.ts
```

## Założenia kontraktu API (do implementacji w backendzie)

Ponad tabelę z `docs/frontend-agent.md` §4:

- Typy odpowiedzi są w `src/api/types.ts` (`Page<T>`, `StatsOverview`, `Timeseries`, `RuleDef`, `CampaignListItem`, `CampaignDetail`, `IndicatorFindings`, `ThresholdsPreview`).
- Listy: `{ items, total, page, pageSize }`. Tablice w query jako `platform[]=a&platform[]=b` (mock przyjmuje też `platform=a&platform=b`).
- `GET /findings`: dodatkowo `scam=1` (scam p ≥ próg `scam.p`) i `campaignId`. `sort=pole:asc|desc`, pola: `fetchedAt`, `publishedAt`, `riskScore`, `scam`, `riskLevel`, `status`.
- `PATCH /findings/status` – zmiana zbiorcza `{ ids, status, comment? }` → `{ items: Finding[] }` (akcja na zaznaczonych i „oznacz kampanię jako scam”).
- `POST /thresholds/preview` `{ values }` → liczba rekordów per poziom ryzyka z ostatnich 30 dni przy obecnych i proponowanych progach.
- `PUT /thresholds` przyjmuje `{ values }`; serwer nadaje `version` i `updatedAt`.
- Klucze progów: `flags.<FlagKey>`, `contentType.<ContentType>`, `risk.MEDIUM|HIGH|CRITICAL` (próg na `riskScore`), `scam.p`. Eval-set ma te same klucze; dla `risk.*` prawdopodobieństwem jest `riskScore`.
- `GET /stats/timeseries`: `{ bucket, groupBy, keys, points: [{ date, counts }] }`. Incydent = rekord w module 1–3 albo scam p ≥ próg. Przy `groupBy=module` klucze `1`, `2`, `3`, `scam`.
- `GET /stats/overview`: „zweryfikowane” = CONFIRMED + DISMISSED + ESCALATED.
- `GET /campaigns` zwraca `trend` (liczba nowych członków per dzień w zakresie dat). `GET /campaigns/:id` → `{ campaign, graph, members }`.
- Węzły grafu: rekord = id rekordu, wskaźnik = `typ:wartość`, agregat = `agg:typ` (powyżej 300 węzłów).
- `RuleDef` ma pole `module` (`null` dla 18 reguł, `1`/`3` dla `M1_PROMO`, `M3_ADVISORY`).
- Raport CSV: UTF-8 z BOM, separator `;` (otwiera się poprawnie w Excelu PL).
- `Finding` nie ma listy podejrzanych domen. Front oznacza link jako podejrzany, gdy rekord ma sygnał `IMPERSONATION`, `CERT_LIST_DOMAIN` lub `KNF_WARNING_LIST`, a domena linku jest wśród wskaźników rekordu. Lepiej dodać w backendzie `suspicious: boolean` per link.
- Kolejność zdarzeń socketu dla jednego rekordu: `finding:new` → `campaign:new_member` → `finding:high_risk`. Front pokazuje jeden toast na rekord (alert kampanii ma pierwszeństwo).

## Bezpieczeństwo zależności

Wersje przypięte (`save-exact`), bez CDN, fonty systemowe.

`npm audit` (21.11.2026): **found 0 vulnerabilities**.
