"""Export all collected samples to one record format (D12-D15) and pack them into a ZIP.

Usage: python scripts/export_samples.py
Output: data/export/<source>/records.jsonl, data/export/investwatch_samples_20261121.zip
"""
import collections
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters import bing_ads, google_ads, meta_ads, tiktok, youtube  # noqa: E402
from adapters.common import validate  # noqa: E402

RES = "scrapers/poc/results/"
OUT = ROOT / "data" / "export"
ZIP = OUT / "investwatch_samples_20261121.zip"


def latest_docs(collector):
    """Newest non-empty *-docs.json of a collector, or [] when none exists yet."""
    files = sorted((ROOT / RES / collector).glob("*-docs.json"), reverse=True)
    return next(([RES + collector + "/" + f.name] for f in files if json.loads(f.read_text(encoding="utf-8"))), [])


# Per source: inputs in priority order; the first record with a given source_url wins.
INPUTS = {
    "youtube": (youtube, [
        RES + "youtube_transcripts/20261121-175316-docs.json",
        RES + "youtube_posts.data_api/20261121-175414-docs.json",
        RES + "youtube_posts.ytdlp/20261121-170427-docs.json",
        RES + "youtube.ytdlp_search/20261121-160400-docs.json",
    ]),
    "tiktok": (tiktok, latest_docs("tiktok_transcripts") + [
        RES + "tiktok_posts.embed_ytdlp/20261121-175100-docs.json",
        RES + "tiktok.embed_ytdlp/20261121-160840-docs.json",
    ]),
    "google_ads": (google_ads, [
        "data/samples/ads_sample_v1.jsonl",
        RES + "google_ads.atc_rpc/20261121-172343-docs.json",
        RES + "google_ads.atc_playwright/20261121-171613-docs.json",
    ]),
    "meta_ads": (meta_ads, [
        "data/samples/meta_ads_sample_v1.jsonl",
        RES + "fb_ads.ytdlp_by_id/20261121-170511-docs.json",
    ]),
    "bing_ads": (bing_ads, [
        RES + "bing_ads.ms_adlib/20261121-175411-docs.json",
    ]),
}

KNOWN_GAPS = """\
- Brak etykiet (M1/M2/M3, naruszenie/brak naruszenia): to surowe dane, `content_keywords` jest puste (`[]`).
- Google Ads: filtr regionu PL w Transparency Center nie jest szczelny, część kreacji jest po angielsku albo w innych językach (`source_meta.lang_hint_pl` = false: {non_pl} z {google}).
- Tekst reklam obrazkowych Google pochodzi z OCR (RapidOCR), a transkrypty YouTube z whispera (faster-whisper small). W obu są błędy, zwłaszcza w polskich znakach i nazwach własnych.
- `published_at` bywa `null` (np. YouTube z yt-dlp, Bing). `author` bywa `null`.
- Opisy z yt-dlp i z biblioteki reklam Meta bywają ucięte (kończą się „…”).
- Meta: 9 reklam pominięto, bo Meta je usunęła lub wyłączyła za naruszenie Standardów dotyczących reklam (5: wyłączone konto reklamodawcy, 4: usunięta reklama); treść reklamy nie jest dostępna, a Meta nie podaje konkretnej reguły. Notka i reklamodawca są w `data/samples/meta_ads_sample_v1.jsonl` (`source_meta.notice`).
- Obrazy, audio i segmenty transkryptów z czasami nie są w paczce.
- YouTube i TikTok: w paczce są tylko filmy z transkryptem. Pominięte filmy bez transkryptu: {no_transcript}.
"""


def load(path):
    p = ROOT / path
    if p.suffix == ".jsonl":
        return [json.loads(line) for line in p.open(encoding="utf-8") if line.strip()]
    return json.loads(p.read_text(encoding="utf-8"))


def short(o, n=120):
    if isinstance(o, str):
        return o if len(o) <= n else o[:n] + "…"
    if isinstance(o, list):
        return [short(x, n) for x in o[:5]]
    if isinstance(o, dict):
        return {k: short(v, n) for k, v in o.items()}
    return o


