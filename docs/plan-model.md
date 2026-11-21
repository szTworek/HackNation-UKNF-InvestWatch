# InvestWatch – plan modelu klasyfikacji (v2, budżet 12h)

Zakres: **tylko model** (dane → etykiety → trening → ewaluacja → `predict()`). Scraping robi osobna osoba
(kontrakt JSON w sekcji 7). Dane wejściowe: **posty z social mediów i transkrypcje filmów, tylko PL**,
real data, bez masowej syntetyki. Model zwraca prawdopodobieństwa, progi ustawia panel kalibracji.

## 0. Najważniejsze wnioski z materiałów organizatora

1. **Trzy moduły to trzy różne pytania i każde wymaga innej klasyfikacji:**
   - M1: reklama **zarejestrowanej** firmy inwestycyjnej (także zagranicznej, działającej transgranicznie po polsku) publikowana przez **osobę trzecią** (finfluencer).
     Wynik: firma, reklamujący, treść, URL, okresowa aktualizacja.
   - M2: materiał publikowany **przez samą zarejestrowaną firmę**. Ocena informacji o ryzyku: czy jest dostateczna, **proporcjonalna do informacji o zyskach** i wyraźna (18 reguł).
   - M3: podmiot **niebędący firmą inwestycyjną** (wealth management, investment consulting, family office, „doradca”), który faktycznie świadczy doradztwo.
2. **Definicja doradztwa (zał. 3, art. 76 uoof)** to **spersonalizowana** rekomendacja („w oparciu o potrzeby i sytuację klienta”) dotycząca **instrumentów finansowych**. Wynikają z tego dwie rzeczy:
   - Ogólne „kupcie akcje X” od finfluencera to rekomendacja inwestycyjna (MAR/ESMA), a nie doradztwo. To osobna flaga.
   - Krypto (poza tokenami będącymi instrumentami), złoto fizyczne czy nieruchomości **nie są instrumentami finansowymi**. Ich „doradca” nie trafia do M3 jako naruszenie art. 76. Za to akcje, obligacje, jednostki funduszy, ETF, **CFD/forex** i inne derywaty – tak.
3. **Oszustwa (scam) nie są wprost żadnym z modułów, ale przecinają wszystkie trzy:**
   - Scam podszywa się pod zarejestrowane firmy i znane osoby. Bez rozróżnienia raport M1 zaśmieci się fałszywymi reklamami „XTB/Orlen/PKO”.
   - Scam oferuje „opiekuna konta” i „strategię dopasowaną do Ciebie”, więc z tekstu wygląda jak M3.
   - Według CSIRT KNF fałszywe inwestycje to ponad 96% z 41 751 domen oszukańczych zgłoszonych do blokady w 2025 r.

   Dla analityka to najbardziej wartościowy alert, więc **scam ma osobną ścieżkę** (sekcja 2).
4. **Ocena jury:** trafność klasyfikacji ryzyka, **wpływ progu na FP/FN w panelu kalibracji**, stabilność, bezpieczeństwo bibliotek i czystość konsoli.
   Wagi: technologia 30%, innowacyjność **(w tym ustandaryzowany proces pracy z asystentami AI – trzymamy `docs/` jako dowód)** 20%, architektura 20%, zgodność ze specyfikacją 20%, atrakcyjność 10%.
5. Wymagania techniczne: open source i on-premise (Ollama/vLLM, **zero płatnych API**), Docker Compose, skan zależności (Snyk / `pip-audit`), sekrety w `.env`, README minimalny.
   Do oddania: opis, prezentacja PDF, README, repo i opcjonalnie film do 3 min.
6. Organizator **nie dał próbek danych**. Gold set budujemy sami.

## 1. Architektura modelu: embeddingi + weak supervision

1. Embedding model (zamrożony) + lekkie głowy (LogReg/MLP). Trenuje się w minuty, łatwo go kalibrować i jest szybki.
2. **Bielik 11B (lokalnie, Ollama) jako nauczyciel**: etykietuje kilka tysięcy realnych tekstów i cytuje fragmenty dla każdej flagi.
3. **Flagi na poziomie fragmentów** (okna ok. 40–60 słów z zakładką, bo transkrypcje ASR nie mają interpunkcji):
   flaga dokumentu = max po fragmentach, a najlepszy fragment = evidence.
