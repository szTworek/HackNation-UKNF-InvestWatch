# Strony WWW firm inwestycyjnych w module 2: zakres, reguły, wykonalność, prototyp

Stan na 2026-11-22. Kolektor: `scrapers/poc/firm_web/collect_site.py`. Dane: `data/samples/firm_web_v1.jsonl` (9 rekordów), pomiary `scrapers/poc/results/firm_web/blocks/*.json`, screenshoty `scrapers/poc/results/firm_web/shots/` (39 plików, 52 MB, poza gitem), przebieg `scrapers/poc/results/firm_web/summary.json`.

Oznaczenia: **[S]** sprawdzone (źródło, komenda, plik); **[W]** wniosek, niezweryfikowany.

## 1. Zakres: strony WWW firm są w M2

- [S] Opis wyzwania, Moduł 2 (`pliki_dc/markdown/Opis Wyzwania HackNation UKNF 19.11.md:16`): zakres to „materiały marketingowe publikowane bezpośrednio przez zarejestrowane w Polsce firmy inwestycyjne (w tym polskie oddziały firm zagranicznych)”. Strona WWW firmy to materiał publikowany bezpośrednio przez firmę. M1 obejmuje treści podmiotów trzecich, więc kanał firmowy pasuje do M2, a nie do M1.
- [S] Art. 44 ust. 1 rozporządzenia delegowanego 2017/565 (EUR-Lex, CELEX 32017R0565, wersja PL, przeczytane 2026-11-21) obejmuje informacje, które firma „kieruje do klientów … albo rozpowszechnia w sposób umożliwiający takim klientom dotarcie do tych informacji, w tym publikacje handlowe”. Publiczna strona WWW firmy się w tym mieści.
- [S] Art. 24 ust. 3 MiFID II (CELEX 32014L0065, PL): informacje „muszą być rzetelne, wyraźne i niewprowadzające w błąd. Publikacje handlowe oznacza się wyraźnie jako publikacje handlowe”.
- [W] Firmy z PoC to podmioty z rejestru KNF (`data/knf_entities.json` w sesji `knf-registry`): „XTB S.A.” (dom maklerski), „Etoro (Europe) Ltd”, „Plus500CY Ltd” / „Plus500EE AS”, „Trading 212 EU GmbH” / „Trading 212 Markets Ltd”, „Revolut Securities Europe UAB” (firmy zagraniczne bez oddziału). Którą spółkę obsługuje polski klient danej marki, nie sprawdzałem. W polu `author` przyjąłem jedną spółkę na markę.

## 2. 18 reguł załącznika na stronie WWW

Klasy sprawdzalności:
- **tekst**: regex albo LLM na `text.page`;
- **pomiar**: DOM i screenshot z kolektora, deterministycznie;
- **klik**: wymaga interakcji (rozwinięcia, przejścia linku);
- **ocena**: automat wskazuje kandydatów, werdykt wydaje człowiek albo LLM.

Brzmienie art. 44 w kolumnie „Przepis” jest [S] (EUR-Lex PL, art. 44 ust. 1–8 przeczytane w całości). Źródło: https://eur-lex.europa.eu/legal-content/PL/TXT/HTML/?uri=CELEX:32017R0565 (pobrane przez Playwright, curl nie dostał odpowiedzi).

