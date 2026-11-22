# InvestWatch – integracja backend / scraper ↔ AI ↔ frontend

Dokument dla osoby robiącej **scraping + backend (Node.js)**. Opisuje, jak łączymy się z serwisem AI (Python)
i z frontendem. Kontrakty z tego dokumentu są wiążące. Zmiany najpierw tutaj, potem w kodzie.

Powiązane pliki:
- `docs/plan-model.md` – co robi model,
- `docs/frontend-agent.md` – typy (sekcja 3) i REST/socket API dla frontu (sekcja 4).
  Frontend powstaje na mock serwerze z tym kontraktem. **Backend ma go zaimplementować 1:1**, a front tylko przełączy `VITE_API_URL`.

---

## 1. Architektura

```
            ┌──────────────┐  repeatable jobs   ┌──────────────┐
            │  scheduler   │ ─────────────────▶ │  scrape queue│ (BullMQ/Redis)
            └──────────────┘                    └──────┬───────┘
                                                       ▼
┌────────────┐   items (SQL) + raw (MinIO)     ┌──────────────┐
│  Postgres  │ ◀────────────────────────────── │ scraper (Node)│ Playwright/httpx-like, UA+proxy rotation
│ + pgvector │                                 └──────┬───────┘
│            │                                        │ item_id
│            │                                 ┌──────▼───────┐
│            │                                 │ analyze queue│
│            │                                 └──────┬───────┘
│            │      findings (SQL)             ┌──────▼───────┐  POST /analyze   ┌──────────────┐
│            │ ◀────────────────────────────── │ backend worker│ ───────────────▶ │  ai-service  │ FastAPI, GPU
│            │                                 └──────┬───────┘ ◀─────────────── │  (Python)    │
│            │ ◀── graf: embeddingi, wskaźniki, krawędzie, kampanie (zapisuje AI) │              │──▶ Ollama (Bielik)
└─────┬──────┘                                        │ socket.io events        └──────────────┘
      │  REST                                  ┌──────▼───────┐
      └──────────────────────────────────────▶ │ backend API  │ ◀──── frontend (React)
                                               └──────────────┘
```

Podział odpowiedzialności:

| Kto | Co |
|---|---|
| **Backend (Ty)** | scraper, kolejki, scheduler, tabele `sources/scrape_runs/items/findings/finding_history/thresholds`, REST + socket dla frontu, docker-compose |
| **AI (ja)** | `ai-service`: klasyfikacja, scoring reguł, scam, embeddingi, graf i kampanie (tabele grafu), rejestr KNF / listy ostrzeżeń (tabele referencyjne), eval-set do kalibracji |
| **Frontend (agent)** | `frontend/`, na razie na mocku |

## 2. Co potrzebuję od Ciebie NAJPIERW

1. **Próbka 50–200 realnych rekordów** ze scrapera jako JSONL w formacie z sekcji 3, nawet z jednego źródła.
   Z tego robię ręcznie oznaczony zbiór testowy, bez którego nie pokażemy metryk. Wrzuć do `ml/data/incoming/`.
2. **`outboundLinks` i `redirectChains`** (sekcja 3). To najsilniejszy sygnał scamu (podszywanie się pod marki, domeny z list CERT/KNF) i podstawa grafu kampanii.
3. Dla wideo: napisy lub transkrypcja, jeśli platforma je daje. Jeśli nie ma napisów, odkładasz audio do MinIO, a AI zrobi transkrypcję (faster-whisper, opcjonalnie).

## 3. Kontrakt: rekord ze scrapera (`ScrapedItem`)

JSON, **camelCase** we wszystkich kontraktach HTTP.

```jsonc
{
  "id": "uuid",                        // nadaje backend
  "platform": "facebook|instagram|tiktok|youtube|x|web|other",
  "kind": "post|transcript|comment|page",
  "url": "https://...",                // dokładna lokalizacja (wymóg M1/M3)
  "canonicalUrl": "https://...",
  "author": { "handle": "@x", "displayName": "X", "profileUrl": "...", "followers": 12000, "verified": false },
  "title": "...",                      // tytuł filmu / strony
  "text": "czysty tekst bez HTML",     // post, opis + transkrypcja, treść strony
  "transcriptSegments": [ { "startS": 0.0, "endS": 4.2, "text": "..." } ],   // opcjonalnie, dla wideo
  "hashtags": ["#reklama"],
  "outboundLinks": ["https://bit.ly/abc"],
  "redirectChains": [ ["https://bit.ly/abc", "https://track.example", "https://landing.example/pl"] ],
  "isSponsored": true,                 // jeśli platforma oznacza post jako płatny / partnerstwo
  "media": [ { "type": "image|video|audio", "objectKey": "minio/key", "url": "..." } ],
  "rawObjectKey": "minio/raw/....html",
  "publishedAt": "ISO8601",
  "fetchedAt": "ISO8601",
  "sourceId": "uuid",
  "runId": "uuid"
}
```

