"""Bing/Microsoft ads: Microsoft Ad Library REST API (keyless, EEA ads, Poland = country code 151).
Endpoint taken from the fejker repo (ftf/sources.py ms_adlib_search)."""
import httpx

from common import envelope, ua


def collect(query, notes, top=10):  # top=25 -> HTTP 400
    r = httpx.get("https://adlibrary.api.bingads.microsoft.com/api/v1/Ads", headers={"User-Agent": ua()}, timeout=30,
                  params={"searchText": query, "top": top, "skip": 0, "countryCodes": 151})
    r.raise_for_status()
    js = r.json()
    rows = js.get("value", js if isinstance(js, list) else [])
    notes["returned"] = len(rows)
    for a in rows:
        yield envelope(
            url=f"https://adlibrary.ads.microsoft.com/ad/{a.get('AdId')}", source="microsoft_ad_library",
            collector="bing_ads.ms_adlib", content_type="ad", title=a.get("Title"), text=a.get("Description") or "",
            author=a.get("AdvertiserName"), sponsor=a.get("AdvertiserName"),
            links=[u for u in (a.get("DestinationUrl"),) if u],
            source_meta={"query": query, "ad_id": a.get("AdId"), "advertiser_id": a.get("AdvertiserId"),
                         "display_url": a.get("DisplayUrl"), "country_code": 151},
        )