def main():
    stats = {}
    skipped_total = collections.Counter()
    no_transcript = collections.defaultdict(set)
    example = None
    for name, (adapter, paths) in INPUTS.items():
        seen, records, skipped, dup = set(), [], 0, 0
        for path in paths:
            for raw in load(path):
                rec = adapter.to_record(raw)
                if not rec["text"]:
                    skipped += 1
                    continue
                if name in ("youtube", "tiktok") and not rec["text"].get("transcript"):
                    no_transcript[name].add(rec["source_url"])
                    continue
                if rec["source_url"] in seen:
                    dup += 1
                    continue
                errors = validate(rec)
                if errors:
                    raise ValueError(f"{name} {rec['source_url']}: {errors}")
                seen.add(rec["source_url"])
                records.append(rec)
        no_transcript[name] -= seen
        d = OUT / name
        d.mkdir(parents=True, exist_ok=True)
        with (d / "records.jsonl").open("w", encoding="utf-8", newline="\n") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        keys = collections.Counter(k for r in records for k in r["text"])
        stats[name] = {"records": len(records), "skipped_empty_text": skipped, "duplicates": dup,
                       "text_keys": dict(keys), "source": records[0]["source"] if records else None,
                       "non_pl": sum(1 for r in records if r["source_meta"].get("lang_hint_pl") is False)}
        skipped_total[name] = skipped
        if name == "youtube":
            example = next((r for r in records if "transcript" in r["text"]), records[0])
        print(f"{name}: {len(records)} records, skipped empty text {skipped}, duplicates {dup}, text keys {dict(keys)}")

    rows = "\n".join(
        f"| `{n}/records.jsonl` | `{s['source']}` | {s['records']} | {', '.join(f'`{k}` ({c})' for k, c in s['text_keys'].items())} |"
        for n, s in stats.items())
    skipped_str = ", ".join(f"{n} {c}" for n, c in skipped_total.items() if c) or "0"
    readme = f"""# InvestWatch — próbki danych (2026-11-21)

Realne dane z kolektorów PoC (YouTube, TikTok, reklamy Google, Meta i Microsoft/Bing), w jednym formacie rekordu. Jeden rekord JSON na linię (UTF-8). Rekordy są zdeduplikowane po `source_url`.

## Pliki

| plik | `source` | rekordy | klucze `text` (liczba rekordów) |
|---|---|---|---|
{rows}

## Format rekordu

Pola obowiązkowe:

- `source`: platforma, np. `youtube`, `google_ads_transparency`.
- `source_url`: adres materiału (unikalny w pliku).
- `author`: kanał, konto albo reklamodawca, może być `null`.
- `published_at`: data publikacji albo pierwszego wyświetlenia (ISO 8601), może być `null`.
- `fetched_at`: moment pobrania (ISO 8601).
- `query_keywords`: zapytanie albo domena, które znalazły rekord, np. `["forex"]`, `["xtb.com"]`.
- `content_keywords`: słowa kluczowe treści, na razie `[]`.
- `text`: obiekt `{{nazwa_sekcji: tekst}}`. Cała treść sekcji to jeden string.

Klucze `text`:

- YouTube: `title`, `description`, `transcript` (whisper, tylko część filmów).
- TikTok: `title`, `description` albo, dla filmów z transkrypcją, `post`, `transcript` (whisper).
- reklamy: `title`, `ad_body`, `cta`, `link_description`, a dla reklam obrazkowych `ocr`.

Pola opcjonalne: `sponsor`, `links`, `content_type` (`video` / `ad`) i `source_meta` (metadane platformy, np. `video_id`, `statistics`, `advertiser_id`, `ocr.mean_confidence`; `collector` to kolektor, który pobrał rekord).

Przykład (YouTube, stringi skrócone tu do 120 znaków):

```json
{json.dumps(short(example), ensure_ascii=False, indent=2)}
```

## Znane braki

{KNOWN_GAPS.format(non_pl=stats['google_ads']['non_pl'], google=stats['google_ads']['records'], skipped=skipped_str, no_transcript=', '.join(f'{n} {len(u)}' for n, u in no_transcript.items() if u) or '0')}"""
    (OUT / "README.md").write_text(readme, encoding="utf-8", newline="\n")

    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(OUT / "README.md", "README.md")
        for name in INPUTS:
            z.write(OUT / name / "records.jsonl", f"{name}/records.jsonl")
    print(f"zip: {ZIP} ({ZIP.stat().st_size} bytes)")
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
