"""X posts: official X API v2 recent search (last 7 days). X_BEARER_TOKEN in UKNF/.env.
Pay-per-use: each returned post is billed, keep max_results small."""
import httpx

from common import env, envelope


def collect(query, notes, max_results=10):
    tok = env("X_BEARER_TOKEN")
    if not tok:
        raise RuntimeError("X_BEARER_TOKEN missing in UKNF/.env")
    r = httpx.get("https://api.x.com/2/tweets/search/recent", timeout=20, headers={"Authorization": f"Bearer {tok}"},
                  params={"query": f"{query} lang:pl -is:retweet", "max_results": max_results,
                          "tweet.fields": "created_at,author_id,entities,public_metrics,lang",
                          "expansions": "author_id", "user.fields": "username,name,verified"})
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code}: {r.text[:300]}")
    j = r.json()
    users = {u["id"]: u for u in j.get("includes", {}).get("users", [])}
    notes["result_count"] = j.get("meta", {}).get("result_count", 0)
    for t in j.get("data", []):
        u = users.get(t["author_id"], {})
        yield envelope(
            url=f"https://x.com/{u.get('username', 'i')}/status/{t['id']}", source="x", collector="x_posts.api_recent_search",
            content_type="post", text=t["text"], published_at=t.get("created_at"), author=u.get("username"),
            links=[x.get("expanded_url") for x in t.get("entities", {}).get("urls", [])],
            source_meta={"query": query, "tweet_id": t["id"], "metrics": t.get("public_metrics"), "lang": t.get("lang")},
        )
