"""Deterministic mock history (every record mock=True) so 30-day charts and alerts have shape before real history exists."""
import hashlib
import random
from datetime import datetime, timedelta, timezone

from .entities import GROUPS

# (module hint, platform, author or None = entity itself, text template)
TEMPLATES = [
    ("M2", "meta_ads", None, {"ad_body": "Handluj CFD na {brand} z dźwignią 1:30. Otwórz konto w 5 minut i zacznij inwestować już dziś!", "title": "Trading bez granic"}),
    ("M2", "google_ads", None, {"ocr": "{brand}\nInwestuj w akcje z 0% prowizji\nBonus do 100 zł na start\n{domain}"}),
    ("M2", "bing_ads", None, {"title": "{brand} – Forex i CFD", "ad_body": "Najlepsza platforma do handlu forex. Tylko dziś bonus powitalny. Zarejestruj się."}),
    ("M2", "meta_ads", None, {"ad_body": "Inwestuj w ETF-y z {brand}. Kontrakty CFD są złożonymi instrumentami i wiążą się z dużym ryzykiem. 76% rachunków inwestorów detalicznych odnotowuje straty.", "title": "ETF od 1 zł"}),
    ("M1", "youtube", "Finanse Po Godzinach", {"title": "Jak zacząć z {brand}? Kod polecający w opisie", "description": "Mój kod polecający {brand}: wpisz: FPG2026 i odbierz darmowe akcje. Link afiliacyjny w opisie.", "transcript": "Dzisiaj pokażę wam jak założyć konto w {brand}, wpiszcie mój kod, dostaniecie akcje za darmo."}),
    ("M1", "tiktok", "inwestuj_z_ola", {"post": "Akcje za darmo w {brand} 🔥 link w bio #inwestowanie", "transcript": "Otwórz konto z mojego linku i odbierz bonus, to naprawdę proste."}),
    ("M1", "meta_ads", "Okazje Finansowe PL", {"ad_body": "Do 100€ w akcjach za darmo! Otwórz konto z naszego linku w aplikacji {brand}.", "cta": "Send Message"}),
    ("M3", "youtube", "Trader Marek", {"title": "Moje sygnały na {brand} – +134% w miesiąc", "description": "Dołącz do grupy na Telegram t.me/tradermarek, kopiuj moje transakcje na {brand}.", "transcript": "Kup teraz złoto, cel cenowy 2500, to pewny zysk, zero ryzyka, gwarantowany zysk."}),
    ("M3", "tiktok", "krypto_sygnaly_pl", {"post": "Sygnały forex codziennie 📈 grupa WhatsApp, handluję na {brand}", "transcript": "Wzrost o 87% w tydzień, kopiujcie moje transakcje, tylko dziś wejście do grupy za darmo."}),
    ("M3", "meta_ads", "{brand} Społeczność Inwestorów", {"ad_body": "Lista akcji na ten tydzień na WhatsApp. Ostatnio wzrost o 134,9%! Handlujemy przez {brand}.", "cta": "Send WhatsApp Message"}),
]
COUNTS = {"xtb": 34, "etoro": 26, "plus500": 18, "trading212": 22, "revolut": 24}
NOW = lambda: datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)  # noqa: E731


def _ts(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def mock_items():
    now, out = NOW(), []
    for eid, n in COUNTS.items():
        g = GROUPS[eid]
        rnd = random.Random(f"mock-{eid}")
        for i in range(n):
            mod, platform, author, tpl = rnd.choice(TEMPLATES)
            day = rnd.choices(range(30), weights=[1 + (30 - d) / 15 for d in range(30)])[0]
            pub = now - timedelta(days=day, hours=rnd.randint(0, 20))
            fmt = {"brand": g["name"], "domain": g["domains"][0]}
            url = f"mock://{platform}/{eid}/{i}"
            out.append({
                "id": "itm_" + hashlib.sha1(url.encode()).hexdigest()[:12],
                "channel": "ad" if platform.endswith("_ads") else "social", "platform": platform,
                "source_url": url, "author": author.format(**fmt) if author else g["name"],
                "author_entity_id": None if author else eid, "entity_ids": [eid],
                "published_at": _ts(pub), "fetched_at": _ts(pub + timedelta(hours=2)), "query_keywords": [g["name"]],
                "text": {k: v.format(**fmt) for k, v in tpl.items()}, "source_meta": {"generator": "mockgen"},
                "mock": True, "_classified_at": _ts(pub + timedelta(hours=2)),
            })
    return out


# entity -> (page path, days ago, risk before, risk after)
CHANGES = {
    "xtb": ("https://www.xtb.com/pl", 3, {"present": True, "cfd_loss_pct": 77, "above_fold": True}, None),
    "etoro": ("https://www.etoro.com/pl/", 6, {"present": True, "cfd_loss_pct": 61, "above_fold": True}, None),
    "plus500": ("https://lp.plus500.com/main/", 12, None, None),
    "revolut": ("https://www.revolut.com/pl-PL/stock-trading/", 9, {"present": True, "cfd_loss_pct": None, "above_fold": False}, None),
    "trading212": ("https://www.trading212.com/pl", 2, {"present": True, "cfd_loss_pct": 74, "above_fold": True},
                   {"present": False, "cfd_loss_pct": None, "above_fold": None}),
}


def mock_pages(existing_pages, latest_snapshot):
    """Returns (pages, snapshots, changes). Builds a change from a mock 'before' snapshot to the page's current snapshot."""
    now = NOW()
    pages, snaps, changes = [], [], []
    by_url = {p["url"]: p for p in existing_pages}
    for eid, (url, ago, before, after) in CHANGES.items():
        page = by_url.get(url)
        if not page:
            page = {"page_id": f"{eid}-mock-home", "entity_id": eid, "url": url, "label": f"{GROUPS[eid]['name']} home (mock)", "mock": True}
            pages.append(page)
        cur = latest_snapshot(page["page_id"])
        detected = now - timedelta(days=ago)
        if cur is None or page.get("mock"):
            cur = {"id": f"snp_mock_{eid}_after", "page_id": page["page_id"], "entity_id": eid, "url": url,
                   "fetched_at": _ts(detected), "text_sha256": hashlib.sha256(f"{eid}-after".encode()).hexdigest(),
                   "text": f"{GROUPS[eid]['name']} – inwestuj w akcje i ETF. (mock page text)",
                   "risk_warning": {**(after or {"present": True, "cfd_loss_pct": None, "above_fold": True}), "text": None}, "mock": True}
            snaps.append(cur)
        prev_rw = {**(before or (cur.get("risk_warning") or {})), "text": (cur.get("risk_warning") or {}).get("text")}
        prev = {"id": f"snp_mock_{eid}_before", "page_id": page["page_id"], "entity_id": eid, "url": url,
                "fetched_at": _ts(detected - timedelta(days=7)), "text_sha256": hashlib.sha256(f"{eid}-before".encode()).hexdigest(),
                "text": (cur.get("text") or "")[:2000] + "\n(mock: previous version)", "risk_warning": prev_rw, "mock": True}
        snaps.append(prev)
        changes.append({"id": f"chg_mock_{eid}", "page_id": page["page_id"], "entity_id": eid, "from_snapshot": prev["id"],
                        "to_snapshot": cur["id"], "detected_at": _ts(detected), "summary": "0 lines added, 1 removed, 0 style changes",
                        "added_lines": [], "removed_lines": ["(mock: previous version)"], "style_changes": [], "assessment": None,
                        "mock": True})
    return pages, snaps, changes
