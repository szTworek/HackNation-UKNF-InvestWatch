"""Ekstrakcja wskaźników do grafu kampanii: domeny, telefony, Telegram/WhatsApp, e-maile, portfele krypto, IBAN."""

from __future__ import annotations

import re
from urllib.parse import urlparse

# domeny zbyt popularne, by łączyć przez nie rekordy
COMMON_DOMAINS = {
    "youtube.com", "youtu.be", "facebook.com", "fb.com", "instagram.com", "tiktok.com", "x.com", "twitter.com",
    "google.com", "goo.gl", "bit.ly", "linktr.ee", "t.co", "reddit.com", "wikipedia.org", "spotify.com",
    "apple.com", "linkedin.com", "discord.gg", "discord.com", "patreon.com", "amzn.to", "amazon.com",
    "web.archive.org", "archive.org",
}

URL_RE = re.compile(r"https?://[^\s)\]>\"']+", re.I)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?48[\s-]?)?(?:\d{3}[\s-]?\d{3}[\s-]?\d{3})(?!\d)")
TG_RE = re.compile(r"(?:t\.me/|telegram\.me/|@)([A-Za-z0-9_]{5,32})\b")
WA_RE = re.compile(r"wa\.me/(\+?\d{8,15})|whatsapp[^\d+]{0,20}(\+?\d[\d\s-]{8,16}\d)", re.I)
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
WALLET_RES = {
    "btc": re.compile(r"\b(?:bc1[a-z0-9]{25,60}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b"),
    "eth": re.compile(r"\b0x[a-fA-F0-9]{40}\b"),
    "trx": re.compile(r"\bT[1-9A-HJ-NP-Za-km-z]{33}\b"),
}
IBAN_RE = re.compile(r"\b(?:PL)?\d{2}(?:[\s]?\d{4}){6}\b")


def domain_of(url: str) -> str | None:
    try:
        host = urlparse(url).netloc.lower().split("@")[-1].split(":")[0]
    except ValueError:
        return None
    return host[4:] if host.startswith("www.") else host or None


def registered_domain(host: str) -> str:
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"com", "net", "org", "co", "gov", "edu"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def extract(text: str, links: list[str] | None = None) -> list[dict[str, str]]:
    out: dict[tuple[str, str], dict[str, str]] = {}

    def add(t: str, v: str) -> None:
        v = v.strip()
        if v:
            out.setdefault((t, v.lower()), {"type": t, "value": v})

    for u in list(links or []) + URL_RE.findall(text):
        host = domain_of(u)
        if host and registered_domain(host) not in COMMON_DOMAINS and host not in COMMON_DOMAINS:
            add("domain", registered_domain(host))
    for m in PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        if len(digits) in (9, 11):
            add("phone", "+48" + digits[-9:])
    for m in TG_RE.finditer(text):
        if "t.me" in m.group(0) or "telegram" in text[max(0, m.start() - 40): m.start()].lower():
            add("telegram", m.group(1))
    for m in WA_RE.finditer(text):
        add("whatsapp", re.sub(r"[\s-]", "", m.group(1) or m.group(2)))
    for m in EMAIL_RE.finditer(text):
        add("email", m.group(0))
    for kind, rx in WALLET_RES.items():
        for m in rx.finditer(text):
            add("wallet", f"{kind}:{m.group(0)}")
    for m in IBAN_RE.finditer(text):
        add("iban", re.sub(r"\s", "", m.group(0)))
    return list(out.values())
