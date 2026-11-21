"""YouTube posts, no login: yt-dlp search. Default flat (fast, live demo); full=True adds full
description + captions (youtube-transcript-api)."""
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

from common import envelope, ua


def collect(query, notes, n=10, full=False):
    notes.update(mode="full" if full else "flat", transcripts_ok=0, transcripts_err=[])
    opts = {"quiet": True, "skip_download": True, "extract_flat": not full, "http_headers": {"User-Agent": ua()}}
    with yt_dlp.YoutubeDL(opts) as ydl:
        res = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
    for v in res.get("entries") or []:
        transcript = None
        if full:
            try:
                transcript = " ".join(s.text for s in YouTubeTranscriptApi().fetch(v["id"], languages=["pl", "en"]))
                notes["transcripts_ok"] += 1
            except Exception as e:
                notes["transcripts_err"].append(type(e).__name__)
        d = v.get("upload_date")
        yield envelope(
            url=v.get("webpage_url") or v["url"], source="youtube", collector="youtube_posts.ytdlp",
            content_type="video", title=v.get("title"), query_keywords=[query],
            sections=[s for s in ({"type": "title", "text": v.get("title")},
                                  {"type": "description", "text": v.get("description")},
                                  {"type": "transcript", "text": transcript}) if s["text"]],
            published_at=f"{d[:4]}-{d[4:6]}-{d[6:]}" if d else None, author=v.get("channel"),
            source_meta={"query": query, "video_id": v["id"], "channel_id": v.get("channel_id"),
                         "view_count": v.get("view_count"), "duration": v.get("duration"), "tags": v.get("tags"),
                         "description_truncated": not full, "has_transcript": bool(transcript)},
        )
