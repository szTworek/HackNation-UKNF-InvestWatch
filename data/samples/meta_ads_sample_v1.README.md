# meta_ads_sample_v1

25 reklam z Meta Ad Library (web scrape, zapytanie "forex"), format rekordu D12-D15. Jeden rekord na linie JSONL, UTF-8.

- Zrodlo: `scrapers/poc/results/fb_ads.ad_library_web/20261121-170439-docs.json` (zebrane 2026-11-21); dla 2 reklam (732363262964757, 1918975318998428) `ad_body` pochodzi z `fb_ads.ytdlp_by_id` (pelniejszy tekst, akapity).
- Konwerter: `scripts/convert_fb_ads_web.py <wejscie.json> [wyjscie.jsonl] [katalog_ytdlp]`.
- Rekordy: 25, z niepustym `ad_body`: 16. Pozostale 9 to reklamy usuniete/wylaczone przez Meta (zostala tylko notka w `source_meta.notice`), `text` = [].

## Pola
`source`=meta_ad_library, `source_url`, `author`=`sponsor` (nazwa strony reklamodawcy), `published_at` (poczatek wyswietlania, data `YYYY-MM-DD`), `fetched_at`, `query_keywords`=["forex"], `content_keywords`=[] (preprocessing), `text` = lista sekcji `[{"type","text"}]` (typy: `ad_body`, `title`, `link_description`, `cta`; `[]` dla reklam bez tresci), brak osobnego pola `sections`, `links` (domena docelowa, male litery; tylko gdy reklama ma karte linku), `content_type`=ad, `url_key`.

`source_meta`: `library_id`, `delivery_end`, `status` (Aktywna/Nieaktywna, null gdy brak), `ads_with_same_creative`, `multiple_versions`, `eu_transparency`, `has_categories`, `restricted_for_some_audiences`, `notice`, `has_video`, `platform_icons` (liczba ikon platform; nazw platform scrape nie zawiera), `ad_body_source`.

## Czego brakuje
- Brak etykiet (zgodna / niezgodna z regulacja, typ naruszenia); to surowa probka.
- Nazwy platform, obrazy/wideo, tekst z grafiki: brak.
- 9 reklam bez tresci; reklamy w wiekszosci angielskie/indyjskie, nie polskie ani z rejestru KNF.
- Podzial na `title`/`link_description` to heurystyka z ukladu karty (po domenie); reklamy bez domeny maja naglowek wewnatrz `ad_body`.
- `published_at` bez godziny. Reklamy z "Rozpoczecie wyswietlania" (aktywne) maja `delivery_end` = null.
