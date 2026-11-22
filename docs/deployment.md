# InvestWatch – Docker i CI/CD

## Uruchomienie

```bash
docker compose up -d --build
```

Aplikacja: http://localhost:8080 · API AI: http://localhost:8000/docs · konsola MinIO: http://127.0.0.1:9001

Komenda buduje ze źródeł i uruchamia frontend, API, `ai-service` na CPU, Postgres i MinIO. Obrazy nie są publikowane w żadnym rejestrze.
Dane logowania baz mają domyślne wartości deweloperskie (`.env.example`); poza komputerem deweloperskim ustaw własne w `.env`.

### Dane (Postgres + MinIO)

```text
data/export, data/monitor, rejestr KNF ── db-init ──> Postgres  <── api (odczyt, statusy, progi; co 5 s nowe wyniki)
rekordy bez oceny ── loader (w tle) ── ai-service /ingest ──> Postgres
data/media, data/monitor/screens ── minio-init ──> MinIO  <── api /api/media, /api/screens
scrape-worker (przycisk „Zbieranie danych”) ──> Postgres
```

- `minio-init` (jednorazowy): buckety `media` i `screens`, kopia plików z `data/`.
- `db-init` (jednorazowy, kilka sekund, `db/load.py --stage init`): migracje `db/migrations/*.sql`, rejestr KNF, podmioty, rekordy, monitor stron, media. `api` startuje zaraz po nim.
- `loader` (w tle, `db/load.py --stage score`): ocena rekordów bez wyniku w `ai-service`; statusy analityków zostają. API co 5 s dociąga nowe wyniki z bazy, wysyła je przez socket (`finding:new`, `finding:high_risk`) i pokazuje postęp (`GET /api/load`, zdarzenie `load:progress`).
  Z LLM (`LLM_BACKEND=groq`) ocenia najwyżej `LOADER_LLM_LIMIT` rekordów na przebieg (domyślnie 100: najpierw rekordy powiązane z 5 podmiotami, po równo ze źródeł); rekordy bez oceny LLM (limit 429) czekają na kolejny przebieg. Następna porcja: `docker compose run --rm loader` (bez restartu API).
- API (`api/`) nie ma trybu bez bazy: czyta tylko Postgres i MinIO. Rekordy oznaczone `mock` (atrapy monitora) nie są ładowane.

```bash
docker compose run --rm db-init                             # ponowne wczytanie po nowych plikach w data/
docker compose run --rm loader                              # kolejna porcja ocen
docker compose exec postgres psql -U investwatch investwatch  # podgląd bazy
docker compose down -v                                      # czysty stan (usuwa bazę i pliki MinIO)
```

## Obrazy

| Obraz | Kod | Uwagi |
|---|---|---|
| `uknf-frontend` | `frontend/` | nginx, proxy `/api` i `/socket.io` |
| `uknf-api` | `api/` | backend: REST + socket.io, Postgres, MinIO |
| `uknf-loader` | `db/` | jednorazowe ładowanie `data/` do Postgresa |
| `uknf-ai-service` | `ml/` | CPU |
| `uknf-ai-service-gpu` | `ml/` | CUDA, tylko przez `compose.gpu.yaml` |
| `uknf-collector` | `scrapers/`, `adapters/`, `preprocessing/`, `db/` | zadania jednorazowe (profil `jobs`), `scrape-worker` |
| `pgvector/pgvector:pg16` | `db/migrations/` | Postgres |
| `bitnamilegacy/minio` | — | MinIO (oficjalne obrazy `minio/minio` nie są już publikowane) |

## Środowiska

| | dev lokalny | dev | prod |
|---|---|---|---|
| Uruchomienie | `compose.yaml` + `compose.dev.yaml` | `bash deploy/verify.sh dev` | `bash deploy/verify.sh prod` |
| Ustawienia | `compose.dev.yaml` | `deploy/dev.env` | `deploy/prod.env` |
| Front | `localhost:5173`, hot reload | `localhost:8081` | `localhost:8080` |
| ai-service | `localhost:8000`, baseline | `localhost:8001`, baseline | `localhost:8000`, model po przejściu bramki jakości |

`deploy/verify.sh` stawia stack, sprawdza Postgres, MinIO, loader, frontend, API (rekordy i podmiot z bazy, grafikę z MinIO), socket.io i analizę AI, a na końcu usuwa kontenery.

## Development

```bash
# aplikacja z hot reloadem
docker compose -f compose.yaml -f compose.dev.yaml up --build

# lista kolektorów
docker compose -f compose.yaml -f compose.dev.yaml run --rm --build collector

# uruchomienie kolektora; wyniki trafiają do scrapers/poc/results/
docker compose -f compose.yaml -f compose.dev.yaml run --rm collector youtube_posts forex

# GPU (wymaga NVIDIA Container Toolkit)
docker compose -f compose.yaml -f compose.gpu.yaml up -d --build
```

Klucze API są w opcjonalnym `.env`, a sesje Playwright w `.secrets/` (tylko do odczytu). Żadne z nich nie trafia do obrazu.
`python -m login` otwiera widoczne okno Chrome, więc uruchamiaj je na hoście, nie w kontenerze.

Model włącza się przy co najmniej 500 dokumentach treningowych i przykładach scamu w walidacji; inaczej działa baseline. Pliki modelu kopiuje się do `models/`.

### Szybki build (tylko API LLM)

Bez torcha, modeli lokalnych i kolektorów z Chrome. Wymaga `GROQ_API_KEY` w `.env`.

```bash
docker compose -f compose.yaml -f compose.api.yaml up -d --build
# z przyciskiem zbierania danych (dodatkowy obraz ok. 4 GB):
docker compose -f compose.yaml -f compose.api.yaml --profile scraping up -d --build
```

## Pipeline

```text
CI + Security -> build i skan obrazów -> deploy dev -> deploy prod
```

- **CI:** lint, typecheck, testy, build, smoke test API i kolektora.
- **Security:** gitleaks (sekrety), CodeQL (SAST), `npm audit`, `pip-audit`, Snyk (wymaga sekretu `SNYK_TOKEN`). Uruchamiany też w PR i co tydzień.
- **Obrazy:** Grype blokuje podatności HIGH/CRITICAL z dostępną poprawką.
- **Deploy dev / prod:** wdrożenie weryfikacyjne na runnerze GitHub Actions przez `deploy/verify.sh`. Projekt nie ma serwera, więc nic nie zostaje uruchomione po zakończeniu joba.

Zaakceptowane wyjątki z uzasadnieniem: `.security/pip-audit-ignore.txt` i `.grype.yaml`.