4. **Funkcje scoringowe** (wymóg specyfikacji) łączą wyjścia modelu z lookupami w jawne score'y per moduł i dla scamu.
5. Opcja, jeśli zostanie czas: fine-tune pl-ModernBERT jako porównanie.

## 1a. Pipeline dwuetapowy: triage → wzbogacenie → klasyfikacja końcowa

Drogie kroki (przeglądarka, wideo, audio) robimy tylko dla treści, które przeszły szybki filtr.

```
item ──▶ [1] TRIAGE: klasyfikator tekstu (post / opis / transkrypcja z platformy)
             p(INVESTMENT), p(SCAM) – niski próg, wysoki recall
         │  nieinwestycyjne → koniec (zapis z niskim ryzykiem)
         ▼
         [2a] STRONA DOCELOWA (scraper, Playwright w izolowanym kontenerze, bez wypełniania formularzy)
              łańcuch przekierowań, finalna domena, tekst strony, zrzut desktop + mobile,
              formularze (telefon/e-mail = „konsultant oddzwoni”), bloki tekstu ze stylami (rozmiar czcionki, kolor, widoczność)
         [2b] WIDEO / AUDIO (ai-service)
              klatki kluczowe (ffmpeg, zmiana sceny / co ~3 s) → OCR napisów na ekranie
              audio → ASR (faster-whisper), gdy platforma nie daje napisów
              detektor syntetycznego głosu (deepfake) → score per segment
         ▼
         [3] KLASYFIKACJA KOŃCOWA: ten sam model na tekście złożonym z sekcji
             [POST] [TRANSKRYPCJA] [NAPISY NA EKRANIE] [STRONA DOCELOWA]
             + cechy scam scorera: domena landingu na listach CERT/KNF, podszywanie się, formularz telefonu,
               syntetyczny głos, sąsiedzi w grafie kampanii
```

Co to daje:
- **Scam:** post bywa niewinny („zobacz, co powiedział X 👇”), a dopiero landing to fałszywy artykuł z formularzem.
  Deepfake celebrytów w wideo to dziś główny wektor oszustw.
- **Reguły wizualne 4, 5, 7 i 8 przestają być „NOT_CHECKED”.** Z bloków tekstu Playwrighta liczymy:
  - r4: rozmiar czcionki ostrzeżenia vs mediana strony,
  - r5: kontrast WCAG koloru tekstu do tła,
  - r7: czy ostrzeżenie jest widoczne bez rozwijania,
  - r8: czy na mobile ostrzeżenie się mieści i jest czytelne.

  Dla wideo i grafik r4 liczymy z wysokości ramek OCR (ostrzeżenie vs główny przekaz).
- Evidence wskazuje sekcję i czas: „napis na ekranie w 0:12”, „strona docelowa”, „transkrypcja 1:45”.

Realizm (12h), w kolejności priorytetu:
1. landing: klasyfikacja tekstu + cechy domen (tanie, scraper daje dane),
2. ASR fallback (faster-whisper, GPU, ok. 1h pracy),
3. reguły 4/5/7/8 z bloków DOM (wysoka wartość dla modułu 2 i zgodności ze specyfikacją),
4. OCR klatek (EasyOCR `pl`),
5. detektor syntetycznego głosu: **eksperymentalny**. Otwarte detektory (wav2vec2/AASIST na ASVspoof) słabo generalizują
   na skompresowane nagrania z social mediów i nowe syntezatory, więc to słaba cecha z niską wagą,
   pokazywana jako „sygnał pomocniczy”, a nie werdykt.

Opcja na później: VLM (Gemma z wizją w Ollamie) opisujący zrzut landingu („fałszywy artykuł”, „formularz rejestracji”).
Konkuruje z Bielikiem o 12 GB VRAM.

## 2. Etykiety

**A – temat** (single): `NON_FINANCIAL`, `FINANCIAL_OTHER`, `INVESTMENT`

