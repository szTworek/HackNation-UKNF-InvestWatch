# Etap 3: model i funkcje AI

**Cel:** ai-service używa wytrenowanego modelu, wykrywa kampanie, obsługuje rekomendacje i nie pokazuje zaślepek jako wyników.
**Czas:** około 3–4 godziny.
**Zależy od:** etapu 1, kroki 1 i 2. Model podmieniamy po kroku 4 etapu 1. Może iść równolegle z etapem 2.
**Repo:** `HackNation-UKNF-InvestWatch`.

## Zakres plików

| Wolno zmieniać | Nie zmieniać |
|---|---|
| `ml/src/investwatch_ml/**` | `frontend/**` (etap 2) |
| `ml/scripts/**`, poza `build_findings.py` | procesy i pliki w starym repo `UKNF` |
| `compose*.yaml`, tylko usługa `ai-service` | sekrety i pliki `.env` |

Finalna aplikacja nie może wołać Gemini, Groq ani innego płatnego lub zewnętrznego API. Te usługi służą tylko do przygotowania danych. Nie rób commitów bez wyraźnej prośby.

## Kontrakt z etapem 2

Zmiany w odpowiedziach są wyłącznie dodawaniem pól. Istniejące pola `/ingest` i `/analyze` zostają.

**`analysis.scoringInput`** to nowe pole z danymi potrzebnymi do ponownego liczenia wyniku:

```json
{ "pred": {}, "entities": [], "context": {} }
```

**`POST /rescore`** przyjmuje opcjonalne `items`, dzięki czemu działa po restarcie ai-service, gdy pamięć `_PRED` jest pusta:

```json
{
  "thresholds": {},
  "persist": false,
  "items": [{ "itemId": "scr-1", "scoringInput": {} }]
}
```

**`POST /campaigns/build`**:

```json
// wejście
{ "items": [{ "id": "scr-1", "text": "...", "author": "...", "platform": "facebook",
              "indicators": [], "scamP": 0.8, "fetchedAt": "ISO" }] }

// wyjście
{
  "campaigns": [{ "id": "C-ab12", "name": "...", "memberIds": ["scr-1"], "topIndicators": [] }],
  "assignments": { "scr-1": "C-ab12" },
  "related": { "scr-1": [{ "findingId": "scr-2", "reason": "SHARES_INDICATOR", "detail": "wspólna domena x.pl", "score": 0.9 }] }
}
```

Identyfikator kampanii musi być stabilny dla tego samego składu, np. hash posortowanych wskaźników.

## Krok 1: włączenie modelu

Stan dziś: kontener zgłasza `baseline-heuristics-0.1`. Domyślny `compose.yaml` montuje pusty `./models`, a `compose.dev.yaml` wymusza `INVESTWATCH_BASELINE=1`.

1. Ustaw `MODELS_PATH=./ml/models` i `INVESTWATCH_BASELINE=0`.
2. Upewnij się, że `BAAI/bge-m3` jest dostępny w cache `hf-cache`. Po pierwszym pobraniu usługa ma działać bez internetu.
3. Na komputerze z GPU uruchom z `compose.gpu.yaml`. Karta ma 12 GB, więc **najpierw zatrzymaj Bielika i inne procesy GPU**.
4. Sprawdź `GET /health`. `modelVersion` musi zaczynać się od `heads-`.
5. Bramka jakości (`n_train >= 500`, są przykłady scamu) musi przejść bez `INVESTWATCH_USE_MODEL=1`.

Porównaj metryki z kandydatem z 21.11 (`temat 0,77`, `typ treści 0,44`, `scam AP 0,75`). Jeśli finalny model jest gorszy, użyj kandydata i zapisz powód.

## Krok 2: kontrakt `/rescore` i `scoringInput`

Zaimplementuj kontrakt powyżej. Test: `/ingest`, restart usługi, `/rescore` z `items`, wynik identyczny jak przed restartem przy tych samych progach.

## Krok 3: kampanie

Nowy moduł `ml/src/investwatch_ml/campaigns.py`, lokalny, bez bazy:

1. Krawędzie mocne: wspólna domena, telefon, Telegram, WhatsApp, kod afiliacyjny.
2. Krawędzie słabsze: podobieństwo embeddingów `>= 0.92` w obrębie rekordów z `scamP >= 0.3`.
3. **Pomiń wskaźniki popularne:** domeny platform (`youtube.com`, `facebook.com`, `t.me` bez nazwy kanału, skracacze linków) i każdy wskaźnik u ponad 5% rekordów. Inaczej wszystko sklei się w jedną kampanię.
4. Grupowanie: spójne składowe na mocnych krawędziach, potem Louvain na grafie ważonym.
5. Kampania ma co najmniej 3 rekordy i co najmniej 2 różnych autorów albo wspólny mocny wskaźnik.
6. Nazwa powstaje z najmocniejszego wskaźnika, bez użycia LLM.

## Krok 4: rekomendacje i nieuprawnione namawianie

Dziś treści typu „kupujcie akcje X” nie trafiają do żadnego modułu.

- Dodaj regułę `M3_RECOMMENDATION`, gdy `contentType.RECOMMENDATION` lub flaga `SPECIFIC_INSTRUMENT_CALL` przekroczy próg.
- Rekord trafia do widoku modułu 3 jako **„do weryfikacji”**, z osobnym uzasadnieniem.
- Odróżnij to od `PERSONALIZED_ADVICE`. Rekomendacja dla ogółu nie jest doradztwem dopasowanym do klienta. Kryptowaluty, złoto i nieruchomości nie są instrumentami finansowymi w tym rozumieniu.
- Prywatna opinia lub relacja z własnej transakcji nie może uruchamiać tej reguły.
- Przekaż identyfikator i polską nazwę reguły do etapu 2, który dopisze ją w `/api/rules`.

Test: przypadki `reco`, `opinion` i `advisory` z `ml/data/gold/edge_cases.jsonl`.

## Krok 5: usunięcie zaślepek

- `/enrich/media`: usuń losowy `syntheticVoice.score`. Zwracaj `{"asr":{"used":false,"text":"","segments":[]},"keyframes":[],"syntheticVoice":null}` z informacją, że funkcja nie jest aktywna.
- `/explain`: zbuduj opis z prawdziwych reguł, flag i cytatów, bez dopisku „stub”. Bielik może być później opcją, ale demo nie może od niego zależeć.
- `/calibration/eval-set`: gdy brak `eval_set.json`, zwróć pustą listę lub błąd zamiast syntetycznych danych.

## Krok 6, tylko jeśli zostanie czas

1. Strona docelowa przez Playwright w izolacji, wyłącznie dla kopii archiwalnych przy domenach podejrzanych. **Nie odwiedzamy żywych domen oszustów.**
2. OCR z `preprocessing/ocr` w przepływie `/ingest`.
3. Reguły wizualne 4, 5, 7, 8. Do tego czasu mają status `NOT_CHECKED`, nigdy `OK`.
4. Trening z ręcznie ocenionymi danymi z `ml/data/review/review_decisions.json`.

## Gotowe, gdy

- [ ] `/health` pokazuje model `heads-*`, a usługa działa bez internetu.
- [ ] Kod aplikacji nie zawiera wywołań Gemini ani Groq poza skryptami danych.
- [ ] `/rescore` działa po restarcie.
- [ ] `/campaigns/build` nie tworzy jednej wielkiej kampanii i zwraca stabilne identyfikatory.
- [ ] Rekomendacje trafiają do M3 jako „do weryfikacji”, a opinie nie.
- [ ] Żaden endpoint nie zwraca losowego ani udawanego wyniku.
