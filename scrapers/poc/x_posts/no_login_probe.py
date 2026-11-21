"""X posts, no login: probe public endpoints (syndication timeline, Nitter mirrors, x.com, API without auth).
Returns no documents; result is in notes."""
import re

from curl_cffi import requests

URLS = {
    "syndication_timeline": "https://syndication.twitter.com/srv/timeline-profile/screen-name/{q}",
    "nitter.net_search": "https://nitter.net/search?f=tweets&q={q}",
    "nitter.net_rss": "https://nitter.net/{q}/rss",
    "xcancel_search": "https://xcancel.com/search?f=tweets&q={q}",
    "x_profile": "https://x.com/{q}",
    "api_v2_noauth": "https://api.x.com/2/tweets/search/recent?query={q}",
}


def collect(query, notes):
    for k, u in URLS.items():
        try:
            r = requests.get(u.format(q=query), impersonate="chrome", timeout=20)
            notes[k] = {"status": r.status_code, "bytes": len(r.text),
                        "status_links": len(set(re.findall(r"/status/(\d{15,})", r.text)))}
        except Exception as e:
            notes[k] = f"{type(e).__name__}: {str(e)[:100]}"
    return []