Zasady:
- `text` po Twojej stronie: bez HTML, z normalizacją białych znaków. Emoji i hashtagi zostają, bo to cenne sygnały.
- Deduplikacja dokładna po Twojej stronie (`url` unique + `textHash` = sha256 znormalizowanego tekstu).
  Near-duplicates wykrywa AI w grafie.
- Landing pages odwiedzasz w kroku wzbogacenia (sekcja 3a), tylko dla rekordów, które przeszły triage.

## 3a. Wzbogacenie przed klasyfikacją (enrichment)

Pipeline jest dwuetapowy (szczegóły: `docs/plan-model.md` §1a):

1. **Triage:** `POST /triage` na samym tekście. Szybkie, dla każdego rekordu.
2. **Wzbogacenie**, tylko gdy `enrich: true`:
   - **Strona docelowa (Ty, Playwright):** odwiedź `outboundLinks` (maks. 3 na rekord) i zapisz `LandingPage`.
     **Bezpieczeństwo:** osobny kontener, brak ciasteczek i kont, **nie wypełniamy ani nie wysyłamy formularzy**,
     blokada pobierania plików, timeout 20 s, rotacja UA i proxy (wymóg specyfikacji).
   - **Media (Ty pobierasz, AI analizuje):** wideo lub audio do MinIO (yt-dlp dla YT/TikTok, jeśli się da),
     potem `POST /enrich/media`. Wynik: ASR, klatki + OCR, score syntetycznego głosu.
3. **Klasyfikacja końcowa:** `POST /analyze` z rekordem, jego `landingPages` i `mediaAnalysis`.

```jsonc
// LandingPage – zapisuje scraper
{
  "requestedUrl": "https://bit.ly/abc", "finalUrl": "https://landing.example/pl/artykul",
  "redirectChain": ["https://bit.ly/abc", "https://track.example/?c=1", "https://landing.example/pl/artykul"],
  "httpStatus": 200, "title": "...", "text": "czysty tekst strony",
  "screenshots": { "desktop": "minio/key.png", "mobile": "minio/key_m.png" },   // viewport 1366x768 i 390x844
  "forms": [ { "fields": ["name", "phone", "email"], "submitText": "Zarejestruj się" } ],
  "textBlocks": [                                    // do reguł 4/5/7/8 – zrzut z DOM, per viewport
    { "viewport": "desktop", "text": "...", "fontSizePx": 11, "fontWeight": 400,
      "color": "rgb(153,153,153)", "background": "rgb(255,255,255)",
      "bbox": [x, y, w, h], "visible": true, "inViewportOnLoad": false, "insideCollapsed": false }
  ],
  "fetchedAt": "ISO8601"
}
```

`textBlocks` łatwo wyciągnąć w Playwright przez `page.evaluate` po wszystkich elementach z bezpośrednim tekstem:
`getComputedStyle` (font-size, color, efektywne tło po przodkach), `getBoundingClientRect`, widoczność
oraz `details:not([open])`/`display:none` u przodków. Limit ok. 400 bloków na viewport.

```jsonc
// MediaAnalysis – zwraca ai-service z POST /enrich/media { itemId, objectKey }
{
  "asr": { "used": true, "text": "...", "segments": [ { "startS": 0, "endS": 4.2, "text": "..." } ] },
  "keyframes": [ { "t": 12.0, "objectKey": "minio/frames/..jpg", "ocrText": "ZARABIAJ 30 000 ZŁ",
                   "boxes": [ { "text": "...", "bbox": [x, y, w, h] } ] } ],
  "syntheticVoice": { "score": 0.81, "model": "...", "segments": [ { "startS": 0, "endS": 10, "score": 0.9 } ],
                      "experimental": true }
}
```

## 4. Kontrakt: ai-service (FastAPI, port 8000)

