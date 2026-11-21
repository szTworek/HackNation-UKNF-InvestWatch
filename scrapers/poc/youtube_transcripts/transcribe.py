"""YouTube transcripts for RawDocuments from youtube_posts (D7): source captions first, else audio + faster-whisper.

Usage (from scrapers/poc): python -m youtube_transcripts.transcribe results/youtube_posts.data_api/*-docs.json
Resumable: videos with an existing segments/<video_id>.json are not processed again."""
import argparse
import copy
import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import yt_dlp
from yt_dlp.utils import download_range_func
from youtube_transcript_api import YouTubeTranscriptApi

from common import POC_DIR, RESULTS, ua

OUT = RESULTS / "youtube_transcripts"
SEGMENTS = OUT / "segments"
AUDIO = OUT / "audio"
MODEL = "small"


def iso_seconds(d: str | None) -> int | None:
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", d or "")
    if not m:
        return None
    dd, h, mi, s = (int(x or 0) for x in m.groups())
    return dd * 86400 + h * 3600 + mi * 60 + s


def captions(video_id: str) -> list[dict]:
    t = YouTubeTranscriptApi().fetch(video_id, languages=["pl"])
    return [{"start": round(s.start, 2), "end": round(s.start + s.duration, 2), "text": s.text} for s in t.snippets]


def download_audio(video_id: str, clip_s: int | None) -> Path:
    AUDIO.mkdir(parents=True, exist_ok=True)
    opts = {"quiet": True, "no_warnings": True, "format": "bestaudio", "http_headers": {"User-Agent": ua()},
            "outtmpl": str(AUDIO / f"{video_id}.%(ext)s")}
    if clip_s:
        opts["download_ranges"] = download_range_func(None, [(0, clip_s)])
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
    return Path(info["requested_downloads"][0]["filepath"])


def whisper(model, audio: Path, language: str | None) -> tuple[list[dict], dict]:
    segs, info = model.transcribe(str(audio), language=language, vad_filter=True, beam_size=1)
    out = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segs]
    return out, {"language": info.language, "audio_s": round(info.duration, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", help="RawDocument *-docs.json files from youtube_posts")
    ap.add_argument("--long-min", type=float, default=20, help="videos longer than this get truncated")
    ap.add_argument("--clip-min", type=float, default=10, help="truncate long videos to the first N minutes")
    ap.add_argument("--sleep", type=float, default=4, help="pause between videos (s)")
    ap.add_argument("--only", type=lambda s: s.split(","), help="comma-separated video_ids to process")
    a = ap.parse_args()

    records = {}
    for p in a.inputs:
        for r in json.loads(Path(p).read_text(encoding="utf-8")):
            if not a.only or r["source_meta"]["video_id"] in a.only:
                records.setdefault(r["source_meta"]["video_id"], r)
    SEGMENTS.mkdir(parents=True, exist_ok=True)
    t_run, model, captions_blocked, docs, log = time.perf_counter(), None, None, [], []

    for i, (vid, rec) in enumerate(records.items(), 1):
        seg_file = SEGMENTS / f"{vid}.json"
        duration = iso_seconds(rec["source_meta"].get("duration"))
        meta = {"method": None, "model": None, "duration_s": duration, "seconds_to_transcribe": None}
        if seg_file.exists():
            seg = json.loads(seg_file.read_text(encoding="utf-8"))
        elif not duration:
            seg, meta["error"] = None, "live/upcoming stream (duration 0), skipped"
        else:
            seg, t0 = None, time.perf_counter()
            if not captions_blocked:
                try:
                    seg = {"method": "captions", "model": None, "truncated": False, "language": "pl",
                           "segments": captions(vid)}
                except Exception as e:
                    if type(e).__name__ in ("IpBlocked", "RequestBlocked") or "429" in str(e):
                        captions_blocked = type(e).__name__
                    meta["captions_error"] = type(e).__name__
            if seg is None:
                try:
                    clip = int(a.clip_min * 60) if duration > a.long_min * 60 else None
                    t_dl = time.perf_counter()
                    audio = download_audio(vid, clip)
                    t_dl = time.perf_counter() - t_dl
                    if model is None:
                        from faster_whisper import WhisperModel
                        model = WhisperModel(MODEL, device="cpu", compute_type="int8")
                    lang = (rec["source_meta"].get("default_audio_language") or "")[:2] or None
                    t_tr = time.perf_counter()
                    segs, winfo = whisper(model, audio, lang)
                    seg = {"method": "whisper", "model": f"faster-whisper-{MODEL}-int8", "truncated": bool(clip),
                           "truncated_to_s": clip, "language": winfo["language"], "audio_s": winfo["audio_s"],
                           "audio_ref": audio.relative_to(POC_DIR).as_posix(),
                           "seconds_download": round(t_dl, 1), "seconds_whisper": round(time.perf_counter() - t_tr, 1),
                           "segments": segs}
                except Exception as e:
                    meta["error"] = f"{type(e).__name__}: {e}"[:400]
            if seg is not None:
                seg = {"video_id": vid, **seg, "seconds_to_transcribe": round(time.perf_counter() - t0, 1)}
                seg_file.write_text(json.dumps(seg, ensure_ascii=False, indent=1), encoding="utf-8")
            time.sleep(a.sleep + random.random() * 2)

        d = copy.deepcopy(rec)
        d["source_url"] = d.pop("url")
        d["query_keywords"] = [rec["source_meta"]["query"]] if rec["source_meta"].get("query") else []
        d["content_keywords"] = []
        title = rec.get("title") or ""
        desc = rec["text"].removeprefix(title).lstrip("\n")
        d["text"] = [{"type": "title", "text": title}, {"type": "description", "text": desc}]
        if seg:
            meta.update(method=seg["method"], model=seg["model"], truncated=seg["truncated"],
                        seconds_to_transcribe=seg.get("seconds_whisper", seg["seconds_to_transcribe"]))
            if seg.get("audio_s"):
                meta["audio_s"] = seg["audio_s"]
            d["text"] += [{"type": "transcript", **s} for s in seg["segments"]]
            d["transcript_ref"] = seg_file.relative_to(POC_DIR).as_posix()
            d["audio_ref"] = seg.get("audio_ref")
        else:
            d["transcript_ref"] = None
        d["source_meta"]["transcript"] = meta
        docs.append(d)
        log.append({"video_id": vid, **meta})
        print(f"[{i}/{len(records)}] {vid} {meta}", flush=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (OUT / f"{stamp}-docs.json").write_text(json.dumps(docs, ensure_ascii=False, indent=1), encoding="utf-8")
    done = [x for x in log if x["method"]]
    audio_s = sum(x.get("audio_s") or 0 for x in done if x["method"] == "whisper")
    whisper_s = sum(x["seconds_to_transcribe"] or 0 for x in done if x["method"] == "whisper")
    summary = {"run_seconds": round(time.perf_counter() - t_run, 1), "inputs": a.inputs, "videos": len(records),
               "with_transcript": len(done), "by_method": {m: sum(x["method"] == m for x in done) for m in ("captions", "whisper")},
               "captions_blocked": captions_blocked, "audio_minutes": round(audio_s / 60, 1),
               "whisper_seconds_per_audio_minute": round(whisper_s / (audio_s / 60), 1) if audio_s else None,
               "videos_log": log}
    (OUT / f"{stamp}-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "videos_log"}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
