# InvestWatch

System monitoringu treści inwestycyjnych dla UKNF. Zbiera reklamy i posty z sieci, ocenia je i wskazuje analitykowi materiały do weryfikacji w trzech modułach:

- **M1:** reklama firmy inwestycyjnej przez osobę trzecią lub finfluencera, z naruszeniami.
- **M2:** materiał marketingowy samej firmy z niedostateczną informacją o ryzyku (18 reguł, art. 44 rozp. 2017/565).
- **M3:** nieuprawnione namawianie do inwestowania i usługi doradcze bez zezwolenia.

Wynik to wskazówka dla analityka, a nie rozstrzygnięcie prawne.

## Szybki start

Wymagany Docker z Compose.

**Najszybciej: LLM przez API, bez torcha i Chrome** (około minuty):

```bash
docker compose -f compose.yaml -f compose.api.yaml up -d --build
```

**Z przyciskiem „Zbieranie danych”** (dodatkowy obraz około 4 GB):

```bash
docker compose -f compose.yaml -f compose.api.yaml --profile scraping up -d --build
```

**W pełni lokalnie, z Bielikiem na GPU** (wymaga NVIDIA Container Toolkit, pobiera model około 8 GB). W `.env` ustaw `LLM_BACKEND=ollama` i usuń `LLM_MODEL`:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml --profile local-llm up -d --build
```

Aplikacja: <http://localhost:8080>. Dane trzyma Postgres (rekordy, oceny, statusy, progi, podmioty) i MinIO (grafiki, zrzuty stron); przy każdym `up` jednorazowa usługa `loader` ładuje do nich `data/` i ocenia nowe rekordy w ai-service.

### Konfiguracja (`.env` w katalogu głównym)

```env
LLM_BACKEND=groq          # parametr builda: groq (domyślnie) | ollama | none; po zmianie uruchom z --build
LLM_MODEL=openai/gpt-oss-120b
GROQ_API_KEY=
YOUTUBE_API_KEY=          # opcjonalny
```

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `FRONTEND_PORT` | `8080` | port aplikacji |
| `AI_PORT` | `8000` | port ai-service (tylko localhost) |
| `OLLAMA_URL` | `http://ollama:11434` | Ollama na komputerze: `http://host.docker.internal:11434` |
| `MODELS_PATH` | `./ml/models` | klasyfikator z treningu |
| `LOADER_LLM_LIMIT` | `100` | ile rekordów loader ocenia przez LLM w jednym przebiegu |
| `POSTGRES_PASSWORD`, `MINIO_ROOT_PASSWORD` | wartości deweloperskie | zmień poza komputerem deweloperskim (`.env.example`) |

`.env`, `ml/data/` i `ml/models/` nie są w repozytorium. Kolejna porcja ocen LLM (reszta czeka w bazie):

```bash
docker compose run --rm loader
```

### Wymagania sprzętowe

| Tryb | Dysk | GPU |
|---|---|---|
| API | około 1 GB | nie |
| API + zbieranie danych | około 6 GB | nie |
| Lokalny Bielik | około 20 GB | NVIDIA, testowane na 12 GB VRAM |

## Usługi

| Usługa | Technologia | Rola |
|---|---|---|
| `frontend` | React, Mantine, nginx | panel analityka, kalibracja, graf powiązań |
| `api` | Node.js, Express, Socket.IO | API aplikacji, statusy, progi, sterowanie zbieraniem |
| `ai-service` | Python, FastAPI | język, rejestr KNF, reguły, LLM, kampanie |
| `scrape-worker` | Python, Playwright, RapidOCR | przebiegi kolektorów, ręczne i z harmonogramu |
| `ollama` | Ollama | lokalny LLM (profil `local-llm`) |

Przebieg: kolektory → pomijanie znanych adresów → filtr języka → LLM → rekord w aplikacji. Meta jest uruchamiana tylko ręcznie, bo kolektor działa przez stronę WWW, a jej regulamin dopuszcza automatyzację wyłącznie przez API.

Więcej: [wdrożenie](docs/deployment.md), [kontrakt API](contracts/app_api.md), [scrapowanie](docs/scraping-guide.md).

## Klasyfikacja

Prompt jest w [`classifier_prompt.md`](ml/src/investwatch_ml/classifier_prompt.md), a instrukcja dla Claude w [`.claude/skills/investwatch-ad-review`](.claude/skills/investwatch-ad-review/SKILL.md). Moduły się wykluczają. LLM zwraca rozkład M1/M2/M3/NONE, pewność, uzasadnienie i cytaty. Rejestr KNF i słowa kluczowe ze stemmingiem trafiają do modelu jako sygnały. Reguły 4–8 (czcionka, kontrast, ukrycie ostrzeżenia) liczą się z pomiarów strony lub grafiki, bez LLM.

Zgodność z ręczną oceną 42 rekordów:

| Model | Trafność |
|---|---|
| gpt-oss-120b (Groq) | 36/42 (86%) |
| gpt-oss-20b (Groq) | 30/42 (71%) |
| Bielik 11B (lokalnie) | 29/42 (69%) |

