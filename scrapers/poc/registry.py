"""Collector registry and CLI. Every collector: collect(query: str, notes: dict) -> Iterable[RawDocument].

  python -m registry                       # list collectors
  python -m registry youtube_posts forex   # default variant of a module
  python -m registry google_ads.atc_rpc "XTB"
"""
import importlib
import sys

from common import run

# module -> variants (first = default), each "package.file"
MODULES = {
    "youtube_posts": ["youtube_posts.ytdlp", "youtube_posts.data_api"],
    "tiktok_posts": ["tiktok_posts.embed_ytdlp", "tiktok_posts.tiktokapi"],
    "ig_posts": ["ig_posts.session", "ig_posts.graph_api", "ig_posts.instaloader_anon"],
    "fb_posts": ["fb_posts.session", "fb_posts.no_login_probe"],
    "x_posts": ["x_posts.session", "x_posts.api_recent_search", "x_posts.no_login_probe"],
    "fb_ads": ["fb_ads.ad_library_api", "fb_ads.ad_library_web", "fb_ads.ytdlp_by_id"],
    "google_ads": ["google_ads.atc_rpc", "google_ads.atc_playwright"],
    "bing_ads": ["bing_ads.ms_adlib"],
    "x_ads": ["x_ads.ads_repository_probe"],
    "tiktok_ads": ["tiktok_ads.library_probe"],
}
DEFAULT_QUERY = {
    "tiktok_posts": "@etoro_official,@revolut", "tiktok_posts.tiktokapi": "#inwestowanie",
    "ig_posts.instaloader_anon": "@xtb_polska", "ig_posts.graph_api": "@xtb_polska",
    "fb_posts.no_login_probe": "@XTBPL", "x_posts.no_login_probe": "XTB_PL",
    "google_ads": "XTB", "google_ads.atc_playwright": "xtb.com,etoro.com", "x_ads": "eToro", "tiktok_ads": "-",
}


def resolve(name: str) -> str:
    return MODULES[name][0] if name in MODULES else name


def collector(name: str):
    return importlib.import_module(resolve(name)).collect


def main(argv):
    if not argv:
        for m, vs in MODULES.items():
            print(f"{m:14} {', '.join(vs)}")
        return
    name = resolve(argv[0])
    query = argv[1] if len(argv) > 1 else DEFAULT_QUERY.get(name, DEFAULT_QUERY.get(name.split(".")[0], "forex"))
    run(name, collector(name), query)


if __name__ == "__main__":
    main(sys.argv[1:])
