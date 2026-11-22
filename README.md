# UKNF
UKNF - #InvestWatch – na straży inwestorów!

## Dataset

Nie ma publicznego polskiego zbioru z etykietami M1/M2/M3, więc zbudowaliśmy własny. Stan na 22.11.2026.

### Dane realne (z kolektorów)

| Źródło | Rekordy | Gdzie |
|---|---|---|
| Microsoft/Bing Ad Library | 1227 | `ml/data/raw/scraper_live/*bing_ads/` |
| Google Ads Transparency Center (PL, tekst obrazów z OCR) | 710 | `data/export/google_ads/`, `ml/data/raw/scraper_live/zip1122_google_ads/` |
| Meta Ad Library | 331 | `data/export/meta_ads/`, `ml/data/raw/scraper_live/*meta_ads/` |
| YouTube (opis + transkrypcja faster-whisper) | 764 + 352 kandydatów M3 | `ml/data/pool/youtube.jsonl`, `ml/data/pool/m3_youtube.jsonl` |
| TikTok (z transkrypcją) | 55 | `data/export/tiktok/`, `ml/data/raw/scraper_live/zip1122_tiktok/` |
| Strony firm inwestycyjnych | 11 | `ml/data/raw/scraper_live/zip1122_firm_web/` |
| Reddit (polskie subreddity finansowe) | 5343 | `ml/data/pool/reddit.jsonl` |
| Archiwalne strony oszustów z listy CERT PL (Wayback Machine) | 53 | `ml/data/pool/cert_wayback.jsonl` |

Format rekordu (`source`, `source_url`, `author`, `published_at`, `fetched_at`, `query_keywords`, `text`) opisuje [data/export/README.md](data/export/README.md).

### Dane uzupełniające (tylko trening, nigdy test)

Rzadkie klasy (scam, rekomendacje, doradztwo) uzupełniamy danymi przetłumaczonymi na polski lokalnym modelem NLLB i ręcznie napisanymi przypadkami. Rekordy mają `meta.synthetic = true`.

| Zbiór | Rekordy | Licencja |
|---|---|---|
| MultiAgentFraudBench (posty oszustów) | 2200 | CC BY-NC-SA 4.0 |
| VideoConviction (rekomendacje finfluencerów) | 685 | CC BY-NC 4.0 |
| Fraud-R1 | 300 | nie podano |
| Trudne przypadki napisane ręcznie | 100 | własne |

### Etykiety

- **Nauczyciel:** lokalny Bielik 11B v3.1 (Ollama) oznaczył 4329 dokumentów: temat, typ treści, instrumenty, 23 flagi z dowodem w tekście i scam. Gemini (225), Groq (74) i OpenRouter (29) służyły do porównania. Zewnętrzne API są używane tylko przy budowie danych, aplikacja ich nie woła.
- **Rozkład tematów:** inwestycje 2322, inne finansowe 995, niefinansowe 1012.
- **Scam:** 125 przykładów realnych i 1136 z danych uzupełniających.
- **Weryfikacja przez człowieka:** brak. Metryki modelu mierzą zgodność z etykietami nauczyciela, nie prawdę.

### Podział i wyniki

Zbiór testowy zawiera wyłącznie dane realne (548 dokumentów). Model v2 (`ml/models_candidate/v2/metrics.json`): wykrywanie scamu AP 0,82 wobec 0,18 dla reguł słownikowych, temat makro-F1 0,77 wobec 0,52.

### Odtworzenie

Katalog `ml/data/` nie jest w gicie (rozmiar i licencje). Odtwarzają go skrypty w `ml/scripts/`:

1. `collect_*.py`, `ingest_scraper.py`: zbieranie i import eksportu scrapera.
2. `translate_local.py`: tłumaczenie danych uzupełniających (GPU).
3. `build_edge_cases.py`: trudne przypadki.
4. `label_teacher.py`: etykietowanie modelem-nauczycielem.
5. `train_heads.py`: trening i metryki.

### Ograniczenia

- Licencje niekomercyjne (MAFB, VideoConviction) i brak licencji Fraud-R1: przed wdrożeniem produkcyjnym te zbiory trzeba usunąć albo wyjaśnić.
- OCR i transkrypcje mają błędy w polskich znakach i nazwach własnych.
- Filtr regionu PL w Google Ads nie jest szczelny, część kreacji jest po angielsku.
- Treści z listy CERT pochodzą z kopii archiwalnych. Nie odwiedzamy żywych domen oszustów.
