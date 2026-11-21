# InvestWatch – strategia pozyskiwania danych

Dokument dla osoby robiącej scraper. Kontrakty (`ScrapedItem`, `LandingPage`, tabele, kolejki) są w
`docs/backend-integration.md` i tu się nie zmieniają, poza propozycją z sekcji 6.

## 1. Założenie

Nie próbujemy przekonać algorytmu, żeby pokazał nam reklamy. Pytamy o nie tam, gdzie platformy muszą je ujawniać,
a organiczne treści znajdujemy zapytaniami zbudowanymi z rejestru KNF.

| Warstwa | Źródło | Moduły | Pewność | Prio |
|---|---|---|---|---|
| S0 Seedy | rejestr KNF, lista ostrzeżeń KNF, CERT | wszystkie | wysoka | 1 |
| S1 Biblioteki reklam | Meta Ad Library, TikTok Commercial Content Library, Google Ads Transparency Center | M1, M2, scam | wysoka | 1 |
| S2 Znane profile | YouTube, publiczne profile firm i finfluencerów, strony WWW firm | M1, M2, M3 | wysoka | 1 |
| S3 Discovery | wyszukiwarki z `site:` i filtrem daty | M1, M3 | średnia | 2 |
| S4 Wzbogacenie | landing pages, media | wszystkie | wysoka | 2 |

## 2. Dlaczego nie podmieniamy historii Chrome

- Plik `History` w AppData jest lokalny. Wyszukiwarka i Facebook go nie czytają, więc jego edycja nie zmienia wyników.
- Jedyna droga z historii do reklam to Topics API, a Google je wycofuje (deprecated w Chrome 144, usunięcie planowane w 150–152).
- Feed Facebooka i Instagrama zależy od konta. Persony wymagałyby fałszywych kont, co łamie regulaminy, grozi banem
  w trakcie demo i jest nie do obrony w narzędziu dla organu nadzoru.
- Spersonalizowane wyniki są niepowtarzalne, więc analityk nie odtworzy, skąd wziął się rekord.
- `backend-integration.md` §3a zakłada już pracę bez ciasteczek i kont.

Z pomysłu zostaje kilka równoległych przeglądarek: osobny, czysty `browserContext` Playwrighta na zadanie,
z `locale: pl-PL` i `timezoneId: Europe/Warsaw`.

## 3. Warstwy

### S0. Seedy

Codzienny job ładuje listy KNF i CERT do tabel referencyjnych, a z nich powstają wiersze `sources`:
nazwy firm, oficjalne domeny, profile społecznościowe i warianty nazw.

### S1. Biblioteki reklam (główne źródło reklam)

- **Meta:** endpoint `ads_archive` z `ad_reached_countries=PL`, zapytania po nazwach firm i frazach oraz po `search_page_ids`.
  Dla UE obejmuje wszystkie reklamy, także płatnika i beneficjenta, czyli dane wprost potrzebne w M1.
  Wymaga konta deweloperskiego i weryfikacji tożsamości, więc **trzeba to zlecić od razu**.
- **Meta, plan B:** publiczny interfejs Ad Library w Playwright, gdyby weryfikacja nie przeszła na czas.
- **TikTok:** publiczna biblioteka `library.tiktok.com`. API wymaga wniosku i akceptacji, więc na hackathon zakładamy interfejs WWW.
- **Google:** Ads Transparency Center dla reklam w wyszukiwarce i na YouTube, po nazwie reklamodawcy i domenie.

Mapowanie: `kind: "post"`, `isSponsored: true`, `author` = strona reklamująca.

**Uwaga:** `ad_snapshot_url` z API Meta zawiera access token. Do `url` zapisujemy
`https://www.facebook.com/ads/library/?id=<ad_archive_id>`, a surowy JSON przed zapisem do MinIO czyścimy z tokenu.

### S2. Znane profile

