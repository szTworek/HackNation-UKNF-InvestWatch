# Review: hacknation-2026-solutions/fejker

Data: 2026-11-21. Klon: `C:\Users\szymo\Documents\projects\hacknation\fejker` (commit `9528070`, jeden commit).
Legenda: **[test]** = uruchomione dziś przez nas, z liczbami; **[kod]** = przeczytane w źródle; **[wniosek]** = nasza interpretacja.

## Co to jest

**[kod]** To nie scraper postów, tylko FakeTrace: rozwiązanie innego wyzwania (NASK „Kolekcjoner Fejków”). Łączy oszukańcze reklamy w kampanie po wspólnych śladach: piksele, TDS (systemy przekierowań ruchu), domeny, pHash, CLIP, twarze i tekst. Pozyskiwanie danych to jeden plik, `ftf/sources.py` (148 linii), plus `ftf/capture.py` (pobranie strony docelowej w 3 profilach klienta).
- Platformy: **brak** postów organicznych z X, FB, IG, TikToka i YouTube (`grep` po `instagram|tiktok|twitter|ytsearch` znajduje tylko listy domen trackerów w `ftf/web.py:28-49`). Są: lista CERT PL, Microsoft Ad Library, Google Ads Transparency Center (ATC), Meta Ad Library (API z tokenem albo yt-dlp po ID reklamy) i LinkedIn Ad Library.
- Technika: zwykłe `requests` (bez przeglądarki), yt-dlp jako podproces, opcjonalnie Playwright tylko do renderu strony docelowej (`ftf/capture.py:100-123`). Żadnych kont ani cookie.
- Architektura: harmonogram APScheduler (`ftf/scheduler.py`), storage SQLite (`ftf/store.py`), pliki w `data/artifacts/` na dysku, wyjście jako luźne dicty per źródło, bez wspólnego kontraktu. UI to FastAPI + React.
- Bezpieczeństwo: `pip-audit -r requirements.txt` → „No known vulnerabilities found”; `npm audit --package-lock-only` → 4 moderate (`minimatch` przez `shadcn`/`ts-morph`, tylko narzędzia deweloperskie). Brak hooków git i skryptów instalacyjnych w paczkach Pythona. **Uwaga:** `ftf/llm.py:127` przy `FTF_LLM=auto` (domyślnie) woła lokalne `claude -p` na subskrypcji użytkownika. Przy jakimkolwiek uruchomieniu silnika ustaw `FTF_LLM=none`. Nasze testy importowały tylko `sources` i `capture`, więc LLM nie był wołany.
- **Licencja: brak.** Repo jest PRIVATE (`gh repo view` → `licenseInfo: null`), w repo nie ma pliku LICENSE. Prawnie to „wszelkie prawa zastrzeżone”: kodu nie kopiujemy. Wolno wziąć wiedzę (kształty endpointów, parametry, pułapki) i napisać własną implementację.

## Tabela

Zapytania: `forex`, `kod polecający XTB`, `#inwestowanie`. Dwa uruchomienia (run1, run2) w osobnym venv (`python -I`), bez tokenów i cookie. Wyniki run1 i run2 są identyczne, chyba że tabela mówi inaczej.

