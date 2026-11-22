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
data/export, data/monitor, rejestr KNF ── loader ──> Postgres  <── api (odczyt, statusy, progi)
                                  │          └─> ai-service /ingest
data/media, data/monitor/screens ── minio-init ──> MinIO  <── api /api/media, /api/screens
scrape-worker (przycisk „Zbieranie danych”) ──> Postgres
```

- `minio-init` (jednorazowy): buckety `media` i `screens`, kopia plików z `data/`.
- `loader` (jednorazowy, `db/load.py`): migracje `db/migrations/*.sql`, rejestr KNF, podmioty, rekordy i wyniki `ai-service`. Przy każdym `up` analizuje tylko nowe adresy, statusy analityków zostają. `api` startuje po jego zakończeniu.
  Z LLM (`LLM_BACKEND=groq`) ocenia najwyżej `LOADER_LLM_LIMIT` rekordów na przebieg (domyślnie 100, po równo ze źródeł); rekordy bez oceny LLM (limit 429) czekają na kolejny przebieg. Następna porcja: `docker compose run --rm loader`, potem `docker compose restart api`.
- `DATA_MODE=mock` uruchamia API bez bazy (generator w pamięci, podmioty z `frontend/mock-server/entities.snapshot.json`).

```bash
docker compose run --rm loader                              # ponowne ładowanie po nowych plikach w data/
docker compose exec postgres psql -U investwatch investwatch  # podgląd bazy
docker compose down -v                                      # czysty stan (usuwa bazę i pliki MinIO)
```

## Obrazy

| Obraz | Kod | Uwagi |
|---|---|---|
| `uknf-frontend` | `frontend/` | nginx, proxy `/api` i `/socket.io` |
| `uknf-mock-api` | `frontend/mock-server/` | kontrakt API backendu |
| `uknf-ai-service` | `ml/` | CPU |
| `uknf-ai-service-gpu` | `ml/` | CUDA, tylko przez `compose.gpu.yaml` |
| `uknf-collector` | `scrapers/`, `adapters/`, `preprocessing/`, `db/` | zadania jednorazowe (profil `jobs`), `scrape-worker`, `loader` |
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

## Pipeline

```text
CI + Security -> build i skan obrazów -> deploy dev -> deploy prod
```

- **CI:** lint, typecheck, testy, build, smoke test API i kolektora.
- **Security:** gitleaks (sekrety), CodeQL (SAST), `npm audit`, `pip-audit`, Snyk (wymaga sekretu `SNYK_TOKEN`). Uruchamiany też w PR i co tydzień.
- **Obrazy:** Grype blokuje podatności HIGH/CRITICAL z dostępną poprawką.
- **Deploy dev / prod:** wdrożenie weryfikacyjne na runnerze GitHub Actions przez `deploy/verify.sh`. Projekt nie ma serwera, więc nic nie zostaje uruchomione po zakończeniu joba.

Zaakceptowane wyjątki z uzasadnieniem: `.security/pip-audit-ignore.txt` i `.grype.yaml`.