- YouTube i TikTok: `yt-dlp` plus napisy. Dla YouTube wykorzystujemy logikę z `ml/scripts/collect_youtube.py`.
- Facebook i Instagram: tylko to, co widać bez logowania.
- Strony firm: sitemap, potem `httpx`, a Playwright tylko gdy treść wymaga JS.
- Nowy autor znaleziony w S1 lub S3 trafia do `sources` jako profil do cyklicznego monitoringu. To główna pętla wzrostu pokrycia.

### S3. Discovery przez wyszukiwarki

Zapytanie = zakres platformy × fraza × okno czasu:

```text
site:instagram.com/reel  "XTB" ("#reklama" OR "#współpraca" OR "kod polecający")
site:facebook.com        "konto maklerskie" "link w komentarzu"
site:tiktok.com          "zarabiam na forex" "napisz do mnie"
site:facebook.com        "dobiorę portfel" OR "doradztwo inwestycyjne" OR "family office"
```

- Filtr świeżości w Google to parametr URL `tbs=qdr:d` lub `qdr:w`. Działanie trzeba sprawdzić na żywo.
- Silnik: self-hosted SearXNG w compose (`time_range=day|week`), z kilkoma wyszukiwarkami naraz.
- Google często blokuje takie zapytania, więc **S3 nie może być jedynym źródłem** i ma działać bez Google.
- Wynik to tylko URL i snippet. Rekord powstaje po pobraniu strony. Jeśli jest login wall, zapisujemy snippet z `discovery.partial: true`.

Mały budżet zapytań, rotacja macierzy między uruchomieniami i cache wyników na 24 h.

### S4. Wzbogacenie

Bez zmian względem `backend-integration.md` §3a. Tylko po triage, w osobnym kontenerze, bez formularzy i pobierania plików.

## 4. Przepływ i kolejki (BullMQ)

```text
scheduler → discover → fetch → normalize + dedup → items → triage → enrich → analyze
```

| Źródło | Harmonogram |
|---|---|
| Listy KNF / CERT | raz dziennie |
| Biblioteki reklam | co 6 h |
| Znane profile | co 12 h |
| Discovery | raz dziennie, małe porcje |

- Limit współbieżności i tempa **per domena**, retry z wykładniczym backoffem.
- Rotacja UA i proxy zgodnie ze specyfikacją, z `PROXY_LIST`.
- **Bezpiecznik:** CAPTCHA, login wall lub seria 403/429 wstrzymuje dane źródło i zapisuje powód w `scrape_runs.error`.
  Nie obchodzimy tych zabezpieczeń.
- Parsery osobno per platforma, za wspólnym interfejsem `discover()` / `fetch()` / `parse()`.

## 5. Dane osobowe i granice

- Tylko treści publiczne, bez logowania, bez prywatnych grup i bez profili osób niepublikujących ofert.
- Komentarze zbieramy tylko, gdy wskazują na ofertę lub link. Autorów komentarzy nie profilujemy.
- Przed pilotażem w UKNF prawnicy powinni potwierdzić podstawę przetwarzania (RODO) i zgodność z regulaminami platform.

## 6. Propozycja zmiany kontraktu

Opcjonalne pole w `ScrapedItem`, potrzebne do odtworzenia pochodzenia rekordu:

```jsonc
"discovery": { "layer": "S1|S2|S3", "method": "meta_ad_library", "query": "XTB", "rank": 3, "partial": false }
```

## 7. Kolejność prac

1. Złożyć weryfikację Meta i ładować seedy KNF.
2. Meta Ad Library → `items`, pierwsza próbka JSONL do `ml/data/incoming/`.
3. YouTube i strony firm z rejestru.
4. TikTok Library i Google Ads Transparency.
5. SearXNG i macierz zapytań.
6. Landing pages z `textBlocks`.
7. **Tryb demo:** zapisany przebieg odtwarzany z MinIO, na wypadek blokady lub braku sieci przy jury.

## 8. Metryki na prezentację

Rekordy per warstwa i platforma, odsetek udanych pobrań, odsetek rekordów pełnych vs `partial`,
udział duplikatów, liczba nowych autorów na uruchomienie oraz odsetek przechodzących triage (precyzja zapytań).