Zbiór jest mały, a część ocen poprawiono po przejrzeniu rozbieżności z modelem, więc wyniki są optymistyczne.

## Dataset

Nie ma publicznego polskiego zbioru z etykietami M1/M2/M3, więc zbudowaliśmy własny. Stan na 22.11.2026.

### Dane realne (z kolektorów)

| Źródło | Rekordy | Gdzie |
|---|---|---|
| Microsoft/Bing Ad Library | 1322 | `ml/data/raw/scraper_live/*bing*/` |
| Google Ads Transparency Center (tekst obrazów z OCR) | 440 | `data/export/google_ads/`, `ml/data/raw/scraper_live/zip1122_google_ads/` |
| Meta Ad Library | 802 | `data/export/meta_ads/`, `ml/data/raw/scraper_live/*meta*/` |
| YouTube (opis + transkrypcja faster-whisper) | 764 + 352 kandydatów M3 | `ml/data/pool/youtube.jsonl`, `ml/data/pool/m3_youtube.jsonl` |
| TikTok (z transkrypcją) | 49 | `data/export/tiktok/`, `ml/data/raw/scraper_live/zip1122_tiktok/` |
| Strony firm inwestycyjnych | 11 | `ml/data/raw/scraper_live/zip1122_firm_web/` |
| Reddit (polskie subreddity finansowe) | 5343 | `ml/data/pool/reddit.jsonl` |
| Archiwalne strony oszustów z listy CERT PL (Wayback Machine) | 53 | `ml/data/pool/cert_wayback.jsonl` |

Format rekordu (`source`, `source_url`, `author`, `published_at`, `fetched_at`, `query_keywords`, `text`) opisuje [data/export/README.md](data/export/README.md). Liczby obejmują wszystkie pobrane rekordy, także niepolskie. Aplikacja pokazuje wyłącznie polskie rekordy z paczek zip i z przebiegów zbierania.

### Dane uzupełniające (tylko trening, nigdy test)

Rzadkie klasy (scam, rekomendacje, doradztwo) uzupełniamy danymi przetłumaczonymi na polski lokalnym modelem NLLB i ręcznie napisanymi przypadkami. Rekordy mają `meta.synthetic = true`.

| Zbiór | Rekordy | Licencja |
|---|---|---|
| MultiAgentFraudBench (posty oszustów) | 2200 | CC BY-NC-SA 4.0 |
| VideoConviction (rekomendacje finfluencerów) | 215 | CC BY-NC 4.0 |
| Fraud-R1 | 300 | nie podano |
| Trudne przypadki napisane ręcznie | 100 | własne |

### Etykiety klasyfikatora

- **Nauczyciel:** lokalny Bielik 11B v3.1 (Ollama) oznaczył 4329 dokumentów: temat, typ treści, instrumenty, 23 flagi z dowodem w tekście i scam. Gemini (225), Groq (74) i OpenRouter (29) służyły do porównania.
- **Rozkład tematów:** inwestycje 2322, inne finansowe 995, niefinansowe 1012.
- **Scam:** 125 przykładów realnych i 1136 z danych uzupełniających.
- **Weryfikacja przez człowieka:** 42 rekordy, użyte do porównania modeli LLM.

Klasyfikator v2 (`ml/models_candidate/v2/metrics.json`), test na 548 realnych dokumentach: wykrywanie scamu AP 0,815 wobec 0,18 dla reguł słownikowych, temat makro-F1 0,77 wobec 0,52. W `ml/models/` działa wcześniejszy kandydat (504 dokumenty testowe, scam AP 0,75). Metryki mierzą zgodność z etykietami nauczyciela, nie prawdę.

### Odtworzenie

Katalog `ml/data/` nie jest w gicie (rozmiar i licencje). Odtwarzają go skrypty w `ml/scripts/`:

1. `collect_*.py`, `ingest_scraper.py`: zbieranie i import eksportu scrapera.
2. `translate_local.py`: tłumaczenie danych uzupełniających (GPU).
3. `build_edge_cases.py`: trudne przypadki.
4. `label_teacher.py`: etykietowanie modelem-nauczycielem.
5. `train_heads.py`: trening i metryki.
6. `classify_groq.py`, `merge_llm.py`: ocena modułów przez LLM i wstawienie wyników do aplikacji.

## Ograniczenia

- **Tryb Groq wysyła treści do zewnętrznego API.** Wersja on-premise musi używać `LLM_BACKEND=ollama`.
- `build_findings.py` nie filtruje języka. Po przebudowie danych uruchom `filter_polish_zips.py` i `keep_zip_only.py`.
- Licencje niekomercyjne (MAFB, VideoConviction) i brak licencji Fraud-R1: przed wdrożeniem produkcyjnym te zbiory trzeba usunąć albo wyjaśnić.
- Kolektor Mety działa przez stronę WWW. Wersja produkcyjna powinna używać oficjalnego Ad Library API.
- Rekordy zawierają nazwy autorów i reklamodawców, więc surowych danych nie publikujemy.
- OCR i transkrypcje mają błędy w polskich znakach i nazwach własnych.
- Treści z listy CERT pochodzą z kopii archiwalnych. Nie odwiedzamy żywych domen oszustów.
