# Źródła social media i reklam: wyniki testów PoC

Stan na 2026-11-21. Kod: `UKNF/scrapers/poc/`. Każdy moduł ma ten sam interfejs `collect(query, notes) -> Iterable[RawDocument]` i jest wpisany do rejestru `UKNF/scrapers/poc/registry.py`. Rekord to koperta RawDocument (D2: wspólne pola + `source_meta`) z `UKNF/scrapers/poc/common.py`.

Uruchamianie z katalogu `UKNF/scrapers/poc`:

```
.venv/Scripts/python -m registry                          # lista modułów i wariantów
.venv/Scripts/python -m registry youtube_posts forex      # domyślny wariant modułu
.venv/Scripts/python -m registry google_ads.atc_rpc xtb.com
```

Każde uruchomienie zapisuje rekordy i podsumowanie (czas, liczba rekordów, błędy, notatki) do `UKNF/scrapers/poc/results/<kolektor>/` (w `.gitignore`).

Oznaczenia: **[S]** sprawdzone uruchomieniem (liczby z `results/`), **[W]** wnioskowane bez testu.

Uwaga do czasów: między ok. 15:30 a 16:00 sieć tej maszyny miała timeouty do Google i Facebooka. Pojedyncze wolne przebiegi z tego okna (np. YouTube 43,9 s) są opisane osobno.

## 1. Tabela

