# InvestWatch – Docker, CI/CD i wdrożenie

## Co jest budowane

| Obraz | Kod | Kiedy |
|---|---|---|
| `uknf-collector` | `scrapers/`, `adapters/`, `preprocessing/` | zawsze |
| `uknf-frontend`, `uknf-mock-api` | `frontend/` | gdy istnieje `frontend/package.json` |
| `uknf-ai-service` | `ml/` | gdy istnieje `ml/pyproject.toml` |

Serwisy aplikacji (profil `app`) wdrażają się, gdy w repo są i `frontend/`, i `ml/`.
Kolektory (profil `jobs`) to zadania jednorazowe, nie działają stale.

## Środowiska

| | dev lokalny | dev (serwer) | prod (serwer) |
|---|---|---|---|
| Uruchomienie | `compose.yaml` + `compose.dev.yaml` | push na `main` | tag `vX.Y.Z` |
| Obrazy | budowane ze źródeł | GHCR `sha-<commit>` | GHCR `sha-<commit>` |
| Ustawienia | `compose.dev.yaml` | `deploy/dev.env` | `deploy/prod.env` |
| Front | `localhost:5173` | `127.0.0.1:8081` | `127.0.0.1:8080` |
| ai-service | `localhost:8000`, baseline | `127.0.0.1:8001`, baseline | `127.0.0.1:8000`, model |

## Lokalnie

```bash
# lista kolektorów
docker compose -f compose.yaml -f compose.dev.yaml run --rm --build collector

# uruchomienie kolektora; wyniki trafiają do scrapers/poc/results/
docker compose -f compose.yaml -f compose.dev.yaml run --rm collector youtube_posts forex

# transkrypcja
docker compose -f compose.yaml -f compose.dev.yaml run --rm --entrypoint python collector \
  -m youtube_transcripts.transcribe results/youtube_posts.ytdlp/<plik>-docs.json

# aplikacja (gdy są frontend/ i ml/)
docker compose -f compose.yaml -f compose.dev.yaml --profile app up --build
```

Klucze API są w opcjonalnym `.env`, a sesje Playwright w `.secrets/` (tylko do odczytu). Żadne z nich nie trafia do obrazu.
`python -m login` otwiera widoczne okno Chrome, więc uruchamiaj je na hoście, nie w kontenerze.

## Pipeline

- **PR:** obraz kolektora ze smoke testem (importy, Chromium, Chrome), a gdy jest kod aplikacji: lint, typecheck, testy, build, `npm audit`, smoke test API.
- **Push na `main`:** CI, obrazy do GHCR, wdrożenie dev.
- **Tag `vX.Y.Z`:** CI, obrazy do GHCR, wdrożenie prod.

Nieudane wdrożenie przywraca ostatni działający tag (`deploy/deploy.sh`).

## Konfiguracja GitHub

Utwórz środowiska `dev` i `prod` (Settings → Environments). Dla `prod` ustaw *Required reviewers*
oraz ogranicz wdrożenia do tagów `v*`. W każdym środowisku dodaj sekrety:

| Sekret | Wartość |
|---|---|
| `DEPLOY_HOST` | adres serwera |
| `DEPLOY_USER` | użytkownik z dostępem do Dockera |
| `DEPLOY_SSH_KEY` | prywatny klucz SSH przeznaczony tylko do wdrożeń |
| `DEPLOY_KNOWN_HOSTS` | wynik `ssh-keyscan -p <port> <host>`, zweryfikowany z serwerem |

Opcjonalna zmienna `DEPLOY_PORT` (domyślnie 22). Bez sekretów wdrożenie dev jest pomijane z ostrzeżeniem, a prod kończy się błędem.

## Serwer

Wymagany Docker z Compose v2.24+. Stack trafia do `~/investwatch/<env>/`.

```bash
cd ~/investwatch/dev
REGISTRY=ghcr.io/sztworek IMAGE_TAG=main docker compose -p investwatch-dev --env-file dev.env \
  --profile jobs run --rm collector google_ads XTB
```

- **Klucze i sesje:** `~/investwatch/<env>/.env` i `~/investwatch/<env>/.secrets/`.
- **Wyniki kolektorów:** wolumen `investwatch-<env>_collector-results`.
- **Modele:** skopiuj zawartość `ml/models/` do `~/investwatch/<env>/models/`; bez nich działa baseline.
- **GPU:** zainstaluj NVIDIA Container Toolkit i ustaw `USE_GPU=1` w `deploy/<env>.env`.
- **Dostęp publiczny:** porty są na `127.0.0.1`. Postaw przed frontem reverse proxy z TLS.
