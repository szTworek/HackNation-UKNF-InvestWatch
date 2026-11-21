"""FB + IG ads, no login: one Ad Library ad by ID via yt-dlp's facebook:ads extractor (full text,
advertiser, video/image formats for whisper/OCR). query = "id[,id]" (ids from ad_library_api or
ad_library_web). Idea from the fejker repo (ftf/sources.py meta_ad_media). Same Meta-terms caveat as ad_library_web."""
import yt_dlp

from common import envelope


def collect(query, notes):
    notes["errors"] = []
    with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
        for ad_id in (x.strip() for x in query.split(",") if x.strip()):
            try:
                v = ydl.extract_info(f"https://www.facebook.com/ads/library/?id={ad_id}", download=False)
            except Exception as e:
                notes["errors"].append(f"{ad_id}: {str(e)[:150]}")
                continue
            e = (v.get("entries") or [v])[0]
            yield envelope(
                url=f"https://www.facebook.com/ads/library/?id={ad_id}", source="meta_ad_library",
                collector="fb_ads.ytdlp_by_id", content_type="ad", title=v.get("title"), query_keywords=[ad_id],
                text=v.get("description") or "", author=v.get("uploader"), sponsor=v.get("uploader"),
                links=[f["url"] for f in (e.get("formats") or [])[:1]],
                source_meta={"ad_id": ad_id, "page_id": v.get("uploader_id"), "media_ext": e.get("ext"),
                             "entries": len(v.get("entries") or [v])},
            )