| Platforma / źródło | Technika fejkera | Wynik testu | Dla nas | Powód |
|---|---|---|---|---|
| X posty | brak | — | — | nie istnieje w repo [kod] |
| FB posty | brak | — | — | nie istnieje [kod] |
| IG posty | brak | — | — | nie istnieje [kod] |
| TikTok posty | brak | — | — | nie istnieje [kod] |
| YouTube posty | brak (research wspomina yt-dlp `ytsearch`, ale kod tego nie ma) | — | — | nie istnieje [kod] |
| Meta Ad Library: wyszukiwanie | Graph API `ads_archive`, `META_ACCESS_TOKEN` (`ftf/sources.py:105-130`) | [test] bez tokenu funkcja zwraca `[]` bez żadnego requestu, 0 rekordów × 3 zapytania × 2 runy | odrzucić (mamy własny `poc/meta_ads/ad_library_api.py`) | ten sam endpoint co u nas. Wartość tylko w liście pól (`eu_total_reach`, `beneficiary_payers`) i w instrukcji zdobycia tokenu (README) |
| Meta Ad Library: kreacja po ID | yt-dlp ekstraktor `facebook:ads` (`ftf/sources.py:133-141`) | [test] run1 ID `732363262964757`: `.mp4` 303 KB + `.info.json` w 4,7 s; run2 ID `1918975318998428`: 2 pliki w 13 s. `info.json` ma `description` (pełny tekst reklamy), `uploader` („Reelsgoldhunter”), `uploader_id` (page_id), `formats`, `thumbnail`, `like_count`; nie ma daty | **zaadaptować** | bez tokenu i logowania dostajemy media i tekst reklamy do MinIO. Uzupełnia API, które nie daje plików wideo. Na Windows `shutil.which("yt-dlp")` nie znajduje `yt-dlp.exe` w venv, jeśli venv nie jest w PATH (`ftf/sources.py:135-137`) [test] |
| Google ATC: podpowiedzi | POST RPC `SearchService/SearchSuggestions` przez `requests` (`ftf/sources.py:79-89`) | [test] `forex`: 20 (reklamodawcy i domeny, np. „FOREX AB” SE, „FOREXCOM” FR), `kod polecający XTB`: 0, `#inwestowanie`: 9 (szum: `hrs.de`, `hm.com`) | zaadaptować | jedyna droga „słowo → reklamodawca” w ATC. Pełnotekstowo po treści reklam ATC nie szuka. Słowa jak hashtagi i frazy dają 0 albo szum [test] |
| Google ATC: kreacje | POST RPC `SearchService/SearchCreatives` po domenie albo `advertiser_id`, region PL `2616` (`ftf/sources.py:92-103`) | [test] `domain=xtb.com`: 40 (limit `n=40`), 26 image + 14 text, URL obrazka w 14 z 40; po `AR06684873466715308033` („XTB S.A.”): 40; czas 0,3–0,5 s | **zaadaptować** (zamiast naszego Playwrighta) | nasz `poc/google_ads/atc_playwright.py` otwiera przeglądarkę, żeby przechwycić ten sam RPC. Fejker pokazuje, że wystarczy `requests` (kolejka `fetch_http` zamiast `fetch_browser`, D9). Brak: tekstu kreacji (siedzi w `content.js`), paginacji ponad 40, `GetCreativeById` z datami i zasięgiem PL (jest tylko w `research/01`) |
| Microsoft Ad Library | GET REST `adlibrary.api.bingads.microsoft.com/api/v1/Ads`, `countryCodes=151` (`ftf/sources.py:55-66`) | [test] **błąd 400** × 3 zapytania × 2 runy: „limit of '24' for Top query… '25'”. Nasza poprawka `top=24`: `forex` 200, 24 rekordy z `DestinationUrl`; kolejne 3 zapytania dostały **429** (rate limit po ok. 8 wywołaniach w kilka minut) | zaadaptować (nowe źródło, opcjonalne) | jedyna oficjalna API reklam bez klucza z pełnym tekstem i URL docelowym. Ruch Bing w PL jest mały [wniosek], a limit 429 jest niski. Kod fejkera jest zepsuty (stały `top=25`) |
| LinkedIn Ad Library | GET HTML + regex `/ad-library/detail/(\d+)` (`ftf/sources.py:144-148`) | [test] 0 rekordów × 3 × 2. Bezpośredni GET: **HTTP 403**, 4548 B strony blokady. Kod nie sprawdza statusu, więc błąd wygląda jak „brak wyników” | odrzucić | blokada dla `requests` z tej maszyny. Poza tym nie nasza grupa docelowa (finfluencerzy) [wniosek] |
| CERT PL lista ostrzeżeń | GET `hole.cert.pl/domains/v2/domains.json`, filtr rdzeni nazw domen (`ftf/sources.py:34-52`) | [test] 74 domeny × 2 runy (z 2000 najnowszych). Trafienia: `inpost` 17, `trade` 13, `invest` 12, `news` 10; **0** trafień na nasze `forex`/`xtb`/`inwest` | zaadaptować pod M3 (podmioty spoza rejestru) | publiczne, bez klucza, dowolne użycie. Seed domen fałszywych platform inwestycyjnych do porównania z rejestrem KNF. Filtr fejkera jest zbyt szeroki (`news`, `bank`) |
| Strona docelowa (capture) | 3 profile klienta: `bot`, `desktop_pl`, `fb_mobile` z `Referer: l.facebook.com`; łańcuch przekierowań, meta refresh i JS redirect; flaga `cloaking` (`ftf/capture.py:35-97`) | [test] `xtb.com/pl`: 200, 474 092 B, ten sam łańcuch w 3 profilach → `cloaking: null`; domena z CERT `newsy2-debitis47.cfd`: nieosiągalna we wszystkich 3. Playwright nietestowany (`render=False`) | zaadaptować (pomysł) | wykrywanie cloakingu przez porównanie profili to tani sygnał dla M2/M3. Sprzeczne z D1: zapis pod `sha1(url)[:12]` nadpisuje poprzedni capture (`ftf/capture.py:65-67`) |
| TikTok/X Ads, BigQuery ATC, DSA DB | tylko opis w `research/01` | nietestowane (brak kodu) | — | `research/01` to dobra ściąga ze statusem LIVE/READ per źródło. Pokrywa się z `sources-feasibility.md` [wniosek] |

