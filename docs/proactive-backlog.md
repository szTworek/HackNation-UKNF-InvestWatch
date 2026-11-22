# Proactive backlog — InvestWatch

Źródło wymagań: `C:\Users\szymo\Documents\projects\hacknation\inwestwatch\UKNF\pliki_dc\markdown\Opis Wyzwania HackNation UKNF 19.11.md` (dalej: Opis), reguły M2: `ZASÓB DLA UCZESTNIKÓW - InvestWatch - kryteria oceny informacji o ryzyku.md` (dalej: Zasób).
Prace innych sesji (stan iter. 2, wszystkie poza gitem albo nieśledzone):
- `C:\Users\szymo\Documents\projects\hacknation\inwestwatch\docs\sources-feasibility.md` (dalej: Feasibility)
- `C:\Users\szymo\Documents\projects\hacknation\inwestwatch\UKNF\docs\wow-ideas.md` (dalej: Wow)
- `C:\Users\szymo\Documents\projects\hacknation\inwestwatch\UKNF\docs\DECYZJE.md` (D1–D4, kontrakt RawDocument)
- `C:\Users\szymo\Documents\projects\hacknation\inwestwatch\scrapers\knf_registry\` + `data\knf_entities.json` (760 podmiotów)

Status: niecommitowane, prowadzone przez pętlę `/loop 30m` (max 8 iteracji).

## Ryzyka

| # | Ryzyko | Źródło | Skutek | Mitygacja |
|---|---|---|---|---|
| R10 | Budżet się nie domyka: same 4 kolektory to ~22 h (Feasibility §3), core ~40–45 h, wyróżniki 13–16 h (Wow), razem ~80 h przy ~60 osobogodzinach (Wow, nagłówek) | Feasibility §3, Wow | na koniec brak dashboardu albo panelu kalibracji, które jury ocenia wprost (Opis §6) | live tylko WWW+SearXNG i YouTube (8 h + 3 h); TikTok i Meta tylko z fixture'ów; wyróżnik #1 od razu w wersji przyciętej R4+R8 |
| R11 | Pliki sesji leżą poza repo: `inwestwatch\docs`, `inwestwatch\scrapers`, `inwestwatch\data` nie są w `UKNF` (jedyne repo git), a `UKNF\docs` jest nieśledzone (`git status` → `?? docs/`) | `git status`, `find` | repozytorium do oceny (Opis §4) bez kodu scrapera rejestru | przenieść do `UKNF\` przed pierwszym commitem; jedna sesja odpowiada za strukturę katalogów |
| R12 | Meta Ad Library API wymaga weryfikacji tożsamości 1–3 dni robocze (Feasibility §2.2 [W]); hackathon kończy się wcześniej | Feasibility §2.2 | M1 bez FB/IG, choć Opis §2 wymienia je wprost | decyzja dziś: albo ktoś startuje weryfikację teraz, albo od razu tylko WWW Ad Library + fixture |
| R13 | Polskie podmioty z rejestru nie mają domen: z 38 domów i banków maklerskich domenę ma 2 (`knf_entities.json`) | `data\knf_entities.json` | M2 (materiały firm z ich stron) nie ma listy stron startowych; dopasowanie reklamy po domenie nie złapie np. XTB S.A. (`xtb.com` jest przypięte do `XTB Ltd`, cypryjskiej) | ręczna lista seed URL dla 38 polskich podmiotów (P6) |
| R14 | Kompletność rejestru niesprawdzona: brak trafień dla „saxo” i „flatex”/„degiro”; `www.tb.com` jako domena XTB Ltd pochodzi z literówki w źródle KNF | `data\knf_entities.json`, pole `details["Dodatkowe informacje"]` | fałszywe M3 (legalna firma uznana za nieautoryzowaną) | porównać liczbę rekordów z licznikiem na stronie KNF; ręcznie sprawdzić 5 znanych marek |
| R1 | Panel kalibracji bez etykiet nie pokaże FP vs FN | Opis §3.3, §6 | jury ocenia wprost | pokryte w Wow #5 (pętla analityka), dopilnować oznaczenia 30–50 rekordów przed demo |
| R5 | LLM na CPU × 18 reguł × N dokumentów = minuty na dokument | Opis §3.2 | dashboard pusty w demo | jedno wywołanie LLM na dokument, regex przed LLM |
| R6 | Skan zależności (Snyk / pip-audit / npm audit) obowiązkowy | Opis §5, §6 | punkt oceny wprost | ujęte w Wow (sekcja proces); pilnować, że trafi do CI |
| R7 | „Console.log” to osobny punkt oceny | Opis §6 | błędy w DevTools przy jury | lint `no-console`, przegląd konsoli przed demo |
| R9 | M3: firmy zagraniczne z paszportem UE świadczą legalnie | Załącznik 1, 3 | fałszywe M3 | rejestr obejmuje obie listy notyfikacji (760 rekordów, 722 zagraniczne); dochodzi P4 |
| R15 | Wymaganie „embeddingi” i „usuwanie duplikatów” (Opis §3.2 Preprocessing) pokryte tylko dedupem po `content_sha256` (D1); identyczna reklama pod różnymi URL-ami przejdzie jako osobne rekordy | Opis §3.2, D1 | punkt zgodności i zalew duplikatów w dashboardzie | P5 |
| R17 | Score M2 niezdefiniowany: 18 reguł daje 18 werdyktów, a Opis §3.3 wymaga jednego „parametru progowego”; bez reguły agregacji (max? ważona suma?) suwak nie ma na czym działać | Opis §3.3, makieta (Kalibracja) | panel kalibracji M2 nie zadziała albo pokaże coś innego niż karta | decyzja: score M2 = max po regułach tekstowych i wizualnych z wagą reguły; próg per moduł |
| R18 | RAM na laptopie demo: D5 + D6 dają ~10 kontenerów (scraper z Chromium, preprocessing, AI, API, frontend, Postgres, MinIO, Redis, Ollama, SearXNG); `gemma3:12b` w Q4 to rząd 8–10 GB [W, bez pomiaru] | Opis §5 „lista wymagań sprzętowych”, D5, D6 | swap i zamrożony dashboard w trakcie demo | P11 |
| R19 | Score z LLM to werbalna „pewność” w JSON, a Opis §3.2 mówi o „funkcji scoringowej na podstawie warstwy wyjściowej”; werbalna pewność nie jest skalibrowana, więc suwak progu przesuwa się skokami (0,8 / 0,9) | Opis §3.2, Wow #2 (`confidence` w karcie) | krzywa FP/FN schodkowa, słaba demonstracja kalibracji | P10 |
| R20 | Automatyczne napisy YouTube PL (D7) przekręcają nazwy marek i liczby („XTB” → „iks te be”, „12%” → „dwanaście procent”); regex reguł 3/14/15 i dopasowanie do rejestru na nich nie trafią | D7, Feasibility §2.4 | M1/M3 z wideo z niską pełnością, czego panel kalibracji nie pokaże bez etykiet z wideo | P12 |
| R21 | Materiały formalne bez właściciela i czasu w budżecie: opis + tytuł, PDF prezentacji, README, opcjonalny film ≤ 3 min (Opis §4); Wow liczy core i wyróżniki, ale nie te ~3–4 h na końcu | Opis §4, Wow | oddanie bez PDF albo z README pisanym w ostatniej godzinie (Opis §5 „bez AI slop”) | rezerwa 4 h w planie + P13 |
| R16 | „Agregator wyników łączący wyniki 1, 2, 3 w ujednolicone obiekty” (Opis §3.2) bez właściciela; D2 opisuje tylko surowy dokument, nie wynik analizy | Opis §3.2, D2 | brak wspólnego obiektu dla dashboardu i filtrów po module | kontrakt `Finding` (dokument + moduł + reguła + score + podmiot) obok D2 |

Zamknięte w iter. 2: R2 (reguły wizualne) → D3 + Wow #1; R3, R4 (demo bez sieci, dane z pendrive'a) → Feasibility §4; R8 (wspólny checkout) → zastąpione przez R11, gałęzi wciąż brak.

## Pomysły (ranking)

| Rank | Pomysł | Koszt | Kryterium jury | Status |
|---|---|---|---|---|
| 1 | P4. Kontrola zakresu zezwolenia: rejestr ma kody usług (`Zakres działalności` dla polskich, `A - Usługi inwestycyjne… sekcji A załącznika I` dla zagranicznych). Doradztwo inwestycyjne to usługa A5 (MiFID II zał. I sekcja A pkt 5). Firma z rejestru bez A5, która w reklamie lub ofercie „poleca, co kupić”, idzie do M3 jako „poza zakresem zezwolenia”. Przykład z danych: `XTB Ltd` ma A „1, 2, 3, 4”, bez 5. Korekta iter. 5: polskie kody to inna numeracja (`XTB S.A.`: „1, 2, 3, 9, 13, 14, 16”, wartości do 16), więc dla 38 polskich podmiotów potrzebna legenda kodów ze strony KNF [do sprawdzenia]; dla 722 zagranicznych A5 działa wprost | 2 h (+0,5 h legenda PL) | zgodność 20% (M3 wprost: „bez wymaganych zezwoleń”), atrakcyjność 10% | nowy, iter. 2 |
| 2 | P5 (zawężony w iter. 4: embedding jest już w D6, zostaje samo klastrowanie). Embeddingi + klastry kampanii: wektor treści (model open source przez Ollama albo sentence-transformers) w pgvector (D4 już przewiduje), próg podobieństwa grupuje ten sam tekst reklamy z wielu kont w jedną „kampanię”; w M1 widać „ta sama kreacja u 7 finfluencerów” | 3 h | zgodność 20% (Opis §3.2 embeddingi + dedup), architektura 20% | nowy, iter. 2 |
| 3 | P6. Seed URL dla M2: lista stron 38 polskich domów i banków maklerskich (SearXNG po nazwie + ręczna akceptacja), zapis jako pole `domains` w tym samym `knf_entities.json` | 1 h | zgodność 20% (M2 nie ruszy bez stron firm) | nowy, iter. 2 |

| 4 | P7. Status rekordu = etykieta kalibracji: `potwierdzone` → 1, `fałszywy alarm` → 0, reszta bez etykiety. Wymaganie „zmiana statusu rekordu” (Opis §3.3) i pętla analityka (Wow #5) to wtedy jedno pole i jeden endpoint zamiast dwóch | 0,5 h (oszczędza ~1 h z Wow #5) | zgodność 20%, architektura 20% | ulepszenie Wow #5, iter. 3 |
| 5 | P8. Trend po `published_at` (D2), nie po `fetched_at`: filmy YouTube i reklamy Ad Library mają daty publikacji, więc wykres „incydenty w czasie” ma historię tygodni już po pierwszym crawlu, a nie 1 słupek z dnia hackathonu | 0,5 h | technologia/demo 30% | nowy, iter. 3 |
| 6 | P9. Dwa progi w panelu: próg flagi (FP/FN) i próg alertu WebSocket, z podglądem „przy tym progu N alertów na dobę” z historii; bez tego alert na żywo albo milczy, albo zalewa | 1 h | technologia/demo 30% (Opis §6 „powiadomienia w czasie rzeczywistym”) | nowy, iter. 3 |

| 7 | P10. Score z warstwy wyjściowej: dla każdej reguły tekstowej prawdopodobieństwo z logprobs tokenu „tak/nie” (Ollama `logprobs` [W, do sprawdzenia w wersji]) albo z klasyfikatora zero-shot NLI (wielojęzyczny model z Hugging Face, lokalnie); daje ciągły score 0–1, na którym suwak działa płynnie | 2–3 h | zgodność 20% (Opis §3.2 dosłownie), technologia 30% | nowy, iter. 4 |
| 8 | P11. Profile sprzętowe w compose: domyślnie `gemma3:4b`, `--profile big` z `gemma3:12b`; w README tabela RAM/CPU/GPU zmierzona `docker stats` na laptopie demo | 1 h | zgodność 20% (Opis §5 wymagania sprzętowe), technologia/demo 30% | nowy, iter. 4 |

| 9 | P12. Normalizacja transkrypcji przed regułami: liczby słowne → cyfry, słownik fonetycznych aliasów marek z `normalized_aliases` rejestru; dopasowanie rozmyte (np. `rapidfuzz`) zamiast dokładnego tylko dla `source = youtube`. W gold secie min. 5 materiałów wideo, żeby R20 było widać w kalibracji | 1,5 h | zgodność 20%, technologia 30% | nowy, iter. 5 |

| 10 | P13. Scenariusz demo jako test E2E: skrypt Playwright przechodzi scenariusz 3 min z Wow (wklej URL → alert WebSocket → karta → suwak progu), w CI służy jako smoke test, a z `record_video_dir` nagrywa film do zgłoszenia; ten sam skrypt sprawdza czystą konsolę (`page.on("console")`, R7) | 2 h | proces AI 20% (test zamiast deklaracji), technologia/demo 30% | nowy, iter. 6 |

| 11 | P14. Byt `Channel` (kanał/autor) przypisany do podmiotu: `platform`, `handle`, `entity_id`, `relation` (`oficjalny` / `przypisany automatycznie` / `przypisany ręcznie`), `basis` (np. link do domeny podmiotu w bio, `beneficiary_payers` z Meta, kod polecający, decyzja analityka), `followers`. Preprocessing przypisuje `author` z koperty (D2) do kanału, kanał do podmiotu; automatyczne przypisania analityk potwierdza. Zasila Podmiot 360 i rozmiar kropki w macierzy ryzyka | 2–3 h | zgodność 20% (M1: „dane podmiotu reklamującego”), atrakcyjność 10% | pomysł Szymona, 2026-11-21 21:19 |

Metryki zaakceptowane do makiety (Szymon): lejek statusów, heatmapa podmioty × reguły, odsetek materiałów bez naruszeń w czasie, donut źródeł, macierz ryzyka (scatter). Odrzucone: czas od wykrycia do decyzji; na razie odrzucone: reklamy własne vs u osób trzecich i top promotorzy.

Makieta P7–P9 i całego UI: https://claude.ai/artifact/7C1JhKBJsxsHzWkQ4mxM3c (Dashboard, Karta dowodowa M2, Panel kalibracji; podmioty fikcyjne, liczby przykładowe).

Pokryte w innych pracach (nie rozwijam): P1 gold set → Wow #5; P2 render 3 viewporty → D3 + Wow #1; P3 tryb replay → Feasibility §4.

## Zakwestionowane założenia

| # | Założenie | Dlaczego wątpliwe | Co zamiast |
|---|---|---|---|
| Z6 | „Rejestr KNF + dopasowanie po domenie rozstrzyga, czy reklamowana firma jest legalna” | polskie podmioty nie mają domen w rejestrze (R13); marka „XTB” trafia w 3 podmioty (`XTB S.A.`, `XTB Ltd`, `Forex TB Ltd`) | dopasowanie wielosygnałowe: domena z seed listy, nazwa prawna, alias; przy niejednoznaczności rekord „do weryfikacji”, nie werdykt |
| Z7 | „Obecność w rejestrze = brak naruszenia M3” | rejestr podaje zakres usług; firma bez A5 nie może doradzać (P4) | M3 = brak w rejestrze ALBO brak A5 |
| Z8 | „4 kolektory live w MVP” (Feasibility §3) | 22 h na kolektory przy budżecie z R10; Meta API zależne od weryfikacji (R12) | 2 live (WWW+SearXNG, YouTube), reszta fixture'y; w prezentacji uczciwie: „mechanizm gotowy, źródło X z nagrania” |
| Z9 | „Wyróżnik #1 w wersji pełnej 8–10 h” (Wow) | przy R10 to 15% całego budżetu; Wow sam przewiduje cięcie po 6 h | zacząć od R4+R8 (font i telefon), R5/R6 dopiero gdy core działa |
| Z10 | „Jeden threshold na cały system” | moduły mają różne rozkłady score (M2 z 18 reguł, M3 z fraz + rejestru); jeden próg da FP w jednym i FN w drugim | próg per moduł (makieta: przełącznik M1/M2/M3 w kalibracji) |
| Z11 | „Alert WebSocket = każdy rekord powyżej progu” | próg flagi ustawia się pod pełność (dużo rekordów), alert musi być rzadki | osobny próg alertu (P9) |
| Z1–Z5 | z iter. 1 | Z1 (threshold = filtr) → Wow #5; Z2 (M2 = sam LLM) → D3; Z3 (social live) → Feasibility; Z4 (rejestr rozstrzyga) → rozwinięte w Z6; Z5 (proces AI) → Wow sekcja proces | zamknięte |

## Historia iteracji

- 2026-11-21 13:45, iter. 1: repo `UKNF` tylko `main` (3 commity), brak gałęzi i worktree innych sesji, notatki wspólne puste; dodano R1–R9, P1–P3, Z1–Z5.
- 2026-11-21 14:20, iter. 7: bez zmian w repo, gałęziach i plikach sesji od iter. 6; pętla zatrzymana o 14:20 zgodnie z poleceniem.
- 2026-11-21 14:16, iter. 6: bez zmian w repo i plikach sesji; dodano R21 (materiały formalne poza budżetem), P13; w makiecie link „Podmiot” we wszystkich planszach.
- 2026-11-21 14:15, iter. 5: bez gałęzi; nowa D7 (napisy YouTube w scraperze, whisper jako fallback) pokrywa Wow #4 tanim wariantem; dodano R20, P12, plansza „Podmiot” w makiecie (P4 na danych rejestru).
- 2026-11-21 14:12, iter. 4: bez gałęzi; nowa D6 (ekstrakcja w scraperze, embedding i dopasowanie KNF w preprocessingu) zawęża P5; dodano R18–R19, P10–P11.
- 2026-11-21 14:10, iter. 3: bez gałęzi; nowa decyzja D5 (scraper i preprocessing osobno, przez kolejkę); zbudowana makieta UI, z niej R17, P7–P9, Z10–Z11.
- 2026-11-21 14:00, iter. 2: nadal brak gałęzi; pojawiły się Feasibility, Wow, DECYZJE D1–D4 i rejestr KNF (760 podmiotów) poza gitem; P1–P3 pokryte gdzie indziej, dodano R10–R16, P4–P6, Z6–Z9.
