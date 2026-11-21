"""YouTube posts: official YouTube Data API v3 (YOUTUBE_API_KEY in UKNF/.env).
search.list = 100 units, videos.list = 1 unit, quota 10 000/day."""
import httpx

from common import env, envelope

API = "https://www.googleapis.com/youtube/v3"


def collect(query, notes):
    key = env("YOUTUBE_API_KEY")
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY missing in UKNF/.env")
    with httpx.Client(timeout=20) as c:
        s = c.get(f"{API}/search", params={"part": "snippet", "q": query, "type": "video", "maxResults": 10,
                                           "regionCode": "PL", "relevanceLanguage": "pl", "key": key})
        s.raise_for_status()
        ids = [i["id"]["videoId"] for i in s.json()["items"]]
        v = c.get(f"{API}/videos", params={"part": "snippet,statistics,contentDetails,paidProductPlacementDetails",
                                          "id": ",".join(ids), "key": key})
        v.raise_for_status()
    notes["quota_units"] = 101
    for it in v.json()["items"]:
        sn = it["snippet"]
        yield envelope(
            url=f"https://www.youtube.com/watch?v={it['id']}", source="youtube", collector="youtube_posts.data_api",
            content_type="video", title=sn["title"], query_keywords=[query],
            sections=[s for s in ({"type": "title", "text": sn["title"]},
                                  {"type": "description", "text": sn.get("description")}) if s["text"]],
            published_at=sn["publishedAt"], author=sn["channelTitle"],
            source_meta={"query": query, "video_id": it["id"], "channel_id": sn["channelId"], "tags": sn.get("tags"),
                         "statistics": it.get("statistics"), "duration": it["contentDetails"]["duration"],
                         "has_paid_product_placement": it.get("paidProductPlacementDetails", {}).get("hasPaidProductPlacement"),
                         "default_audio_language": sn.get("defaultAudioLanguage")},
        )