**B – typ treści** (single, gdy A=INVESTMENT):
`NEWS_EDU`, `OPINION_DISCUSSION`, `FIRM_OWN_MARKETING` (M2), `THIRD_PARTY_PROMO` (M1), `RECOMMENDATION`, `SERVICE_OFFER` (M3-kandydat)

**C – instrumenty** (multi): `CFD_FOREX`, `STOCKS`, `FUNDS_ETF`, `BONDS`, `CRYPTO`, `OTHER_DERIVATIVES`, `NON_INSTRUMENT` (złoto, nieruchomości, „projekty”)

**D – flagi zgodności, fragmentowe** (M2 + M1):
`PROFIT_CLAIM` (r3), `RISK_WARNING` (r3/r6), `AD_DISCLOSURE` (r2 + #reklama/#współpraca/kod/link afiliacyjny), `PAST_PERFORMANCE` (r12–13),
`PAST_PERF_DISCLAIMER` (r14), `FORECAST` (r15), `FORECAST_DISCLAIMER` (r15), `TAX_CLAIM` (r16), `PRODUCT_COMPARISON` (r11),
`SUPERVISOR_AS_SAFETY` (r17–18)

**E – flagi doradztwa** (M3): `PERSONALIZED_ADVICE` („dobiorę portfel do Twojej sytuacji”), `PAID_ADVISORY_SERVICE`
(konsultacje, abonament, „zarządzam portfelami klientów”), `SPECIFIC_INSTRUMENT_CALL` (kup/sprzedaj/trzymaj konkretny instrument)

**F – scam**:
- głowa dokumentowa `SCAM` (binarna, sigmoid, **niezależna od typu treści**, bo scam też jest „reklamą”),
- flagi fragmentowe:
  - `GUARANTEED_PROFIT` / `NO_RISK_CLAIM`, `UNREALISTIC_RETURNS` (dodatkowo regex na liczby: „30% miesięcznie”, „z 1000 zł 15 000 zł”),
  - `URGENCY_PRESSURE` („tylko dziś”, „ostatnie miejsca”), `CELEBRITY_OR_BRAND_ENDORSEMENT` („Lewandowski/Orlen/PKO inwestuje”),
  - `AUTOMATED_PROFIT` („bot/AI trading”, „platforma zarabia za Ciebie”), `LOW_ENTRY_DEPOSIT` („zacznij od 250 USD / 1000 zł”),
  - `OFF_PLATFORM_CONTACT` („zostaw numer, konsultant oddzwoni”, WhatsApp/Telegram), `SECRECY_CONSPIRACY` („banki nie chcą, żebyś wiedział”),
  - `FAKE_NEWS_FORMAT` (styl fałszywego artykułu lub wywiadu).

## 3. Scoring (agregator) – jawne funkcje, progi z panelu kalibracji

- **Lookupy** (bez ML):
  - rejestr firm inwestycyjnych KNF (4 listy z zał. 1) → fuzzy match nazw (rapidfuzz),
  - lista ostrzeżeń publicznych KNF i CERT hole.cert.pl → domeny i podmioty,
  - mapa *marka → oficjalne domeny* dla ok. 30 największych brokerów i banków (ręcznie),
  - langdetect dla reguły 10.
- **Scam score**: LogisticRegression na cechach `[p(SCAM), max flag F, domena na liście CERT/KNF, podszywanie się, brak w rejestrze, brak ostrzeżenia CFD]`.
  Kluczowa cecha **podszywanie się**: tekst wymienia zarejestrowaną markę, ale link prowadzi poza jej oficjalne domeny. Jest tania i bardzo silna.
- **M1**: `THIRD_PARTY_PROMO ∧ podmiot ∈ rejestr ∧ ¬scam` → rekord raportu. Dodatkowo naruszenie, jeśli brak `AD_DISCLOSURE` albo `PROFIT_CLAIM ∧ ¬RISK_WARNING`.
- **M2**: `FIRM_OWN_MARKETING ∧ podmiot ∈ rejestr` → reguły, np. r3: `max(PROFIT_CLAIM) > t ∧ max(RISK_WARNING) < t`
  oraz proporcjonalność (liczba i siła fragmentów zysku vs ryzyka). Reguły 4–8 są wizualne, więc `NOT_CHECKED`.
- **M3**: `(PERSONALIZED_ADVICE ∨ PAID_ADVISORY_SERVICE) ∧ instrument ∉ {CRYPTO, NON_INSTRUMENT}-only ∧ podmiot ∉ rejestr`.
- Scam ma priorytet: rekord z wysokim scam score idzie jako alert CRITICAL niezależnie od modułu.

## 3a. Graf powiązań / kampanie scamowe

Scamy działają kampaniami: setki postów z tym samym szablonem tekstu, rotujące domeny, te same numery telefonów i kanały Telegram.
Pojedynczy post bywa niejednoznaczny, ale jego powiązanie ze znaną kampanią jest mocnym sygnałem.

**Węzły:** post / transkrypcja, autor (profil), domena (po rozwinięciu przekierowań i skracaczy), telefon, Telegram/WhatsApp,
e-mail, portfel krypto, IBAN, marka podszywana, osoba publiczna.

**Krawędzie:**
- `SHARES_INDICATOR` – wspólny wskaźnik (domena, telefon…), ważony IDF. Stoplista popularnych domen (youtube.com, bit.ly, facebook.com…).
- `SIMILAR_TEXT` – cosine embeddingów > próg (ANN top-k) albo near-duplicate (MinHash); wykrywa szablony kampanii.
- `SAME_AUTHOR`, `REDIRECTS_TO` (łańcuch przekierowań od scrapera), `IMPERSONATES` (post → marka).

**Kampania** = społeczność w grafie (connected components na silnych krawędziach + Louvain z networkx).
Etykieta kampanii pochodzi z członków: udział potwierdzonych scamów i średni scam score.

**Przy każdym nowym rekordzie:**
1. ekstrakcja wskaźników (regex: URL/domena, +48 telefony, t.me, wa.me, e-mail, portfele BTC/ETH/TRX, IBAN; marki z NER/słownika),
2. embedding → ANN top-k podobnych,
3. upsert krawędzi → przypisanie do kampanii,
4. **cecha `graph_scam_neighbors`** (ważony udział scamów wśród sąsiadów) wchodzi do scam scorera,
5. jeśli kampania jest scamowa, emitujemy alert „nowy element kampanii X”.

**Pętla analityka:** potwierdzenie scamu przez analityka propaguje się na kampanię. Jej niezweryfikowani członkowie dostają podbity score i trafiają do kolejki.
To jest active learning bez dodatkowego kodu ML.

**Storage (do uzgodnienia z backendem):** Postgres + **pgvector** (ANN embeddingów) + tabele `nodes` / `edges`.
Spełnia wymóg „baza SQL” bez dodatkowej bazy grafowej. Clustering liczy serwis AI (networkx) inkrementalnie lub co N minut.
Neo4j odpada, bo to dodatkowy ciężki serwis bez realnej korzyści przy tej skali.

Z mojej strony (ML): `indicators.py` (ekstrakcja), `graph.py` (krawędzie, kampanie, cecha do scorera) i notebook z wizualizacją kampanii na zebranych danych.
Landingi z Common Crawl dla domen CERT dają od razu realne kampanie do demo.

## 4. Źródła danych (realne, PL, social media)

| Źródło | Co daje | Prio |
|---|---|---|
| Pierwsze wyniki scrapera kolegi | realny rozkład, gold | 1 |
| Transkrypcje YouTube polskich kanałów finansowych (youtube-transcript-api / yt-dlp) | segmenty sponsorowane (M1), rekomendacje, edukacja, ostrzeżenia | 1 |
| Reddit PL (r/Polska_wpz, r/inwestowanie, r/kryptowaluty) przez publiczne archiwum | posty i dyskusje = negatywy, cytowane scamy | 1 |
| Lista CERT hole.cert.pl + ostrzeżenia KNF → Common Crawl (CDX) | **realne teksty landingów scamowych** | 1 |
| Rejestr KNF → strony i profile firm | `FIRM_OWN_MARKETING`, legalne ostrzeżenia CFD = hard negatives dla scamu | 1 |
| Raport CSIRT KNF „Schematy i metody oszustw inwestycyjnych” (PDF) | wzorce i przykłady do flag F oraz promptu nauczyciela | 2 |
| Mendeley Investment Deception, ScamBench (kat. investment) → tłumaczenie Bielikiem | uzupełnienie klasy SCAM (skrypty scamów są międzyjęzykowe) | 2 |
| FineWeb-2 `pol_Latn` (filtrowane) | dodatkowe strony firm i treści finansowe | 3 |

Hard negatives są kluczowe dla FP: legalna reklama CFD z ostrzeżeniem ESMA („X% rachunków inwestorów detalicznych traci pieniądze”)
vs scam, który ją kopiuje. Edukacja o scamach („uważajcie na reklamy z Lewandowskim”) vs sam scam.

## 5. Modele

- Embeddingi: **bge-m3** (8k, multilingual) vs **mmlw-roberta-large / stella-pl** (PL-MTEB). Wybór na gold.
- Nauczyciel: **Bielik 11B v3.1 Instruct Q4_K_M** (Ollama), JSON schema.
- Głowy: LogReg/MLP + kalibracja. Baseline: TF-IDF + LogReg.
- Metryki: per głowa i flaga precision/recall/PR-AUC. **Dla SCAM osobno recall przy ustalonej precyzji.**
  Tabela próg → FP/FN do panelu kalibracji.

## 6. Gold set

ok. 200–250 realnych tekstów oznaczonych przez człowieka (Bielik pre-label, człowiek poprawia), warstwowo:
ok. 50 scam, 50 promocja/reklama legalna, 40 oferty usług/doradztwa, 60 edukacja/news/dyskusja, 30 niefinansowe.
Podział po autorze/kanale/domenie, żeby ten sam autor nie trafił do train i test.

## 7. Kontrakt z backendem

> Wiążąca wersja kontraktu (camelCase, pełne pola, baza, przepływy) jest w `docs/backend-integration.md`. Poniżej skrót.

```jsonc
// input (od scrapera)
{ "id": "...", "url": "...", "platform": "facebook|instagram|tiktok|youtube|x|web",
  "kind": "post|transcript|comment|page", "author": {"handle": "...", "followers": 0},
  "text": "...", "outbound_links": ["..."], "published_at": "ISO", "fetched_at": "ISO" }
// output (serwis AI, FastAPI)
{ "topic": {...}, "content_type": {...}, "instruments": {...},
  "flags": {"PROFIT_CLAIM": {"p": 0.88, "evidence": [{"start": 10, "end": 80, "text": "..."}]}, ...},
  "scam": {"p": 0.93, "signals": ["IMPERSONATION", "CERT_LIST_DOMAIN", "GUARANTEED_PROFIT"]},
  "entities": [{"name": "...", "role": "investment_firm", "knf": "REGISTERED|NOT_FOUND|ON_WARNING_LIST"}],
  "module_scores": {"m1": 0.7, "m2": 0.2, "m3": 0.1}, "model_version": "..." }
```

`outbound_links` od scrapera są **ważne dla scamu** (podszywanie się, lista CERT). Trzeba to uzgodnić z kolegą.

## 8. Harmonogram (12h)

| h | Zadanie |
|---|---|
| 0–1 | env, Ollama + Bielik + bge-m3, zamrożenie etykiet |
| 1–3 | źródła: YT transkrypcje, Reddit, CERT/KNF → CC landingi, rejestr KNF; pula ok. 3–5k |
| 3–7 | Bielik etykietuje w tle; równolegle gold (ok. 200) + baseline; lookupy (rejestr, CERT, marki) |
| 7–9 | embeddingi, głowy, scam scorer, ewaluacja, tabele progów |
| 8–10 | wskaźniki + graf + kampanie, cecha grafowa w scam scorerze |
| 9–11 | `predict()` + FastAPI, eksport, (opcja) ModernBERT |
| 11–12 | bufor, wykresy do prezentacji |
