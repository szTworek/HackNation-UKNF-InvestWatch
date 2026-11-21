"""TikTok transcripts for RawDocuments from tiktok.embed_ytdlp: audio via yt-dlp + faster-whisper, output already in D14.

Usage (from scrapers/poc): python -m tiktok_transcripts.transcribe results/tiktok.embed_ytdlp/<stamp>-docs.json --audio-dir <tmp>
Audio is deleted after each transcription."""
import argparse
import json
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import yt_dlp

from common import RESULTS, now, ua

OUT = RESULTS / "tiktok_transcripts"
MODEL = "small"


def download_audio(url: str, video_id: str, audio_dir: Path) -> Path:
    opts = {"quiet": True, "no_warnings": True, "format": "bestaudio/best", "http_headers": {"User-Agent": ua()},
            "outtmpl": str(audio_dir / f"{video_id}.%(ext)s")}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    return Path(info["requested_downloads"][0]["filepath"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="RawDocument *-docs.json from tiktok.embed_ytdlp")
    ap.add_argument("--audio-dir", help="temporary audio directory (default: system temp)")
    ap.add_argument("--sleep", type=float, default=2, help="pause between videos (s)")
    ap.add_argument("--fallback-lang", default="en", help="re-transcribe with this language when detection is unsure")
    ap.add_argument("--min-lang-prob", type=float, default=0.7)
    a = ap.parse_args()

    records = json.loads(Path(a.input).read_text(encoding="utf-8"))
    audio_dir = Path(a.audio_dir or tempfile.mkdtemp(prefix="tiktok_audio_"))
    audio_dir.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    from faster_whisper import WhisperModel
    model = WhisperModel(MODEL, device="cpu", compute_type="int8")
    t_run, docs, log = time.perf_counter(), [], []

    for i, rec in enumerate(records, 1):
        vid = rec["source_meta"]["video_id"]
        meta = {"method": "whisper", "model": f"faster-whisper-{MODEL}-int8", "lang": None, "seconds_to_transcribe": None}
        transcript = ""
        try:
            t_dl = time.perf_counter()
            audio = download_audio(rec["url"], vid, audio_dir)
            meta["seconds_download"] = round(time.perf_counter() - t_dl, 1)
            t_tr = time.perf_counter()
            segs, info = model.transcribe(str(audio), language=None, vad_filter=True, beam_size=1)
            transcript = " ".join(s.text.strip() for s in segs).strip()
            if transcript and a.fallback_lang and info.language_probability < a.min_lang_prob:
                meta["lang_detected"] = info.language
                segs, info = model.transcribe(str(audio), language=a.fallback_lang, vad_filter=True, beam_size=1)
                transcript = " ".join(s.text.strip() for s in segs).strip()
            meta.update(lang=info.language, lang_probability=round(info.language_probability, 2),
                        audio_s=round(info.duration, 1), seconds_to_transcribe=round(time.perf_counter() - t_tr, 1))
            audio.unlink(missing_ok=True)
        except Exception as e:
            meta["error"] = f"{type(e).__name__}: {e}"[:400]
        if not transcript:
            meta["empty"] = True

        text = {"post": rec.get("text") or ""}
        if transcript:
            text["transcript"] = transcript
        docs.append({
            "source": "tiktok",
            "source_url": rec["url"],
            "author": rec.get("author"),
            "published_at": rec.get("published_at"),
            "fetched_at": now(),
            "query_keywords": [f"@{rec['author']}"] if rec.get("author") else [],
            "content_keywords": [],
            "text": text,
            "content_type": "video",
            "source_meta": {"video_id": vid, "duration_s": rec["source_meta"].get("duration"), "transcript": meta},
        })
        log.append({"video_id": vid, "author": rec.get("author"), **meta})
        print(f"[{i}/{len(records)}] {vid} {meta}", flush=True)
        time.sleep(a.sleep)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (OUT / f"{stamp}-docs.json").write_text(json.dumps(docs, ensure_ascii=False, indent=1), encoding="utf-8")
    done = [x for x in log if not x.get("empty")]
    summary = {"run_seconds": round(time.perf_counter() - t_run, 1), "input": a.input, "videos": len(records),
               "with_transcript": len(done), "audio_seconds": round(sum(x.get("audio_s") or 0 for x in log), 1),
               "whisper_seconds": round(sum(x["seconds_to_transcribe"] or 0 for x in log), 1),
               "langs": {l: sum(x["lang"] == l for x in log) for l in {x["lang"] for x in log}}, "videos_log": log}
    (OUT / f"{stamp}-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "videos_log"}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
