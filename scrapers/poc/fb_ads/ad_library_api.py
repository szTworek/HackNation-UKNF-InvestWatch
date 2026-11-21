"""FB + IG ads: official Meta Ad Library API (/ads_archive). META_ACCESS_TOKEN in UKNF/.env
(user token of an identity-verified FB account, any Meta app)."""
import httpx

from common import env, envelope

API = "https://graph.facebook.com/v24.0/ads_archive"
FIELDS = ("id,page_id,page_name,ad_creation_time,ad_delivery_start_time,ad_delivery_stop_time,"
          "ad_creative_bodies,ad_creative_link_titles,ad_creative_link_captions,ad_creative_link_descriptions,"
          "ad_snapshot_url,publisher_platforms,languages,beneficiary_payers,eu_total_reach,target_ages,"
          "target_gender,target_locations,bylines")


def collect(query, notes, limit=25):
    tok = env("META_ACCESS_TOKEN")
    if not tok:
        raise RuntimeError("META_ACCESS_TOKEN missing in UKNF/.env")
    r = httpx.get(API, timeout=30, params={"access_token": tok, "search_terms": query, "ad_reached_countries": '["PL"]',
                                           "ad_type": "ALL", "ad_active_status": "ALL", "fields": FIELDS, "limit": limit})
    if r.status_code != 200:
        raise RuntimeError(r.json().get("error", {}).get("message", r.text[:300]))
    data = r.json().get("data", [])
    notes["returned"] = len(data)
    notes["has_next_page"] = bool(r.json().get("paging", {}).get("next"))
    for a in data:
        payers = a.get("beneficiary_payers") or []
        yield envelope(
            url=f"https://www.facebook.com/ads/library/?id={a['id']}", source="meta_ad_library",
            collector="fb_ads.ad_library_api", content_type="ad",
            title=(a.get("ad_creative_link_titles") or [None])[0], text="\n".join(a.get("ad_creative_bodies") or []),
            published_at=a.get("ad_delivery_start_time"), author=a.get("page_name"),
            sponsor=", ".join(p.get("payer", "") for p in payers) or a.get("bylines"),
            links=[a["ad_snapshot_url"]] if a.get("ad_snapshot_url") else [],
            source_meta={"query": query, "ad_id": a["id"], "page_id": a.get("page_id"), "beneficiary_payers": payers,
                         "eu_total_reach": a.get("eu_total_reach"), "publisher_platforms": a.get("publisher_platforms"),
                         "delivery_stop": a.get("ad_delivery_stop_time"), "languages": a.get("languages")},
        )
