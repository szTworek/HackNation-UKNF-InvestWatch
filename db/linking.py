"""PoC entity groups (KNF registry names, brand domains) and record -> entity linking (moved from app/backend)."""
import re

# Brand group -> KNF registry entry names, brand domains, name patterns, official author names, homonym exclusions.
GROUPS = {
    "xtb": {
        "name": "XTB",
        "registry": ["XTB S.A.", "XTB Ltd"],
        "domains": ["xtb.com", "xtb.pl"],
        "alias": r"\bxtb\b|x-trade brokers",
        "official": ["xtb s.a.", "xtb online investing", "xtbpl", "xtb polska", "xtb ltd", "xtb"],
        "exclude": r"shimano|\bksw\b|ebilet|gala|deore|slx|kaseta|korba",
    },
    "etoro": {
        "name": "eToro",
        "registry": ["Etoro (Europe) Ltd"],
        "domains": ["etoro.com"],
        "alias": r"\betoro\b",
        "official": ["etoro", "etoro group ltd.", "etoro (europe) ltd", "etoro_official", "etoro polska"],
        "exclude": None,
    },
    "plus500": {
        "name": "Plus500",
        "registry": ["Plus500CY Ltd", "Plus500EE AS"],
        "domains": ["plus500.com", "plus500.pl"],
        "alias": r"\bplus\s?500",
        "official": ["plus500 ltd", "plus500cy ltd", "plus500ee as", "plus500official", "plus500"],
        "exclude": None,
    },
    "trading212": {
        "name": "Trading 212",
        "registry": ["Trading 212 EU GmbH", "Trading 212 Ltd", "Trading 212 Markets Ltd"],
        "domains": ["trading212.com"],
        "alias": r"\btrading\s?212\b",
        "official": ["trading 212 markets ltd", "trading 212 ltd", "trading 212 eu gmbh", "trading212", "trading 212"],
        "exclude": None,
    },
    "revolut": {
        "name": "Revolut",
        "registry": ["Revolut Securities Europe UAB"],
        "domains": ["revolut.com"],
        "alias": r"\brevolut\b",
        "official": ["revolut", "revolut ltd", "revolut securities europe uab", "revolut bank uab", "revolut polska"],
        "exclude": None,
    },
}

_ALIAS = {eid: re.compile(g["alias"], re.I) for eid, g in GROUPS.items()}
_EXCL = {eid: re.compile(g["exclude"], re.I) for eid, g in GROUPS.items() if g["exclude"]}
_DOMAIN = {eid: re.compile("|".join(re.escape(d) for d in g["domains"]), re.I) for eid, g in GROUPS.items()}


# Official social profiles shown on the entity card.
HANDLES = {"xtb": {"youtube": "XTBPolska", "tiktok": "xtbpl"}, "etoro": {"tiktok": "etoro_official"},
           "plus500": {"tiktok": "plus500official"}, "trading212": {"tiktok": "trading212"}, "revolut": {"tiktok": "revolut"}}


def is_official(eid, author):
    return bool(author) and author.strip().lower() in GROUPS[eid]["official"]


def mentions(eid, text):
    return bool(_ALIAS[eid].search(text) or _DOMAIN[eid].search(text))


def link(rec):
    """Return (entity_ids, author_entity_id) for a normalized record."""
    author = rec.get("author") or ""
    sponsor = rec.get("sponsor") or ""
    sm = rec.get("source_meta") or {}
    body = " \n".join(rec["text"].values())
    side = " ".join([author, sponsor, " ".join(str(x) for x in (rec.get("links") or [])),
                     str(sm.get("domain") or ""), str(sm.get("display_url") or "")])
    hay = body + " \n" + side
    firm = (sm.get("firm") or "").lower().replace(" ", "")
    ids, author_eid = [], None
    for eid in GROUPS:
        official = is_official(eid, author) or is_official(eid, sponsor)
        if sm.get("advertiser_is_firm") and firm == eid:
            official = True
        hit = official or _ALIAS[eid].search(hay) or _DOMAIN[eid].search(hay)
        if not hit:
            continue
        if not official and eid in _EXCL and _EXCL[eid].search(hay):
            continue
        ids.append(eid)
        if official and author_eid is None:
            author_eid = eid
    return ids, author_eid