| id | Reguła | Przepis | Sprawdzalność na WWW | Sygnał w danych |
|---|---|---|---|---|
| 1 | Identyfikacja firmy | ust. 2 lit. a: „informacje zawierają nazwę firmy inwestycyjnej” | tekst | nazwa i aliasy z rejestru KNF w `text.page` (zwykle stopka) |
| 2 | Oznaczenie reklamy | art. 24 ust. 3 MiFID II: „Publikacje handlowe oznacza się wyraźnie jako publikacje handlowe” | tekst + ocena | regex „materiał marketingowy / reklama / komunikat marketingowy”; czy cała strona firmy wymaga etykiety, to interpretacja prawna |
| 3 | Ryzyko przy zyskach | ust. 2 lit. b: zagrożenia sygnalizuje się „w sposób rzetelny i wyraźny … przy wskazywaniu potencjalnych korzyści” | tekst + pomiar | bloki `profit` (PROFIT_RE) i `risk` (RISK_RE); „towarzyszy” = odległość `first_profit_y` od `first_risk.y` oraz `fixed` (pasek przyklejony do ekranu) |
| 4 | Rozmiar czcionki ryzyka | ust. 2 lit. c: czcionka „o rozmiarze co najmniej równym rozmiarowi czcionki wykorzystywanemu w przeważającej mierze” | pomiar | `font_ratio` = `font_px` ÷ `dominant_font_px` (moda ważona liczbą znaków); wariant `dominant_font_px_main` bez stopki i sekcji legal |
| 5 | Ekspozycja i kontrast | ust. 2 lit. c: „układ zapewniający, że wskazanie to jest wyraźne”; lit. e | pomiar (próg w panelu) | `contrast` (DOM), `contrast_px` (tło z pikseli screenshotu), `contrast_px_p10` (najgorsze 10% tła), `occluded_frac` + `occluded_by` (5 punktów `elementFromPoint`) |
| 6 | Ukrywanie | ust. 2 lit. e: „nie ukrywa się, nie umniejsza ani nie przedstawia w sposób niejasny” | pomiar (progi w panelu) | `in_footer`, `legal_hint` (przodek z klasą legal/disclaimer/footnote/risk), `y_ratio`, `above_fold`, znacznik przypisu (`¹…⁴`) |
| 7 | Dostępność za 1 kliknięciem | ust. 2 lit. b i e | pomiar + klik | blok w DOM z `visible=false` (wariant zwinięty), tekst ryzyka tylko pod linkiem (np. PDF XTB); pełna weryfikacja wymaga kliknięcia, kolektor tego nie robi |
| 8 | Responsywność | ust. 2 lit. g: „aktualne i odpowiednie do wykorzystanego środka porozumiewania się” | pomiar | widok 375: `visible`, `font_px`, `truncated`, `offscreen_x`, `horizontal_overflow`, `above_fold` |
| 9 | Zrozumiałość | ust. 2 lit. d: „odpowiedni i zrozumiały dla przeciętnego przedstawiciela grupy” | ocena | LLM i wskaźnik czytelności jako proxy; prawo nie daje progu |
| 10 | Spójność językowa | ust. 2 lit. f: „konsekwentnie przedstawione w tym samym języku” | tekst | język `text.page` vs `text.risk_disclaimer`, `html_lang`, żądane `pl-PL` vs język odpowiedzi |
| 11 | Porównania | ust. 3 lit. a–c: porównanie miarodajne, podane źródła, fakty i założenia | tekst + ocena | wykrycie: „najlepszy”, „nr 1”, „award-winning”, „tańszy niż”; obecność przypisu ze źródłem; rzetelność ocenia człowiek |
| 12a | Wyniki historyczne: okres | ust. 4 lit. b–c: 5 lat, pełne okresy 12-miesięczne, okres referencyjny i źródło | tekst + ocena | regex lat i stóp zwrotu; wyniki w obrazkach/canvas wymagają OCR; kursy na żywo („0.00%”) to fałszywe trafienia |
| 12b | Wyniki historyczne: waluta, opłaty | ust. 4 lit. e–f | tekst | regex ostrzeżenia kursowego i wpływu opłat, uruchamiany tylko po trafieniu 12a |
| 13 | Dominacja wyników historycznych | ust. 4 lit. a: wskazanie wyników „nie jest najwyraźniejszym elementem” | pomiar + ocena | `font_px` i pole bboxa bloku z wynikiem vs reszta strony; zależy od wykrycia 12a |
| 14 | Ostrzeżenie przy wynikach | ust. 4 lit. d: „wyniki w przeszłości nie stanowią pewnego wskaźnika na przyszłość” | tekst | regex „wyniki osiągnięte w przeszłości nie (są / stanowią)…” blisko bloku z wynikiem |
| 15 | Prognozy | ust. 6 lit. e: ostrzeżenie, że prognozy „nie stanowią pewnego wskaźnika” | tekst + ocena (+ klik) | LLM do wykrycia prognoz + regex ostrzeżenia; kalkulatory zysku w JS wymagają interakcji |
| 16 | Informacja podatkowa | ust. 7: opodatkowanie „zależy od indywidualnej sytuacji każdego klienta i może ulec zmianie” | tekst | regex „IKE / IKZE / podatek / zwolnienie” i osobno regex klauzuli „indywidualnej sytuacji” |
| 17 | Aprobata organu | ust. 8: nie używa się nazwy organu w sposób sugerujący, że organ „zatwierdził lub zaaprobował” | tekst + ocena | regex nazw organów (KNF, CySEC, FCA, Bank Litwy) + LLM do kontekstu; sama informacja o licencji nie narusza przepisu |
| 18 | Nadzór jako argument bezpieczeństwa | ust. 8 | tekst + ocena | nazwa organu i „bezpieczn* / chronion* / gwarant*” w tym samym lub sąsiednim bloku |

