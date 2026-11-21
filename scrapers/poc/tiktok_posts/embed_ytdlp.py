"""TikTok posts, no login: creator embed page (/embed/@handle, curl_cffi) lists recent video ids;
yt-dlp fetches each video's metadata. query = "@handle" or "@a,@b" (no keyword search without login)."""
import json
import re

import yt_dlp
from curl_cffi import requests

from common import envelope

STATE = re.compile(r'<script id="__FRONTITY_CONNECT_STATE__"[^>]*>(.*?)</script>', re.S)


def collect(query, notes, per_user=5):
    if not query.startswith("@"):
        raise ValueError("tiktok_posts.embed_ytdlp needs query '@handle[,@handle]'")
    handles = [h.strip().lstrip("@") for h in query.split(",") if h.strip()]
    notes.update(embed={}, video_errors=[])
    with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
        for h in handles:
            r = requests.get(f"https://www.tiktok.com/embed/@{h}", impersonate="chrome", timeout=20)
            src = json.loads(STATE.search(r.text).group(1))["source"]["data"][f"/embed/@{h}"]
            vids = [v["id"] for v in src.get("videoList") or []][:per_user]
            notes["embed"][h] = {"status": r.status_code, "videos": len(vids),
                                 "followers": src.get("userInfo", {}).get("followerCount")}
            for vid in vids:
                url = f"https://www.tiktok.com/@{h}/video/{vid}"
                try:
                    v = ydl.extract_info(url, download=False)
                except Exception as e:
                    notes["video_errors"].append(f"{vid}: {type(e).__name__}: {str(e)[:120]}")
                    continue
                d, desc = v.get("upload_date"), v.get("description") or ""
                yield envelope(
                    url=url, source="tiktok", collector="tiktok_posts.embed_ytdlp", content_type="video",
                    title=v.get("title"), sections=[{"type": "post", "text": desc}] if desc else [], query_keywords=[f"@{h}"], author=v.get("uploader") or h,
                    published_at=f"{d[:4]}-{d[4:6]}-{d[6:]}" if d else None, links=re.findall(r"https?://\S+", desc),
                    source_meta={"video_id": vid, "hashtags": re.findall(r"#(\w+)", desc),
                                 "view_count": v.get("view_count"), "like_count": v.get("like_count"),
                                 "duration": v.get("duration"), "track": v.get("track"),
                                 "audio_available": any(f.get("acodec") not in (None, "none") for f in v.get("formats", []))},
                )
