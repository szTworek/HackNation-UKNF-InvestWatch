# Paczka do uruchomienia InvestWatch z prawdziwymi danymi

Pliki są poza gitem (model i dane ze scrapera). Rozpakuj ten zip w katalogu głównym repo `HackNation-UKNF-InvestWatch`,
tak żeby powstały `ml/models/` i `frontend/mock-server/data/findings.real.json`.

```bash
# w .env w katalogu głównym repo (plik jest poza gitem):
DATA_MODE=real
DEMO_REPLAY=1        # 0 = bez symulowanego napływu rekordów

docker compose up -d --build
```

- Front: http://localhost:8080, ai-service: http://localhost:8000/health (`modelVersion` zaczyna się od `heads-`).
- Pierwszy start ai-service pobiera model `BAAI/bge-m3` (~2,3 GB) z Hugging Face, więc potrzebuje internetu.
  Dla GPU: `docker compose -f compose.yaml -f compose.gpu.yaml up -d --build`.
- Przeliczenie danych po zmianie modelu: `python ml/scripts/build_findings.py`, potem restart usługi `api`.
- Dane zawierają nazwy autorów i reklamodawców: nie publikuj ich ani nie commituj.