| Metoda | Ścieżka | Opis |
|---|---|---|
| GET | `/health` | `{ status, modelVersion, gpu }` |
| POST | `/triage` | `{ items: ScrapedItem[] }` → `{ results: [{ itemId, pInvestment, pScam, enrich: boolean }] }` – szybkie, sam tekst |
| POST | `/enrich/media` | `{ itemId, objectKey }` → `MediaAnalysis` (ASR + klatki/OCR + syntetyczny głos), wolne – kolejka |
| POST | `/analyze` | `{ items: (ScrapedItem & { landingPages?, mediaAnalysis? })[] }` (batch ≤ 32) → `{ results: AnalysisResult[] }` |
| POST | `/rescore` | `{ thresholds: Thresholds, itemIds?: string[] }` → `{ results: Rescore[] }`, przeliczenie reguł i ryzyka po zmianie progów (bez modelu, szybkie) |
| GET | `/thresholds/default` | domyślne progi z ewaluacji |
| GET | `/calibration/eval-set` | `EvalItem[]` dla panelu kalibracji (backend proxy'uje do frontu) |
| POST | `/explain` | `{ itemId }` → `{ explanation }`, opis po polsku z Bielika, tylko dla HIGH/CRITICAL, wolne (async) |
| POST | `/transcribe` | `{ objectKey }` → `{ text, segments }` (opcjonalnie) |

`AnalysisResult` ma **te same pola co `Finding` z `docs/frontend-agent.md` sekcja 3**, z wyjątkiem pól backendowych
(`status`, `history`, metadane itemu). Konkretnie:
`itemId, topic, contentType, instruments, flags, rules, entities, scam, indicators, campaignId, related, modules, riskScore, riskLevel, modelVersion`.

`Rescore` = `{ itemId, rules, modules, riskScore, riskLevel }`.

Efekty uboczne `/analyze`: ai-service sam zapisuje do Postgresa embedding, wskaźniki, krawędzie i przypisanie do kampanii (tabele z sekcji 5b).
Ty zapisujesz `AnalysisResult` do `findings`.

**Stub jest gotowy** (`ml/src/investwatch_ml/api.py`, predykcje z baseline'u słownikowego, prawdziwy scoring reguł):
```
cd ml && uv run uvicorn investwatch_ml.api:app --host 0.0.0.0 --port 8000
```
Dokumentacja OpenAPI: http://localhost:8000/docs. `/rescore` w stubie trzyma predykcje w pamięci procesu.

Pierwotny plan: **do czasu gotowości modelu wystawię stub `/analyze`** (ok. 2h od startu). Ma ten sam kontrakt i losowe, ale spójne wyniki, więc możesz integrować od razu.

## 5. Baza: Postgres 16 + pgvector (`pgvector/pgvector:pg16`)

Migracje to zwykłe pliki SQL w `db/migrations/`, aplikowane przy starcie (np. node-pg-migrate albo init-script w kontenerze).
`001_core.sql` piszesz Ty, `002_ai.sql` piszę ja.

### 5a. Twoje tabele (propozycja)

```sql
create table sources (id uuid primary key, platform text, kind text, target text,   -- handle / URL / fraza
  schedule_cron text, active bool default true, last_run_at timestamptz);
create table scrape_runs (id uuid primary key, source_id uuid references sources, started_at timestamptz,
  finished_at timestamptz, status text, items_found int, error text);
create table items (id uuid primary key, platform text, kind text, url text unique, canonical_url text,
  author jsonb, title text, text text, text_hash text, transcript_segments jsonb, hashtags text[],
  outbound_links text[], redirect_chains jsonb, is_sponsored bool, media jsonb, raw_object_key text,
  published_at timestamptz, fetched_at timestamptz, source_id uuid, run_id uuid);
create table findings (item_id uuid primary key references items, model_version text, analyzed_at timestamptz,
  result jsonb,                         -- pełny AnalysisResult
  modules int[], risk_score real, risk_level text, scam_p real, campaign_id uuid,
  status text default 'NEW', updated_at timestamptz);
create index on findings (risk_level); create index on findings using gin (modules); create index on findings (status);
create index on items (fetched_at);
create table landing_pages (id uuid primary key, item_id uuid references items, requested_url text, final_url text,
  redirect_chain text[], http_status int, title text, text text, screenshots jsonb, forms jsonb, text_blocks jsonb,
  fetched_at timestamptz);
create table media_analysis (item_id uuid primary key references items, asr jsonb, keyframes jsonb,
  synthetic_voice jsonb, analyzed_at timestamptz);
create table finding_history (id bigserial primary key, item_id uuid, at timestamptz, status text, "user" text, comment text);
create table thresholds (id serial primary key, version text, values jsonb, updated_at timestamptz, active bool);
```

### 5b. Tabele AI (piszę ja, Ty tylko czytasz)

```sql
create extension if not exists vector;
create table item_embeddings (item_id uuid primary key, model text, embedding vector(1024));   -- bge-m3
create index on item_embeddings using hnsw (embedding vector_cosine_ops);
create table indicators (id bigserial primary key, type text, value text, norm text, unique (type, norm));
create table item_indicators (item_id uuid, indicator_id bigint, primary key (item_id, indicator_id));
create table edges (src uuid, dst uuid, type text, weight real, detail text, primary key (src, dst, type));
create table campaigns (id uuid primary key, name text, status text, size int, scam_share real, avg_scam real,
  first_seen timestamptz, last_seen timestamptz, top_indicators jsonb);
create table campaign_members (item_id uuid primary key, campaign_id uuid);
-- referencyjne (ładuję skryptem):
create table knf_entities (id bigserial primary key, name text, list_type text, country text, domains text[]);
create table warning_entities (id bigserial primary key, source text, name text, domains text[]);  -- KNF lista ostrzeżeń, CERT
```

Endpointy `/campaigns*`, `/findings/:id/graph`, `/indicators/...` dla frontu robisz zwykłymi SELECT-ami z tych tabel.
Ego-graf to rekurencyjny CTE po `edges` z limitem głębokości 2 i 300 węzłów.

## 6. Przepływy

**Nowy rekord:**
1. scraper zapisuje `items`,
2. `POST /triage`. Nieinwestycyjne idą od razu do `analyze` bez wzbogacenia, reszta do kolejki `enrich`,
3. `enrich`: landing pages (Playwright) i media (`/enrich/media`) równolegle, z timeoutem 2 min.
   Po timeoucie analizujemy to, co jest,
4. kolejka `analyze`: worker zbiera batch do 32 lub czeka 2 s, `POST /analyze` z `landingPages` i `mediaAnalysis`,
5. upsert do `findings`,
6. emituje socket:
   - zawsze `finding:new`,
   - `finding:high_risk`, jeśli `riskLevel ∈ {HIGH, CRITICAL}`,
   - `campaign:new_member`, jeśli `campaignId` jest ustawione, a kampania ma `scam_share ≥ 0.5`.

**Zmiana progów (panel kalibracji):**
1. `PUT /api/thresholds`,
2. zapis nowej wersji,
3. `POST /rescore` (w paczkach),
4. update `findings`,
5. socket `thresholds:updated`.

**Zmiana statusu:**
1. `PATCH /api/findings/:id/status`,
2. `finding_history`,
3. socket `finding:updated`.

Jeśli status to `CONFIRMED` i rekord jest w kampanii, wywołaj `POST /analyze/feedback` (dorobię go), żeby podbić score niezweryfikowanych członków kampanii.

**Scheduler:** repeatable jobs w BullMQ wg `sources.schedule_cron`. Specyfikacja wymaga cron/orchestratora i okresowej aktualizacji raportów M1/M3.

## 7. Docker Compose (docelowo, robisz Ty)

| Serwis | Obraz / build | Port | Uwagi |
|---|---|---|---|
| postgres | `pgvector/pgvector:pg16` | 5432 | volume, migracje z `db/migrations` |
| redis | `redis:7-alpine` | 6379 | BullMQ |
| minio | `minio/minio` | 9000/9001 | raw HTML, screenshoty, audio (opcjonalnie, można zacząć od volume) |
| backend | `./backend` | 3000 | REST + socket.io + worker `analyze` |
| scraper | `./scraper` | – | worker `scrape` |
| ai-service | `./ai-service` | 8000 | GPU (`deploy.resources.reservations.devices: nvidia`), modele w volume |
| ollama | `ollama/ollama` | 11434 | GPU, Bielik do `/explain` |
| frontend | `./frontend` | 8080 | nginx |

`.env.example` w root: `DATABASE_URL`, `REDIS_URL`, `AI_SERVICE_URL`, `MINIO_*`, `PROXY_LIST`, `OLLAMA_URL`.
Żadnych sekretów w repo. Organizator wymaga `npm audit` / Snyk i `pip-audit` oraz pustego `console.log` (używaj loggera, np. pino).

## 8. Struktura repo

```
scraper/  backend/  ai-service/  ml/  frontend/  db/migrations/  docs/  docker-compose.yml  .env.example
```

Osobne foldery i osobne Dockerfile, bez narzędzi monorepo. Organizator wprost prosi o „lekkie serwisy, bez ciężkiego monorepo”.

## 9. Kamienie milowe

| Kiedy | Backend | AI |
|---|---|---|
| teraz | akceptacja kontraktów; **próbka JSONL** | – |
| +2h | Postgres + Redis w compose, `001_core.sql`, scraper → `items` | stub `/analyze` + `002_ai.sql` |
| +5h | kolejka `analyze` → `findings`, socket events | rejestr KNF + listy ostrzeżeń w bazie, `/triage` |
| +7h | kolejka `enrich`: landing pages (Playwright, zrzuty, `textBlocks`), pobieranie mediów | `/enrich/media` (ASR, OCR), reguły 4/5/7/8 |
| +8h | REST dla frontu wg `frontend-agent.md` §4, front przełączony z mocka | prawdziwy model, `/rescore`, eval-set |
| +10h | pełny compose, `npm audit` | graf i kampanie, `/explain` |
| +11h | demo end-to-end: scrape → alert na dashboardzie | metryki do prezentacji |
