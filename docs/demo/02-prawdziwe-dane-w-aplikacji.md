# Etap 2: prawdziwe dane w aplikacji

**Cel:** frontend pokazuje rekordy zebrane przez scraper i ocenione przez ai-service, a nie dane z generatora.
**Czas:** około 2–3 godziny.
**Zależy od:** etapu 1, kroki 1 i 2. Może iść równolegle z etapem 3.
**Repo:** `HackNation-UKNF-InvestWatch`.

## Zakres plików

| Wolno zmieniać | Nie zmieniać |
|---|---|
| `frontend/mock-server/**` | `ml/src/investwatch_ml/**` (etap 3) |
| nowy `ml/scripts/build_findings.py` | `ml/models/**` (etap 1 i 3) |
| `frontend/src/**`, tylko gdy to konieczne | istniejące kolektory w `scrapers/` |
| `compose*.yaml`, tylko usługa `api` | sekrety i pliki `.env` |

Nie rób commitów bez wyraźnej prośby.

## Decyzja architektoniczna

Na demo nie stawiamy jeszcze Postgresa. Serwer Node z `frontend/mock-server` zostaje, bo ma już wszystkie endpointy i zdarzenia socket.io, ale dostaje drugi tryb danych:

```text
DATA_MODE=mock  -> obecny generator (domyślnie, CI i smoke test bez zmian)
DATA_MODE=real  -> frontend/mock-server/data/findings.real.json
```

W trybie `real` serwer **nie może** generować rekordów ani kampanii. Przy braku pliku ma zakończyć start czytelnym błędem, bez cichego przejścia na dane z mocka.

## Krok 1: `ml/scripts/build_findings.py`

Wejście:

1. `data/export/*/records.jsonl` (eksport scrapera),
2. `ml/data/raw/scraper_live/*/records.jsonl` (Meta i Bing),
3. `ml/data/pool/m3_youtube.jsonl` (kandydaci M3). To format `Doc`, więc przed wysłaniem zamień go na rekord kolektora: `source="youtube"`, `source_url=url`, `text={"title": title, "description": text}`, `content_type="video"`.

Na tym etapie **nie używaj** danych syntetycznych ani tłumaczonych (`mafb`, `fraud_r1`, `videoconviction`, `edge_cases`). Na ekranie mają być wyłącznie realne treści.

Przebieg:

1. Wczytaj rekordy i usuń duplikaty po `source_url`.
2. Wysyłaj je paczkami po 32 do `POST http://localhost:8000/ingest` jako `{ "records": [...] }`.
3. Każdy wynik ma postać `{ item, analysis }`. Zmapuj go na `Finding` według tabeli niżej.
4. Zachowaj rekordy z tematem `INVESTMENT` albo `scam.p >= 0.3`. Pozostałe tylko policz w statystykach importu.
5. Jeśli istnieje `POST /campaigns/build` (etap 3), wywołaj go i uzupełnij `campaignId`, `related` i listę kampanii. Jeśli nie istnieje, zostaw kampanie puste.
6. Zapisz atomowo (plik tymczasowy, potem zamiana) do `frontend/mock-server/data/findings.real.json`:

```json
{ "generatedAt": "ISO", "modelVersion": "...", "findings": [], "campaigns": [], "stats": {} }
```

Dopisz ten plik do `.gitignore`.

## Mapowanie `item` + `analysis` na `Finding`

| `Finding` | Źródło | Uwagi |
|---|---|---|
| `id` | `item.id` | stabilne między przebiegami |
| `url` | `item.url` | patrz „Bezpieczeństwo” |
| `platform` | `item.platform` | wartość spoza typu `Platform` zamień na obsługiwaną albo rozszerz typ |
| `kind`, `title`, `publishedAt`, `fetchedAt` | `item` | puste daty: `fetchedAt` = czas importu |
| `author` | `item.author` | |
| `text` | `analysis.analyzedText` | **obowiązkowo**, bo offsety dowodów odnoszą się do tego tekstu |
| `topic`, `contentType`, `instruments`, `flags` | `analysis` | sprawdź kształt `evidence` względem typu `Evidence` |
| `rules`, `modules`, `riskScore`, `riskLevel`, `scam` | `analysis` | |
| `entities`, `indicators`, `modelVersion` | `analysis` | |
| `outboundLinks` | `item.outboundLinks` | |
| `transcript` | fragment po `[TRANSKRYPCJA]`, jeśli jest | |
| `landingPages` | `[]` | wzbogacenie nie jest gotowe |
| `media` | **brak pola** | wynik głosu z `/enrich/media` jest zaślepką i nie może trafić do UI |
| `campaignId`, `related` | `/campaigns/build` | domyślnie `undefined` i `[]` |
| `status` | `NEW` | |
| `history` | jeden wpis „zaimportowano” | |

Zapisz też pole `scoringInput` z `analysis` (etap 3). Serwer używa go przy przeliczaniu progów i nie wysyła go do frontendu.

## Krok 2: tryb `real` w serwerze

- Wydziel ładowanie świata tak, by `server.ts` wybierał `createWorld(...)` albo nową funkcję `loadRealWorld(path)`.
- Zbuduj `World`: `findings`, `byId`, `index`, `members`, `campaigns`, `thresholds`, `evalSet`.
- `evalSet` wczytaj z `GET ${AI_URL}/calibration/eval-set`.
- `/api/stats/*`, `/api/history`, `/api/rules` i raporty mają liczyć wyniki z prawdziwych rekordów.
- Status rekordu zapisuj do `frontend/mock-server/data/state.json`, żeby przetrwał restart.
- Dodaj zmienne `DATA_MODE` i `AI_URL` (w Dockerze `http://ai-service:8000`).

## Krok 3: progi

`PUT /api/thresholds` i `POST /api/thresholds/preview` w trybie `real` wołają `POST ${AI_URL}/rescore` zgodnie z kontraktem z etapu 3. Wynik zapisują w świecie i wysyłają `thresholds:updated`. Przy niedostępnym AI zwróć błąd 503 i nie zmieniaj zapisanych progów.

## Krok 4: zdarzenia na żywo

W trybie `real` nie wolno tworzyć fikcyjnych rekordów. Dodaj tryb odtwarzania demo: `DEMO_REPLAY=1` trzyma 20 rekordów poza listą i co kilka sekund je dodaje, emitując `finding:new`, a dla wysokiego ryzyka także `finding:high_risk`. Rekordy są prawdziwe, tylko ich pojawianie się jest symulowane, więc UI musi pokazywać etykietę „tryb demo”.

## Bezpieczeństwo

- Nie renderuj aktywnych linków do domen z listy CERT ani do rekordów z wysokim `scam.p`. Pokaż adres jako tekst albo link do kopii w archiwum.
- Treść ze scrapera to niezaufany tekst. Renderuj ją bez HTML.
- Interfejs mówi „wymaga weryfikacji”, nigdy „naruszenie stwierdzone”.

## Gotowe, gdy

- [ ] `DATA_MODE=mock` działa jak wcześniej i przechodzi testy CI.
- [ ] `DATA_MODE=real` pokazuje wyłącznie rekordy z `findings.real.json`.
- [ ] Podświetlenia dowodów trafiają w poprawny fragment tekstu na 10 losowych rekordach.
- [ ] Działają listy modułów, szczegóły, statystyki, zmiana statusu i restart bez utraty statusu.
- [ ] Zmiana progu zmienia wyniki przez ai-service.
- [ ] W interfejsie nie ma wyniku analizy głosu ani fikcyjnych rekordów.
- [ ] `npm run build` i `npm test` przechodzą.
