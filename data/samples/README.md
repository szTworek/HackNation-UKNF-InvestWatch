# ads_sample_v1.jsonl

- Źródło: Google Ads Transparency Center, region PL, pobrane 2026-11-21 kolektorem `scrapers/poc/google_ads/atc_rpc.py`; tekst kreacji obrazkowych z OCR (`preprocessing/ocr/rapid.py`, RapidOCR, PP-OCRv5 latin, CPU).
- Format: jeden rekord RawDocument na linię (`rawdocument.v1-poc`). Rdzeń (D12–D15): `source`, `source_url`, `author`, `published_at`, `fetched_at`, `query_keywords`, `content_keywords`, `text` (lista sekcji `{type, text}`).
- Rekordy (stan po 5 z 18 domen): 270 = etoro.com 80, xtb.com 76, bossa.pl 62, mbank.pl 39, plus500.com 13. Po zakończeniu budowy liczby zostaną zaktualizowane.
- Sekcje: `ocr` 257 (obrazy i reklamy tekstowe zapisane przez Google jako obraz), `ad_body` 13 (tekst z podglądu `content.js`).
- Polski: `source_meta.lang_hint_pl` = true w 118 rekordach (heurystyka: polskie znaki i słowa). Reszta to głównie kreacje po angielsku i kilka w innych językach: filtr regionu Google nie jest szczelny.
- `author` = `sponsor` = reklamodawca (np. „XTB S.A.”); `query_keywords` = domena zapytania; `published_at` = pierwsze wyświetlenie (first_shown); `source_meta.last_shown`, `format` (text/image/video), `advertiser_id`, `creative_id`, `ocr.mean_confidence`.
- Puste: `content_keywords` (wypełni preprocessing), `lang` (preprocessing), `title`. Reklamy wideo bez podglądu tekstowego i obrazy bez wykrytego tekstu zostały pominięte.
- OCR ma literówki w polskich znakach (np. „pieniadzom”, „gietdowe”); średnia pewność 0,94–0,99.
- Brak etykiet M1/M2/M3: to surowe dane. Ostrzeżenie o ryzyku („ryzyk…”/„traci…”) pojawia się w tekście 33 rekordów.
- Obrazy źródłowe: `scrapers/poc/results/google_ads.atc_rpc/images/` (lokalnie, poza gitem; ścieżka w `source_meta.image_refs`).
