"""Instagram posts: official Instagram Graph API. query = "@handle" (Business Discovery, business/creator
accounts only) or "#hashtag" (Hashtag Search, max 30 unique hashtags / 7 days).
Needs IG_ACCESS_TOKEN and IG_USER_ID (your own IG Business/Creator account linked to a FB Page)."""
import httpx

from common import env, envelope

G = "https://graph.facebook.com/v24.0"
MEDIA = "id,caption,media_type,permalink,timestamp,like_count,comments_count"


def doc(m, query, author):
    return envelope(url=m["permalink"], source="instagram", collector="ig_posts.graph_api",
                    content_type=m.get("media_type", "post").lower(), text=m.get("caption", ""),
                    published_at=m.get("timestamp"), author=author,
                    source_meta={"query": query, "media_id": m["id"], "likes": m.get("like_count"),
                                 "comments": m.get("comments_count")})


def collect(query, notes):
    tok, me = env("IG_ACCESS_TOKEN"), env("IG_USER_ID")
    if not (tok and me):
        raise RuntimeError("IG_ACCESS_TOKEN / IG_USER_ID missing in UKNF/.env")
    with httpx.Client(timeout=20) as c:
        if query.startswith("@"):
            h = query[1:]
            r = c.get(f"{G}/{me}", params={"access_token": tok,
                      "fields": f"business_discovery.username({h}){{username,followers_count,media.limit(10){{{MEDIA}}}}}"})
            r.raise_for_status()
            media = r.json()["business_discovery"].get("media", {}).get("data", [])
            yield from (doc(m, query, h) for m in media)
            return
        r = c.get(f"{G}/ig_hashtag_search", params={"user_id": me, "q": query.lstrip("#"), "access_token": tok})
        r.raise_for_status()
        hid = r.json()["data"][0]["id"]
        m = c.get(f"{G}/{hid}/recent_media", params={"user_id": me, "access_token": tok,
                                                     "fields": "id,caption,media_type,permalink,timestamp"})
        m.raise_for_status()
        yield from (doc(x, query, None) for x in m.json().get("data", []))
