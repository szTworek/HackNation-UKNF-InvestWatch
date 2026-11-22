# InvestWatch — próbki danych (2026-11-21)

Realne dane z kolektorów PoC (YouTube, TikTok, reklamy Google, Meta i Microsoft/Bing, strony firm), w jednym formacie rekordu. Jeden rekord JSON na linię (UTF-8). Rekordy są zdeduplikowane po `source_url`.

## Pliki

| plik | `source` | rekordy | klucze `text` (liczba rekordów) |
|---|---|---|---|
| `youtube/records.jsonl` | `youtube` | 13 | `title` (13), `description` (13), `transcript` (13) |
| `tiktok/records.jsonl` | `tiktok` | 49 | `post` (49), `transcript` (49) |
| `google_ads/records.jsonl` | `google_ads_transparency` | 440 | `ocr` (426), `ad_body` (14) |
| `meta_ads/records.jsonl` | `meta_ad_library` | 234 | `ad_body` (234), `title` (118), `link_description` (106), `cta` (133) |
| `bing_ads/records.jsonl` | `microsoft_ad_library` | 300 | `title` (300), `ad_body` (252) |
| `firm_web/records.jsonl` | `firm_website` | 11 | `page` (11), `risk_disclaimer` (11) |

## Format rekordu

Pola obowiązkowe:

- `source`: platforma, np. `youtube`, `google_ads_transparency`.
- `source_url`: adres materiału (unikalny w pliku).
- `author`: kanał, konto albo reklamodawca, może być `null`.
- `published_at`: data publikacji albo pierwszego wyświetlenia (ISO 8601), może być `null`.
- `fetched_at`: moment pobrania (ISO 8601).
- `query_keywords`: zapytanie albo domena, które znalazły rekord, np. `["forex"]`, `["xtb.com"]`.
- `content_keywords`: słowa kluczowe treści, na razie `[]`.
- `text`: obiekt `{nazwa_sekcji: tekst}`. Cała treść sekcji to jeden string.

Klucze `text`:

- YouTube: `title`, `description`, `transcript` (whisper, tylko część filmów).
- TikTok: `title`, `description` albo, dla filmów z transkrypcją, `post`, `transcript` (whisper).
- reklamy: `title`, `ad_body`, `cta`, `link_description`, a dla reklam obrazkowych `ocr`.

Pola opcjonalne: `sponsor`, `links`, `content_type` (`video` / `ad`) i `source_meta` (metadane platformy, np. `video_id`, `statistics`, `advertiser_id`, `ocr.mean_confidence`; `collector` to kolektor, który pobrał rekord).

Przykład (YouTube, stringi skrócone tu do 120 znaków):

```json
{
  "source": "youtube",
  "source_url": "https://www.youtube.com/watch?v=Q0xYH7lIqlA",
  "author": "Bunkier Inwestora",
  "published_at": "2025-06-09T17:11:11Z",
  "fetched_at": "2026-11-21T22:31:14+00:00",
  "query_keywords": [
    "kod polecający XTB"
  ],
  "content_keywords": [],
  "text": {
    "title": "Ile trzeba ZAINWESTOWAĆ w XTB żeby zarabiać pasywnie 1000zł z DYWIDEND? #inwestycje #akcje #xtb",
    "description": "📢Zapraszam na Telegram - https://t.me/+3E835iPYZf0zNjg0\n📩Kontakt: bunkierinwestora@gmail.com\n\n#inwestycje #akcje #xtb #d…",
    "transcript": "Ile musisz mieć akcję XTB, żeby zarabiać 1000 zł miesięcznie z dividend? Wyobraź sobie, że co miesiąc pada tobie 1000 zł…"
  },
  "sponsor": null,
  "links": [],
  "content_type": "video",
  "source_meta": {
    "query": "kod polecający XTB",
    "video_id": "Q0xYH7lIqlA",
    "channel_id": "UCiGVJJ7EDNotVINyepRBPQg",
    "tags": [
      "ile trzeba zainwestować",
      "akcje",
      "xtb",
      "dywidenda",
      "dochód pasywny"
    ],
    "statistics": {
      "viewCount": "141117",
      "likeCount": "1646",
      "favoriteCount": "0",
      "commentCount": "57"
    },
    "duration": "PT1M2S",
    "has_paid_product_placement": false,
    "default_audio_language": "pl",
    "firm": "XTB",
    "firms_mentioned": [
      "XTB"
    ],
    "advertiser_is_firm": false,
    "lang_hint_pl": true,
    "transcript": {
      "method": "whisper",
      "model": "faster-whisper-small-int8",
      "duration_s": 62,
      "seconds_to_transcribe": 46.2,
      "truncated": false,
      "audio_s": 61.6
    },
    "collector": "youtube_posts.data_api"
  }
}
```

## Znane braki

- Brak etykiet (M1/M2/M3, naruszenie/brak naruszenia): to surowe dane, `content_keywords` jest puste (`[]`).
- Google Ads: wszystkie kreacje były wyświetlane w Polsce, ale część to kampanie wielorynkowe (np. XTB dla Chile, Słowacji, Węgier, Niemiec) w innych językach. Flaga `source_meta.lang_hint_pl` to prosta heurystyka i zaniża liczbę polskich reklam, bo OCR gubi polskie znaki (false: 303 z 440).
- Tekst reklam obrazkowych Google pochodzi z OCR (RapidOCR), a transkrypty YouTube z whispera (faster-whisper small). W obu są błędy, zwłaszcza w polskich znakach i nazwach własnych.
- `published_at` bywa `null` (np. YouTube z yt-dlp, Bing). `author` bywa `null`.
- Opisy z yt-dlp i z biblioteki reklam Meta bywają ucięte (kończą się „…”).
- Meta: 132 reklam pominięto, bo Meta je usunęła lub wyłączyła za naruszenie Standardów dotyczących reklam; treść reklamy nie jest dostępna, a Meta nie podaje konkretnej reguły. Notka i reklamodawca są w `raw/meta_ads_entities_v1.jsonl` i `raw/meta_ads_sample_v1.jsonl` (`source_meta.notice`).
- `raw/`: surowe wyjście kolektorów (`data/samples/*.jsonl`), w tym filmy YouTube/TikTok bez transkryptu i usunięte reklamy Meta. Pola `source_meta.firm`, `firms_mentioned`, `advertiser_is_firm`, `lang_hint_pl` w plikach `*_entities_v1`.
- Obrazy, audio i segmenty transkryptów z czasami nie są w paczce.
- YouTube i TikTok: w paczce są tylko filmy z transkryptem. Pominięte filmy bez transkryptu: youtube 297, tiktok 5.
