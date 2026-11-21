"""YouTube bez napisów platformy: audio (yt-dlp) -> Whisper w Groq -> data/pool/youtube.jsonl (format Doc).

Tylko do zbierania danych treningowych. Najpierw krótkie filmy, tylko język polski, audio kasowane po transkrypcji.
Wznawialne. Przy blokadzie YouTube albo limicie Groq czeka i ponawia.

  uv run python scripts/collect_youtube_asr.py --max-duration 900
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import yt_dlp
from langdetect import DetectorFactory, detect_langs

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_youtube import build_doc  # noqa: E402

from investwatch_ml.schema import append_jsonl, existing_ids, read_jsonl  # noqa: E402
from investwatch_ml.teacher import load_env  # noqa: E402

ML_DIR = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
ASR_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MAX_BYTES = 24 * 1024 * 1024  # limit pliku w darmowym planie
BLOCK = ("not a bot", "429", "Too Many Requests")
NETWORK = ("Failed to resolve", "getaddrinfo", "HTTPSConnection", "Unable to download API page", "bytes read",
           "timed out", "Connection reset", "EOF occurred")  # awaria sieci, nie wada filmu: nie wpisuj na listę pominiętych


DetectorFactory.seed = 0
PL_CHARS = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")


def p_polish(text: str) -> float:
    try:
        return next((x.prob for x in detect_langs(text[:3000]) if x.lang == "pl"), 0.0)
    except Exception:
        return 0.0


def polish_metadata(title: str | None, description: str | None) -> bool:
    """Tytuł lub opis po polsku – sygnał, że Whisper mógł źle wykryć język nagrania."""
    title, description = title or "", description or ""
    return sum(ch in PL_CHARS for ch in title) >= 2 or p_polish(title + " " + description[:600]) >= 0.6


def no_speech(res: dict) -> bool:
    """Whisper halucynuje na muzyce („Muzyka”, „Dziękuję za oglądanie”): za mało słów albo wysoki no_speech_prob."""
    if len(re.findall(r"\w+", res.get("text") or "")) < 15:
        return True
    probs = [x.get("no_speech_prob", 0.0) for x in res.get("segments") or []]
    return bool(probs) and sum(probs) / len(probs) > 0.6


def log(m: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)


def download(video_id: str, tmp: Path) -> tuple[Path, dict]:
    opts = {"quiet": True, "no_warnings": True, "noprogress": True, "format": "worstaudio[ext=m4a]/worstaudio",
            "outtmpl": str(tmp / "%(id)s.%(ext)s"), "max_filesize": MAX_BYTES,
            "http_headers": {"Accept-Language": "pl-PL,pl;q=0.9"}}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
    files = [f for f in tmp.glob(f"{video_id}.*") if not f.name.endswith(".part")]
    if not files:
        raise FileNotFoundError("brak pliku audio (za duży?)")
    return files[0], info


def transcribe(http: httpx.Client, key: str, path: Path, language: str | None = None) -> dict:
    for attempt in range(8):
        data = {"model": "whisper-large-v3-turbo", "response_format": "verbose_json", "temperature": "0"}
        if language:
            data["language"] = language
        with path.open("rb") as f:
            r = http.post(ASR_URL, headers={"Authorization": f"Bearer {key}"}, files={"file": (path.name, f)}, data=data)
        if r.status_code in (429, 500, 502, 503):
            wait = min(float(r.headers.get("retry-after") or 30 * (attempt + 1)), 900)
            log(f"[asr] Groq {r.status_code}; czekam {wait:.0f}s")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("limit Groq Whisper")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-duration", type=int, default=900)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--delay", type=float, default=3.0)
    ap.add_argument("--max-transcript-chars", type=int, default=9000)
    ap.add_argument("--max-desc-chars", type=int, default=2000)
    args = ap.parse_args()
    load_env()
    key = os.environ["GROQ_API_KEY"]
    pool = ML_DIR / "data/pool"
    out, failed = pool / "youtube.jsonl", pool / "youtube_asr_skipped.jsonl"
    tmp = ML_DIR / "data/audio_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    done = existing_ids(out) | existing_ids(pool / "youtube_skipped.jsonl") | existing_ids(failed)

    seen, cands = set(), []
    for c in read_jsonl(pool / "youtube_candidates.jsonl"):
        k = f"yt:{c['id']}"
        if k not in done and k not in seen and 20 <= (c.get("duration") or 0) <= args.max_duration:
            seen.add(k)
            cands.append(c)
    cands.sort(key=lambda c: c["duration"])
    cands = cands[: args.limit] if args.limit else cands
    log(f"[asr] do zrobienia: {len(cands)} filmów, {sum(c['duration'] for c in cands) / 3600:.1f} h audio")

    http = httpx.Client(timeout=180)
    doc_args = SimpleNamespace(max_desc_chars=args.max_desc_chars, max_transcript_chars=args.max_transcript_chars)
    n_ok = n_skip = blocks = 0
    i = 0
    while i < len(cands):
        c = cands[i]
        key_id = f"yt:{c['id']}"
        path = None
        try:
            path, info = download(c["id"], tmp)
            res = transcribe(http, key, path)
            blocks = 0
            lang = str(res.get("language") or "").lower()
            forced = False
            forced = False  # wymuszanie języka wycofane: 11/11 prób dało halucynacje
            if no_speech(res):
                append_jsonl(failed, [{"id": key_id, "reason": "brak mowy"}])
                n_skip += 1
            elif lang not in ("pl", "polish") and not forced:
                append_jsonl(failed, [{"id": key_id, "reason": f"język {lang}"}])
                n_skip += 1
            else:
                doc = build_doc(c, (res.get("text") or "", True), info, doc_args)
                doc.meta["transcript_source"] = "groq_whisper"
                doc.meta["asr_language_forced"] = forced
                append_jsonl(out, [doc.model_dump()])
                n_ok += 1
        except Exception as e:
            msg = str(e)
            if any(b in msg for b in BLOCK):
                blocks += 1
                if blocks > 3:
                    log("[asr] blokada się utrzymuje, kończę; wznowisz tym samym poleceniem")
                    break
                log(f"[asr] YouTube blokuje; czekam {10 * blocks} min")
                time.sleep(600 * blocks)
                continue
            if isinstance(e, (httpx.TransportError, RuntimeError)) or any(n in msg for n in NETWORK):  # sieć / limit: nie oznaczaj filmu jako złego
                log(f"[asr] {type(e).__name__}; ponawiam za 60 s")
                time.sleep(60)
                continue
            append_jsonl(failed, [{"id": key_id, "reason": f"{type(e).__name__}: {msg[:120]}"}])
            n_skip += 1
        finally:
            if path is not None:
                path.unlink(missing_ok=True)
        i += 1
        if i % 10 == 0 or i == len(cands):
            log(f"[asr] {i}/{len(cands)} | zapisane {n_ok}, pominięte {n_skip}")
        time.sleep(args.delay)
    log(f"[asr] koniec: +{n_ok} filmów -> {out}")


if __name__ == "__main__":
    main()
