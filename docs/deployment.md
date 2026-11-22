# InvestWatch – Docker i CI/CD

## Uruchomienie

```bash
docker compose up -d --build
```

Aplikacja: http://localhost:8080 · API AI: http://localhost:8000/docs

Komenda buduje ze źródeł i uruchamia frontend, API (mock) i `ai-service` na CPU. Obrazy nie są publikowane w żadnym rejestrze.

## Obrazy

| Obraz | Kod | Uwagi |
|---|---|---|
| `uknf-frontend` | `frontend/` | nginx, proxy `/api` i `/socket.io` |
| `uknf-mock-api` | `frontend/mock-server/` | kontrakt API backendu |
| `uknf-ai-service` | `ml/` | CPU |
| `uknf-ai-service-gpu` | `ml/` | CUDA, tylko przez `compose.gpu.yaml` |
| `uknf-collector` | `scrapers/`, `adapters/`, `preprocessing/` | zadania jednorazowe (profil `jobs`) |

## Środowiska

| | dev lokalny | dev | prod |
|---|---|---|---|
| Uruchomienie | `compose.yaml` + `compose.dev.yaml` | `bash deploy/verify.sh dev` | `bash deploy/verify.sh prod` |
| Ustawienia | `compose.dev.yaml` | `deploy/dev.env` | `deploy/prod.env` |
| Front | `localhost:5173`, hot reload | `localhost:8081` | `localhost:8080` |
| ai-service | `localhost:8000`, baseline | `localhost:8001`, baseline | `localhost:8000`, model po przejściu bramki jakości |

`deploy/verify.sh` stawia stack, sprawdza frontend, API, socket.io i analizę AI, a na końcu usuwa kontenery.

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