Sprzeczności z naszymi decyzjami [kod]:
- D1 (niezmienny capture): capture nadpisuje plik dla tego samego URL.
- D2 (koperta RawDocument): brak wspólnej koperty, `published_at` jest tylko w ATC (`first_shown`, epoch jako string).
- D3 (screenshoty 3 viewportów): jeden viewport 412 px.
- D4 (Postgres + MinIO): SQLite plus dysk.
- D8 i D9 (Celery z kolejkami): APScheduler w jednym procesie.
- D10 (hashe): brak `dedup_sha256` i `raw_sha256`.

Silnika fejkera jako całości nie da się więc wpiąć. Pojedyncze funkcje źródeł można przepisać na adaptery.

## Wnioski

1. Fejker nie pomaga z postami finfluencerów (X, FB, IG, TikTok, YouTube): nie ma ich wcale. Planu `fb_posts`, `ig_posts`, `x_posts`, `tiktok_posts` i `youtube_posts` nie zmienia [kod].
2. `google_ads`: zamiast Playwrighta używamy zwykłego POST do `SearchCreatives` i `SearchSuggestions` w kolejce `fetch_http`. Działa bez przeglądarki: 40 kreacji XTB w 0,3 s, powtarzalnie [test]. Własna implementacja, bo repo nie ma licencji.
3. `fb_ads`: jako drugi krok dodajemy yt-dlp `facebook:ads` po `ad_archive_id`. Daje wideo i pełny tekst reklamy bez tokenu [test, 2/2 ID]. Discovery dalej idzie przez API z tokenem Szymona albo przez naszą sondę WWW.
4. Nowe źródła do rozważenia jako adaptery `collect(query)`: `cert_pl` (seed domen pod M3, 74 domeny na run [test]) i opcjonalnie `ms_ads` (24 reklamy na zapytanie po poprawce `top=24`, ale 429 po ok. 8 wywołaniach [test]). LinkedIn odrzucamy (403 [test]).
5. Do przeniesienia jako pomysł, nie kod: profile klienta do wykrywania cloakingu przy pobieraniu strony docelowej (`fetch_http`, D3) i tokeny łączące z `research/01` (`beneficiary_payers`, `page_id`). Silnik FakeTrace (SQLite, APScheduler, brak koperty) jest sprzeczny z D1, D2, D4, D8, D9 i D10, więc go odrzucamy [kod].