| Moduł | Rekomendowany kolektor (wariant) | Wynik testu | Wymagania | Ryzyka | Demo na żywo |
|---|---|---|---|---|---|
| `youtube_posts` | `youtube_posts.data_api` (YouTube Data API v3) | **Działa [S]**: `forex` 10, `kod polecający XTB` 10, `inwestowanie` 13 rekordów; 13,4 s (pierwsze), 0,9 s, 1,8 s. Wyniki z PL (`regionCode=PL`); pole `has_paid_product_placement` = True u 3 z 10 filmów; w opisach kody polecające (np. „kod referencyjny XTB: NPF”) | `YOUTUBE_API_KEY` w `UKNF/.env` (jest: projekt Google Cloud `inwestwatch-poc`, klucz ograniczony do YouTube Data API); 101 jednostek na zapytanie, limit 10 000/dzień, czyli ok. 99 zapytań | limit kwoty | **tak**, ok. 1–2 s |
| `youtube_posts` | `youtube_posts.ytdlp` (bez klucza) | **Działa [S]**: 30 rekordów (3 frazy × 10) w 5,0 s i 4,9 s; przez rejestr 10 rekordów w 1,6 s (i 43,9 s w oknie problemów sieci). Tryb `full=True`: napisy 0/15 (`IpBlocked`, potem HTTP 429) | nic | regulamin YouTube zabrania zbierania poza API; wyniki nie są z PL; opis ucięty | zapas |
| `tiktok_posts` | `tiktok_posts.embed_ytdlp`: strona embed twórcy `tiktok.com/embed/@konto` (curl_cffi) daje ostatnie filmy, yt-dlp metadane filmu | **Działa [S]**: 10 filmów (`@etoro_official`, `@revolut` × 5) w 14,2 s, 12,4 s, 20,4 s; jeden przebieg z timeoutem (okno problemów sieci) | nic; query = `@konto[,@konto]` | tylko konta z listy; brak wyszukiwania po frazie bez logowania; `robots.txt` TikToka zabrania `*` poza `/foryou`, `/discover`, `/about`; `@xtb_pl` to konto prywatnej osoby, nie brokera | **tak** |
| `tiktok_posts` | `tiktok_posts.tiktokapi` (hashtag `#inwestowanie`) | **Nie [S]**: `EmptyResponseException` („detecting you're a bot”) w 2 przebiegach | opcjonalnie `TIKTOK_MS_TOKEN` (cookie `msToken` z przeglądarki, bez logowania) | obchodzenia detekcji nie robimy | nie |
| `ig_posts` | `ig_posts.session`: Playwright z zapisaną sesją (`python -m login ig`), przechwytuje JSON strony hashtagu, profilu lub wyszukiwania | **Czeka na logowanie Szymona** | konto testowe IG; sesja w `UKNF/.secrets/ig_state.json` (w `.gitignore`) | łamie regulamin IG; ryzyko checkpointu lub bana konta testowego; RODO; zakres: kilka zapytań | po teście |
| `ig_posts` | `ig_posts.instaloader_anon` (bez logowania) | **Nie [S]**: przebiegi 1–2 dały metadane profili (np. `xtb_polska`, 44 788 obserwujących), posty `BadResponseException`, hashtag 404; przebiegi 3–4: HTTP 429 | nic | limit po ok. 10 żądaniach | nie |
| `ig_posts` | `ig_posts.graph_api` (Business Discovery, Hashtag Search) | nie testowane | konto IG Business + strona FB + aplikacja Meta + token | widzi tylko konta firmowe; 30 hashtagów / 7 dni | — |
| `fb_posts` | `fb_posts.session`: Playwright z zapisaną sesją (`python -m login fb`), wyszukiwarka postów lub strona `@XTBPL`, bloki `[role=article]` | **Czeka na logowanie Szymona** | konto testowe FB; `UKNF/.secrets/fb_state.json` | łamie regulamin Meta (pkt 3.2.3); ryzyko checkpointu; RODO | po teście |
| `fb_posts` | `fb_posts.no_login_probe` | **Częściowo [S]**: httpx 400 (www, m, mbasic); Playwright 1 post z tekstem (ucięty) i ściana logowania; 4 przebiegi, 9,7–13,7 s | nic | jw. | nie |
| `x_posts` | `x_posts.session`: Playwright z zapisaną sesją (`python -m login x`), wyszukiwanie „Najnowsze”, przechwycenie GraphQL `SearchTimeline` | **Czeka na logowanie Szymona** | konto testowe X; `UKNF/.secrets/x_state.json` | łamie regulamin X; ryzyko blokady konta | po teście |
| `x_posts` | `x_posts.no_login_probe` | **Nie [S]**, 2 przebiegi: syndication 429, `nitter.net` 200 bez tweetów, RSS 410, `xcancel.com` 451, `x.com/XTB_PL` 404, API bez tokenu 401 | nic | — | nie |
| `x_posts` | `x_posts.api_recent_search` (X API v2) | nie testowane | `X_BEARER_TOKEN`; pay-per-use ok. 0,005 USD/post **[W]** | koszt | — |
| `fb_ads` | `fb_ads.ad_library_api` (Meta Ad Library API, `/ads_archive`, kraj PL, pola `beneficiary_payers`, `eu_total_reach`) | nie testowane, czeka na token | `META_ACCESS_TOKEN`: konto FB z weryfikacją tożsamości (1–3 dni **[W]**) + aplikacja Meta | brak, oficjalny kanał DSA | tak **[W]** |
| `fb_ads` | `fb_ads.ad_library_web` (strona Ad Library, Playwright, bez logowania) | **Działa [S]**: `forex` 25 reklam w 9,6 s, 9,1 s, 11,6 s; `kod polecający XTB` 0. Przykład: reklama „Reelsgoldhunter” obiecująca sygnały forex (przypadek M3) | nic | łamie regulamin Meta (automatyzacja poza API); tylko pierwszy ekran (25) | tak (pokaz) |
| `fb_ads` | `fb_ads.ytdlp_by_id`: ekstraktor yt-dlp `facebook:ads` po ID reklamy (pomysł z repo fejker) | **Częściowo [S]**: 5 ID z `ad_library_web` → 2 rekordy z pełnym tekstem, reklamodawcą i plikiem wideo (do whispera), 4,1 s i 3,8 s; reklamy obrazkowe: „No video formats found” | nic | jak `ad_library_web` | tak, jako drugi krok |
| `google_ads` | `google_ads.atc_rpc`: wewnętrzne RPC Google Ads Transparency Center (`SearchSuggestions`, `SearchCreatives`, region PL = 2616) przez curl_cffi, bez przeglądarki; kształt zapytań z repo fejker | **Działa [S]**: `XTB` → reklamodawcy `XTB S.A.` (PL, 3000–4000 reklam) i `XTBL B.V.` (NL); 80 kreacji (2 strony po 40) w 53,0 s i 21,6 s; `xtb.com` → 76 kreacji w 23,5 s | nic, brak oficjalnego API, brak `robots.txt` | głównie obrazy (OCR), tekst reklam tekstowych trzeba dociągnąć z podglądu; nieoficjalne RPC może się zmienić | **tak** |
| `google_ads` | `google_ads.atc_playwright` (Playwright przechwytuje to samo RPC) | **Działa [S]**: 160 kreacji (XTB S.A. 80, eToro Group Ltd. 80; 126 obrazów, 34 tekstowe) w 17,5 s i 17,9 s | nic | wolniejszy od `atc_rpc` | zapas |
| `bing_ads` (nowe) | `bing_ads.ms_adlib`: Microsoft Ad Library REST API, bez klucza, kraj PL = 151 (endpoint z repo fejker) | **Działa [S]**: `forex` 10 reklam w 10,1 s, 5,5 s, 1,4 s (np. „Swissquote Bank SA”, tytuł, opis, URL docelowy); `top=25` zwraca HTTP 400 | nic | — | **tak** |
| `x_ads` | `x_ads.ads_repository_probe` (X Ads Repository przez Playwright, kraj PL, zakres „This year”, eksport CSV) | **Częściowo [S]**: strona działa bez logowania i podpowiada konta; `@xtb`: „No ads found”; raport dla `@etoro` nie skończył się w 60 s ani w 240 s; link „Commercial Communications CSV” zwraca 404 | nic | wyszukiwanie tylko po koncie; eksport trwa minuty albo wcale | nie |
| `tiktok_ads` | `tiktok_ads.library_probe` | **Nie [S]**: `library.tiktok.com/ads` działa bez konta, ale `robots.txt` zabrania `/ads` i `/api`; Creative Center przekierowuje na stronę z „Log in” | API CCL: wniosek badawczy | brak legalnej ścieżki automatycznej | nie |

Kandydat odrzucony bez testu: `google-ads-transparency-mcp 0.3.0`. `atc_rpc` robi to samo bez nowej zależności nieznanego autora. BigQuery `bigquery-public-data.google_ads_transparency_center` wymaga konta Google i zbiór jest niepełny względem strony **[W]**, więc zostaje jako opcja eksportu jednorazowego.

## 2. Rekomendowany zestaw na PoC

| Moduł | Kolektor | Status | Rola w demo |
|---|---|---|---|
| `youtube_posts` | `data_api` | działa [S] | zapytanie na żywo (M1: kody polecające, płatna współpraca; M3) |
| `tiktok_posts` | `embed_ytdlp` | działa [S] | na żywo dla kont z listy |
| `google_ads` | `atc_rpc` | działa [S] | na żywo po nazwie reklamodawcy z rejestru KNF albo domenie (M1, M2) |
| `bing_ads` | `ms_adlib` | działa [S] | na żywo po frazie (M2, M3) |
| `fb_ads` | `ad_library_api`; do czasu tokenu `ad_library_web` + `ytdlp_by_id` | web działa [S], API czeka | M1 (`beneficiary_payers`), M2, M3 |
| `fb_posts`, `ig_posts`, `x_posts` | `session` | czeka na logowanie | kilka zapytań na koncie testowym, wynik zapisany jako fixture |

Wpięcie produkcyjnego źródła UKNF: nowy plik z funkcją `collect(query, notes)` zwracającą tę samą kopertę i wpis w `registry.MODULES`. W docelowym module Celery każdy wariant to zadanie: `fetch_http` dla API, curl_cffi i yt-dlp, `fetch_browser` dla Playwrighta (D9) **[W]**.

## 3. Kroki dla Szymona

Sekrety idą do `UKNF/.env`, sesje do `UKNF/.secrets/`. Oba są w `UKNF/.gitignore`, nie commitujemy ich.

1. **Sesje FB, IG, X (konta testowe)**, ok. 5 min na platformę. Z katalogu `UKNF/scrapers/poc`:
   ```
   .venv/Scripts/python -m login fb
   ```
   Otworzy się okno Chrome. Logujesz się sam kontem testowym (hasło, kod 2FA, ewentualna captcha to Twoje kroki). Potem wracasz do terminala i wciskasz Enter, a sesja zapisuje się do `UKNF/.secrets/fb_state.json`. To samo z `ig` i `x`. Potem testuję `fb_posts`, `ig_posts`, `x_posts` po 2 razy. Checkpoint lub captchę w trakcie testu zapiszę jako wynik.
2. **Meta Ad Library API** (`META_ACCESS_TOKEN`). Weryfikacja tożsamości trwa podobno 1–3 dni, więc warto zacząć teraz.
   1. https://www.facebook.com/ads/library/api → „Get started” → zaloguj się → „Confirm your identity & location” (dokument).
   2. https://developers.facebook.com/apps → „Create app” (typ „Other” / „Business”).
   3. https://developers.facebook.com/tools/explorer → wybierz aplikację → „Generate Access Token”. Token żyje 1–2 h; „Access Token Debugger” → „Extend Access Token” daje 60 dni.
   4. `UKNF/.env`: `META_ACCESS_TOKEN=<token>`.
3. **Opcjonalnie X API** (`X_BEARER_TOKEN`, płatne): https://console.x.com → projekt i aplikacja → metoda płatności i limit wydatków → „Keys and tokens” → „Bearer Token” → `UKNF/.env`.
4. **Opcjonalnie TikTok** (`TIKTOK_MS_TOKEN`): tiktok.com bez logowania → F12 → Application → Cookies → wartość `msToken` → `UKNF/.env`.

Zrobione: `YOUTUBE_API_KEY`. Projekt Google Cloud `inwestwatch-poc` założyłem w Twoim Chrome po Twoim „tak”, a 2FA na koncie Google włączyłeś sam.

## 4. Środowisko i zależności

- Venv `UKNF/scrapers/poc/.venv` (Python 3.13, `uv`), zależności w `UKNF/scrapers/poc/requirements.txt`: curl-cffi 0.17.0, httpx 0.28.1, instaloader 4.16, playwright 1.65.2, python-dotenv 1.2.4, selectolax 1.0.2, tiktokapi 7.3.5, youtube-transcript-api 1.2.5, yt-dlp 2026.10.26.
- `pip-audit -r requirements.txt` i `pip-audit` całego venv: „No known vulnerabilities found” **[S]**.
- Na tej maszynie pełny Chromium Playwrighta (`chrome-win64/chrome.exe`) nie startuje (`spawn UNKNOWN`), działa `chromium_headless_shell` i systemowy Chrome (`channel="chrome"`). Dlatego `login.py`, kolektory `session` i `tiktokapi` używają systemowego Chrome **[S]**.

## 5. Źródła
- Meta Ad Library API: https://developers.facebook.com/docs/graph-api/reference/ads_archive/
- X API pay-per-use (strony trzecie, do potwierdzenia w https://docs.x.com): https://dev.to/xcropio/twitter-x-api-pricing-2026-pay-per-use-rates-enterprise-and-cost-per-tweet-2eam, https://www.socialcrawl.dev/blog/x-twitter-api-2026
- X Ads Repository: https://business.x.com/en/help/ads-policies/product-policies/ads-transparency
- Google ATC, brak API, spór o `region` (vendor): https://dev.to/devil_scrapes/google-ads-transparency-scraper-pull-any-competitors-ads-for-3011k-5f7f
- Repo fejker (endpointy Microsoft Ad Library, RPC Google ATC, yt-dlp `facebook:ads`): `C:\Users\szymo\Documents\projects\hacknation\fejker\ftf\sources.py:52-141`
- Wcześniejszy research: `C:\Users\szymo\Documents\projects\hacknation\inwestwatch\docs\sources-feasibility.md`
