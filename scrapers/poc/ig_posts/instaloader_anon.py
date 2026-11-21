"""Instagram posts, no login: instaloader. query = "@handle[,@handle]" (profile + posts) or "#hashtag"."""
import itertools

import instaloader

from common import envelope, ua


def to_doc(p, how):
    return envelope(
        url=f"https://www.instagram.com/p/{p.shortcode}/", source="instagram", collector="ig_posts.instaloader_anon",
        content_type="video" if p.is_video else "image", text=p.caption or "", published_at=p.date_utc.isoformat(),
        author=p.owner_username, sponsor=", ".join(u.username for u in p.sponsor_users) or None,
        source_meta={"via": how, "shortcode": p.shortcode, "hashtags": p.caption_hashtags, "likes": p.likes,
                     "is_sponsored": p.is_sponsored},
    )


def collect(query, notes, per_user=5):
    L = instaloader.Instaloader(user_agent=ua(), download_pictures=False, download_videos=False,
                                save_metadata=False, max_connection_attempts=1, quiet=True)
    notes["errors"] = []
    if query.startswith("#"):
        try:
            for p in itertools.islice(instaloader.Hashtag.from_name(L.context, query[1:]).get_posts_resumable(), 5):
                yield to_doc(p, query)
        except Exception as e:
            notes["errors"].append(f"{query}: {type(e).__name__}: {str(e)[:200]}")
        return
    for h in (x.strip().lstrip("@") for x in query.split(",")):
        try:
            prof = instaloader.Profile.from_username(L.context, h)
            yield envelope(
                url=f"https://www.instagram.com/{h}/", source="instagram", collector="ig_posts.instaloader_anon",
                content_type="profile", title=prof.full_name, text=prof.biography or "", author=h,
                links=[prof.external_url] if prof.external_url else [],
                source_meta={"followers": prof.followers, "is_verified": prof.is_verified,
                             "is_business": prof.is_business_account, "category": prof.business_category_name},
            )
            for p in itertools.islice(prof.get_posts(), per_user):
                yield to_doc(p, f"@{h}")
        except Exception as e:
            notes["errors"].append(f"@{h}: {type(e).__name__}: {str(e)[:200]}")
