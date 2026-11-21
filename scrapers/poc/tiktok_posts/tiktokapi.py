"""TikTok posts: TikTokApi (Playwright). query = hashtag ("#inwestowanie") or user ("@handle").
Optional TIKTOK_MS_TOKEN (msToken cookie). Uses system Chrome (CHROME_PATH): bundled Chromium
in headed/new-headless mode does not start on this machine."""
import asyncio

from TikTokApi import TikTokApi

from common import env, envelope

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def to_doc(d, query):
    a = d.get("author", {}).get("uniqueId")
    return envelope(
        url=f"https://www.tiktok.com/@{a}/video/{d['id']}", source="tiktok", collector="tiktok_posts.tiktokapi",
        content_type="video", text=d.get("desc", ""), published_at=str(d.get("createTime")), author=a,
        source_meta={"query": query, "video_id": d["id"], "stats": d.get("stats"), "is_ad": d.get("isAd"),
                     "hashtags": [c.get("hashtagName") for c in d.get("textExtra", []) if c.get("hashtagName")]},
    )


async def _collect(query, count=15):
    tok, out = env("TIKTOK_MS_TOKEN"), []
    async with TikTokApi() as api:
        await api.create_sessions(ms_tokens=[tok] if tok else None, num_sessions=1, sleep_after=3,
                                  browser="chromium", headless=True, executable_path=env("CHROME_PATH") or CHROME)
        name = query.lstrip("#@")
        gen = api.user(name).videos(count=count) if query.startswith("@") else api.hashtag(name=name).videos(count=count)
        async for v in gen:
            out.append(to_doc(v.as_dict, query))
    return out


def collect(query, notes):
    notes["ms_token"] = bool(env("TIKTOK_MS_TOKEN"))
    yield from asyncio.run(_collect(query))