Podsumowanie:
- Z samego pomiaru: 4, 5, 6, 8 (wow #1).
- Z samego tekstu: 1, 10, 14, 16, a 12b po trafieniu 12a.
- Automat wskazuje kandydatów, werdykt wydaje człowiek albo LLM: 2, 3, 7, 11, 12a, 13, 15, 17, 18.
- Tylko ocena: 9.

[W] Ostrzeżenie „X% rachunków inwestorów detalicznych…” to wymóg z decyzji interwencyjnych ESMA/KNF dla CFD, a nie z art. 44. Jego źródła nie czytałem.

## 3. Wykonalność: 5 firm, wersje PL

Przebiegi 2026-11-21/22, headless Chromium (Playwright 1.65.2), `locale=pl-PL`, przerwy 2–5 s między stronami. Dla każdej podstrony 3 konteksty: 1440×900, 768×1024, 375×812 (mobile UA, `is_mobile`).

| Firma | URL-e PL (sprawdzone) | robots.txt | Render / blokady | Baner cookies | Znaleziony disclaimer (1440 → 375) |
|---|---|---|---|---|---|
| XTB S.A. | `xtb.com/pl`, `/pl/indeksy-gieldowe`, `/pl/etf`, `/pl/odsetki` | [S] 200, wszystkie dozwolone (Disallow tylko `/liquidity`, `/front-api/*`, parametry `?utm`, `?cur=`) | [S] renderuje się, 200; pojedyncze timeouty, powtórka OK | [S] brak „odrzuć” w pierwszej warstwie („Ustawienia” / „Akceptuję wszystkie”); w drugiej tylko przełączniki i „Zapisz ustawienia”; **baner zostawiony** | pasek „Kontrakty CFD są złożonymi instrumentami… 79% rachunków inwestorów detalicznych odnotowuje straty…”, `sticky` y=0; font 16/16 px = 1,0 (768: 16/14 = 1,14; 375: 14/14 = 1,0); `contrast_px` 14,2 (strona główna, tekst na zdjęciu: p10 = 3,2); na podstronach 9,7–10,5; widoczny na telefonie: tak |
| Etoro (Europe) Ltd | `etoro.com/pl/` (zebrane), `/pl/trading/cfd/`, `/pl/investing/interest-on-balance/`, `/pl/invite/` | [S] 200, dozwolone; `Disallow: /referral*`, `/TJoin*`, `/partners/*` (linki polecające poza zakresem) | [S] `/pl/invite/`: wyzwanie DataDome (`iframe#ddChallengeBody…`), pominięte; po ~25 wczytaniach w ~1 h Cloudflare „Access denied”, HTTP 429 dla `/trading/cfd/` i `/interest-on-balance/` | [S] OneTrust „Odrzucenie wszystkich” kliknięte; baner pojawia się z opóźnieniem, kolektor próbuje 3× | strona główna: górny pasek „Wartość Twoich inwestycji może wzrosnąć lub spaść. Twój kapitał jest zagrożony.”, `sticky`, 14 px vs 16 px głównej treści (ratio 0,88), 375: 12/14 = 0,86, `contrast_px` 8,55; ostrzeżenie CFD „55% kont inwestorów detalicznych traci pieniądze” tylko w `<footer>`, y_ratio 0,90–0,94, 375: 12 px (0,86) |
| Plus500CY Ltd | `plus500.com/pl/` → przekierowanie na `lp.plus500.com/main/` (EN) | [S] 200 dla `www`; `Disallow: /*?*`, `/api` | [S] `www.plus500.com/pl/` i `/pl-PL/` zwracają 403, potem skrypt przenosi na angielską stronę docelową (200); polskiej strony nie widać | [S] baner bez przycisku odrzucenia | „CFDs are complex instruments… 82% of retail investor accounts lose money…”, `sticky` y=8, 16/16 = 1,0, 375: 14/14 = 1,0, `contrast_px` 11,8–13,3 |
| Trading 212 | `trading212.com/pl` | [S] robots.txt też za wyzwaniem (403 „Just a moment…” dla curl, 403 dla Playwright) | [S] Cloudflare Turnstile, tytuł „Cierpliwości…”, 403 we wszystkich viewportach; nie obchodzone | n/d | brak danych |
| Revolut Securities Europe UAB | `revolut.com/pl-PL/`, `/pl-PL/stock-trading/`, `/pl-PL/etfs/` | [S] 200, dozwolone; `Disallow: *?*` (bez parametrów), `/api/` | [S] renderuje się, 200 | [S] „Wyłącz wszystkie pliki cookie poza niezbędnymi” kliknięte (= tylko niezbędne) | podstrony: zdanie w hero „Istnieje ryzyko utraty kapitału — wartość Twoich inwestycji może wzrosnąć lub spaść”, 18 px vs 16 px głównej treści (1,13), y 181–432, `contrast_px` 15–16,5, widoczne na telefonie; strona główna: przypis „⁴INWESTYCJE: ryzyko utraty kapitału.” 12 px, y_ratio 0,61–0,69 |

[S] Wartości z eToro `/trading/cfd/` z przebiegu 2, przed blokadą (pliki nadpisane, liczby z logu tej sesji):
- pasek ryzyka `fixed`, 16 px przy dominującym 18 px: ratio 0,89 (375: 15/16 = 0,94);
- `contrast_px_p10` 2,0–2,7;
- poziome przewinięcie strony przy 1440;
- `/interest-on-balance/` (tytuł „Zarabiaj do 3,80% odsetek od salda”): ten sam pasek 16/18 = 0,89; ostrzeżenie ogólne, bez % CFD.

Kosztem powtórzenia jest ryzyko blokady IP, dlatego tych stron nie powtarzałem.

## 4. Trzy obserwacje pod demo

1. **eToro, strona główna: twarde ostrzeżenie CFD tylko w stopce, mniejszą czcionką** (reguły 3, 4, 6, 8).
   - [S] Górny pasek ma tylko ostrzeżenie ogólne (14 px vs 16 px głównej treści, ratio 0,88).
   - [S] Zdanie „55% kont inwestorów detalicznych traci pieniądze” stoi w `<footer>` na 90–94% wysokości strony i na telefonie ma 12 px (0,86).
   - [W] Czy strona główna eToro reklamuje CFD (wtedy wymóg % CFD), to ocena prawna.
   - Pliki: `shots/etoro_com_pl_375.png`, `blocks/etoro_com_pl.json`.
2. **XTB: disclaimer formalnie wzorowy, ale tekst leży na zdjęciu** (reguła 5).
   - [S] Rozmiar jest OK (ratio 1,0–1,14).
   - [S] Kontrast z DOM wynosi 1,04, bo pasek jest przezroczysty, a DOM widzi jasne tło `body`.
   - [S] Kontrast z pikseli to mediana 14,2, ale najgorsze 10% tła tylko 3,2 (hero ze zdjęciem pod paskiem).
   - [S] Kopia w stopce ma 14 px przy dominującym 16 px (0,875) i kontrast 4,12, poniżej proxy WCAG 4,5.
   - Wniosek dla M2: kontrast z DOM sam nie wystarcza, potrzebny jest pomiar z pikseli.
   - Pliki: `shots/xtb_com_pl_1440.png`, `blocks/xtb_com_pl.json`.
3. **Ta sama marka, dwa wzorce: Revolut, strona główna vs podstrony** (reguły 4 i 6; kontrprzykład do kalibracji).
   - [S] Podstrony akcji i ETF mają zdanie o ryzyku w hero, większe od treści (18 vs 16 px), na 2–5% wysokości.
   - [S] Strona główna ma ryzyko inwestycji tylko jako przypis „⁴INWESTYCJE: …” (12 px) na 61–69% wysokości strony, w bloku przypisów obok „¹ OSZCZĘDNOŚCI … oprocentowanie”.
   - Uwaga: na tej stronie pomiar dominującego fontu jest niepewny (zob. ograniczenia).

Kandydaci tekstowi, do przeglądu, a nie werdykty:
- [S] eToro: obok siebie „Chronione” i „Pod nadzorem CySEC” (reguły 17/18).
- [S] eToro: na stronie głównej w żadnym bloku tekstu nie ma „Ltd” ani „eToro (Europe)” (reguła 1; nazwa może być w obrazie albo na innej podstronie).
- [S] XTB: „Wybierz IKE i IKZE … zyskaj możliwość zwolnienia z 19-proc. podatku” bez klauzuli „indywidualnej sytuacji” na tej stronie (reguła 16).
- [S] XTB: „najlepszym domem maklerskim roku według Invest Cuffs 2025 oraz jesteśmy regulowani przez renomowane instytucje nadzoru” (reguły 11, 17).
- [S] Plus500: „award-winning trading platform¹” i „Globally Licensed & Regulated” z listą organów (reguły 11, 17); przy żądaniu `pl-PL` treść po angielsku (kontekst reguły 10).
- [S] Revolut: „nr 1 pod względem liczby pobrań”, „Najlepszy bank cyfrowy na świecie w 2025 roku” (reguła 11).
- [S] eToro: w obrazie hero „Profitable 4+ years in a row”, „Return (2Y) +96.35%”. To wyniki historyczne poza DOM (reguły 12a/13), widoczne tylko na screenshocie; wymagają OCR.

## 5. Co z tego daje wow #1 (wizualny audyt reguł 4/5/6/8)

- [S] Mechanizm działa na prawdziwych stronach 3 z 5 firm (XTB, eToro, Revolut) oraz na angielskiej stronie docelowej Plus500. Dla każdej strony i viewportu jest pełny screenshot i JSON z bboxami, więc ramki z etykietami („R4: 12 px vs 14 px = 0,86×”, „R5: kontrast p10 3,2:1”) da się narysować na `shots/*.png` bez ponownego pobierania.
- [S] Gotowe do demo przypadki:
  - eToro: stopka na telefonie (R4 + R6 + R8);
  - XTB: tekst na zdjęciu (R5);
  - Revolut: przypis vs hero (R6, kontrprzykład).
- [W] Na pokaz pewniejsze są lokalne strony testowe z zadanymi naruszeniami (`docs/wow-ideas.md`), a strony firm jako „dowód na żywo”. Powody: eToro po kilkudziesięciu wczytaniach zwraca 429, Trading 212 ma Turnstile, a Plus500 nie pokazuje wersji PL.
- Do zrobienia w M2/kolektorze (nie zrobione):
  1. widoczność mierzona po `scrollIntoView` każdego bloku: animacje przy przewijaniu chowają treść (`opacity: 0`); na stronie głównej Revolut nad y = 6000 widocznych jest tylko 17 bloków (na całej stronie jest ich 245), przez co dominujący font wychodzi 12 px;
  2. `occluded_by` z banerem cookies traktować jako „niepewne”: na XTB baner zostaje, bo nie ma przycisku odrzucenia;
  3. kontrast przy `bg_image` / p10 < 4,5 oznaczać „niepewny”, nie „naruszenie”;
  4. wykrywanie ryzyka przez regex ma luki: pierwsza wersja zgubiła „Twój kapitał jest zagrożony”; potrzebny fallback LLM;
  5. PROFIT_RE łapie tekst banera cookies (eToro, y=690).

## 6. Prototyp: jak uruchomić i co zapisuje

```
cd scrapers/poc
.venv/Scripts/python.exe firm_web/collect_site.py                 # domyślne 13 URL-i (FIRMS/URLS w pliku)
.venv/Scripts/python.exe firm_web/collect_site.py https://www.xtb.com/pl
```

- Interfejs: `collect(query, notes)`; `query` = lista URL-i albo string z przecinkami. Moduł nie jest wpięty w `registry.py`, a `common.run`/`missing_core` oczekują `text` jako listy sekcji (stara wersja D14).
- Rekord (D12–D15):
  - `source="firm_website"`;
  - `source_url` = URL końcowy po przekierowaniu;
  - `author` = spółka z rejestru KNF;
  - `published_at=null`;
  - `query_keywords=[URL]`;
  - `content_keywords=[]`;
  - `text={"page": widoczny tekst 1440, "risk_disclaimer": wybrany blok}`.
- `source_meta`:
  - `robots`, `cookies` per viewport;
  - `screenshot_refs`, `text_blocks_ref`;
  - `risk_by_viewport`: `dominant_font_px`, `dominant_font_px_main`, `first_profit_y`, `horizontal_overflow`, `disclaimer{…}`, `first_risk{…}`.
- `blocks/<slug>.json`: pełne `text_blocks` dla 3 viewportów. Pola: `font_px`, `font_px_min`, `color`, `bg`, `bg_image`, `contrast`, `contrast_px`, `contrast_px_p10`, `bbox`, `visible`, `above_fold`, `offscreen_x`, `truncated`, `fixed`, `in_footer`, `legal_hint`, `risk`, `profit`, `occluded`, `occluded_frac`, `occluded_by`.
- Zasady:
  - stron z `Disallow` w robots.txt nie pobiera;
  - przy wyzwaniu (Cloudflare, Turnstile, DataDome, captcha) zapisuje `blocked` i screenshot `*_blocked.png`, bez obchodzenia;
  - cookies klika tylko „odrzuć” / „tylko niezbędne” / „wyłącz wszystkie … poza niezbędnymi”.
- Czas: ok. 60–80 s na URL (3 viewporty, przewinięcie strony dla lazy-load, pełne screenshoty). Pełny przebieg 13 URL-i: 13,5–17,5 min.
