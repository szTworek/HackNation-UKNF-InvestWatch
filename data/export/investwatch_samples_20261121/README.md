# InvestWatch — próbki danych (2026-11-21)

Realne dane z kolektorów PoC (YouTube, TikTok, reklamy Google, Meta i Microsoft/Bing), w jednym formacie rekordu. Jeden rekord JSON na linię (UTF-8). Rekordy są zdeduplikowane po `source_url`.

## Pliki

| plik | `source` | rekordy | klucze `text` (liczba rekordów) |
|---|---|---|---|
| `youtube/records.jsonl` | `youtube` | 5 | `title` (5), `description` (5), `transcript` (5) |
| `tiktok/records.jsonl` | `tiktok` | 6 | `post` (6), `transcript` (6) |
| `google_ads/records.jsonl` | `google_ads_transparency` | 270 | `ocr` (257), `ad_body` (13) |
| `meta_ads/records.jsonl` | `meta_ad_library` | 16 | `ad_body` (16), `title` (8), `link_description` (4), `cta` (12) |
| `bing_ads/records.jsonl` | `microsoft_ad_library` | 10 | `title` (10), `ad_body` (9) |

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
  "source_url": "https://www.youtube.com/watch?v=-h10P4k1SzA",
  "author": "ALLinTraders PL",
  "published_at": "2024-05-27T14:27:44Z",
  "fetched_at": "2026-11-21T16:12:18+00:00",
  "query_keywords": [
    "forex"
  ],
  "content_keywords": [],
  "text": {
    "title": "Prosta i skuteczna strategia trading forex dla początkujących (PSND za FREE)",
    "description": "Chcesz nauczyć się tradingu w praktyczny i uporządkowany sposób? Dołącz do naszego bezpłatnego szkolenia online, podczas…",
    "transcript": "Strawek i PSND chodzi tak naprawdę o znalezieniu odpowiedzi, to jest w zasadzie quintesencją tego czego szukamy jako tra…"
  },
  "sponsor": null,
  "links": [],
  "content_type": "video",
  "source_meta": {
    "query": "forex",
    "video_id": "-h10P4k1SzA",
    "channel_id": "UCYlMSvlMqkIP3R5-MOubBoA",
    "tags": [
      "Elite Expert Club",
      "Paweł Grądziuk",
      "trading",
      "trader",
      "forex"
    ],
    "statistics": {
      "viewCount": "51857",
      "likeCount": "576",
      "favoriteCount": "0",
      "commentCount": "27"
    },
    "duration": "PT3M9S",
    "has_paid_product_placement": false,
    "default_audio_language": "pl",
    "transcript": {
      "method": "whisper",
      "model": "faster-whisper-small-int8",
      "duration_s": 189,
      "seconds_to_transcribe": 70.4,
      "truncated": false,
      "audio_s": 189.0
    },
    "collector": "youtube_posts.data_api"
  }
}
```

## Znane braki

- Brak etykiet (M1/M2/M3, naruszenie/brak naruszenia): to surowe dane, `content_keywords` jest puste (`[]`).
- Google Ads: filtr regionu PL w Transparency Center nie jest szczelny, część kreacji jest po angielsku albo w innych językach (`source_meta.lang_hint_pl` = false: 152 z 270).
- Tekst reklam obrazkowych Google pochodzi z OCR (RapidOCR), a transkrypty YouTube z whispera (faster-whisper small). W obu są błędy, zwłaszcza w polskich znakach i nazwach własnych.
- `published_at` bywa `null` (np. YouTube z yt-dlp, Bing). `author` bywa `null`.
- Opisy z yt-dlp i z biblioteki reklam Meta bywają ucięte (kończą się „…”).
- Meta: 9 reklam pominięto, bo Meta je usunęła lub wyłączyła za naruszenie Standardów dotyczących reklam (5: wyłączone konto reklamodawcy, 4: usunięta reklama); treść reklamy nie jest dostępna, a Meta nie podaje konkretnej reguły. Notka i reklamodawca są w `data/samples/meta_ads_sample_v1.jsonl` (`source_meta.notice`).
- Obrazy, audio i segmenty transkryptów z czasami nie są w paczce.
- YouTube i TikTok: w paczce są tylko filmy z transkryptem. Pominięte filmy bez transkryptu: youtube 38, tiktok 4.
