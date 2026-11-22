"""Demo history (mock: true): earlier snapshots derived from the first real snapshot of a page, so the timeline has changes.

  python -m monitor.seed_demo           # add demo history (skips pages that already have mock rows)
  python -m monitor.seed_demo --reset   # drop all mock rows from snapshots/changes, then seed again
"""
import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta

from monitor.diff import compare
from monitor.extract import WARNING_RE, risk_warning, sha256
from monitor.run import CHANGES, PAGES, SNAPSHOTS, append_jsonl, read_jsonl

PROMO_RE = re.compile(r"bonus|0\s?% prowizji|bez prowizji|oprocentowan|odsetk|darmow|cashback|nagrod|promocj|zarabiaj|free", re.I)
EXTRA_WARNING = (" Zastanów się, czy rozumiesz, jak działają kontrakty CFD, i czy możesz pozwolić sobie na wysokie "
                 "ryzyko utraty pieniędzy. Przed podjęciem decyzji inwestycyjnej zapoznaj się z dokumentem Informacje o ryzyku.")


def shift(ts, days, hours=0):
    t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ") - timedelta(days=days, hours=hours)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def mock_snapshot(base, lines, fetched_at):
    text = "\n".join(lines)
    rw = risk_warning(lines)
    rw["above_fold"] = base["risk_warning"]["above_fold"] if rw["present"] else None
    return {**base, "id": "snp_" + hashlib.sha1(f"{base['page_id']}|{fetched_at}".encode()).hexdigest()[:12],
            "fetched_at": fetched_at, "text": text, "text_sha256": sha256(text), "risk_warning": rw, "mock": True}


def loss_77(base):
    pct = base["risk_warning"]["cfd_loss_pct"]
    if not pct:
        return None
    old = pct - 2
    lines = [re.sub(rf"\b{pct}(\s?%)", rf"{old}\1", l) if WARNING_RE.search(l) else l for l in base["text"].splitlines()]
    return [(lines, 12)]


def warning_longer(base):
    w = base["risk_warning"]["text"]
    if not w:
        return None
    lines = [l + EXTRA_WARNING if l.startswith(w[:60]) else l for l in base["text"].splitlines()]
    return [(lines, 6)]


def warning_removed_then_restored(base):
    lines = base["text"].splitlines()
    stripped = [l for l in lines if not WARNING_RE.search(l)]
    if len(stripped) == len(lines):
        return None
    return [(lines, 14), (stripped, 4)]


def promo_added(base):
    lines = base["text"].splitlines()
    promo = next((l for l in lines if PROMO_RE.search(l) and 15 < len(l) < 200 and not WARNING_RE.search(l)), None)
    if not promo:
        return None
    return [([l for l in lines if l != promo], 8)]


# page_id candidates per scenario (first one with a real snapshot that fits wins)
SCENARIOS = [
    (loss_77, ["xtb-home", "xtb-forex", "plus500-home"]),
    (warning_longer, ["etoro-cfd", "etoro-home", "plus500-forex"]),
    (warning_removed_then_restored, ["xtb-etf", "xtb-indices", "plus500-indices"]),
    (promo_added, ["revolut-stocks", "xtb-interest", "plus500-promo-bulls", "etoro-interest", "revolut-home"]),
    (loss_77, ["plus500-forex", "plus500-indices", "trading212-help-cfd"]),
    (promo_added, ["trading212-help-cfd", "trading212-help-fees", "trading212-help-cfd-loss"]),
]


T212_WARN = ("Kontrakty CFD są złożonymi instrumentami i wiążą się z wysokim ryzykiem szybkiej utraty środków pieniężnych "
             "z powodu dźwigni finansowej. {pct}% rachunków inwestorów detalicznych traci pieniądze w wyniku handlu "
             "kontraktami CFD u tego dostawcy. Zastanów się, czy rozumiesz, jak działają kontrakty CFD, i czy możesz "
             "pozwolić sobie na wysokie ryzyko utraty pieniędzy.")
ETORO_WARN = ("Kontrakty CFD są złożonymi instrumentami i wiążą się z wysokim ryzykiem szybkiej utraty pieniędzy z powodu "
              "dźwigni finansowej. {pct}% rachunków inwestorów detalicznych traci pieniądze w wyniku handlu kontraktami CFD "
              "u tego dostawcy.")
CRYPTO_WARN = "Aktywa kryptowalutowe są wysoce zmienne i nieregulowane. Twój kapitał jest zagrożony."
# Pages whose site blocks automated access (Cloudflare challenge / 429): realistic content, two versions each (old, current).
BLOCKED_MOCK = {
    "trading212-home": (["Trading 212", "Inwestuj w akcje i ETF-y bez prowizji", T212_WARN.format(pct=76),
                         "Ponad 4 miliony klientów", "Otwórz konto"],
                        ["Trading 212", "Inwestuj w akcje i ETF-y bez prowizji", "Odsetki 4,5% od niezainwestowanych środków",
                         T212_WARN.format(pct=77), "Ponad 4 miliony klientów", "Otwórz konto"]),
    "trading212-cfd": (["CFD na ponad 10 000 instrumentów", "Dźwignia do 1:30", T212_WARN.format(pct=76), "Konto demo"],
                       ["CFD na ponad 10 000 instrumentów", "Dźwignia do 1:30", T212_WARN.format(pct=77), "Konto demo"]),
    "trading212-invest": (["Konto Invest", "Akcje ułamkowe od 1 zł", "Inwestowanie wiąże się z ryzykiem utraty kapitału."],
                          ["Konto Invest", "Akcje ułamkowe od 1 zł", "Zero prowizji za transakcje"]),
    "trading212-pricing": (["Opłaty", "Brak prowizji za transakcje", "Przewalutowanie 0,15%", T212_WARN.format(pct=77)],
                           ["Opłaty", "Brak prowizji za transakcje", "Przewalutowanie 0,15%", T212_WARN.format(pct=77)]),
    "trading212-legal": (["Dokumenty prawne", "Regulamin", "Polityka realizacji zleceń", "Ujawnienie ryzyka", T212_WARN.format(pct=77)],
                         ["Dokumenty prawne", "Regulamin", "Polityka realizacji zleceń", "Ujawnienie ryzyka", T212_WARN.format(pct=77)]),
    "etoro-fees": (["Opłaty eToro", "0% prowizji od akcji", "Opłata za wypłatę 5 USD", ETORO_WARN.format(pct=55)],
                   ["Opłaty eToro", "0% prowizji od akcji", "Opłata za wypłatę 5 USD", ETORO_WARN.format(pct=55)]),
    "etoro-crypto": (["Kup kryptowaluty na eToro", "Bitcoin, Ethereum i ponad 100 innych", CRYPTO_WARN],
                     ["Kup kryptowaluty na eToro", "Bitcoin, Ethereum i ponad 100 innych", "Bonus 10 USD na start"]),
    "etoro-risk-disclosure": (["Ogólne ujawnienie ryzyka", ETORO_WARN.format(pct=55), "Wyniki osiągnięte w przeszłości nie gwarantują przyszłych wyników."],
                              ["Ogólne ujawnienie ryzyka", ETORO_WARN.format(pct=55), "Wyniki osiągnięte w przeszłości nie gwarantują przyszłych wyników."]),
}


def seed_blocked(snaps, pages, t_ref):
    real = {s["page_id"] for s in snaps if not s.get("mock")}
    new_snaps, new_changes = [], []
    for pid, (old, cur) in BLOCKED_MOCK.items():
        if pid in real or pid not in pages:
            continue
        p = pages[pid]
        base = {"id": None, "page_id": pid, "entity_id": p["entity_id"], "url": p["url"], "fetched_at": None,
                "text_sha256": None, "text": "", "risk_warning": {"above_fold": True}, "http_status": 200,
                "final_url": p["url"], "mock": True}
        a, b = mock_snapshot(base, old, shift(t_ref, 9, 2)), mock_snapshot(base, cur, shift(t_ref, 0, 1))
        new_snaps += [a, b]
        c = compare(a, b, b["fetched_at"], mock=True)
        if c:
            new_changes.append(c)
            print(f"{'blocked_mock':32} {pid}: {c['summary']}")
    return new_snaps, new_changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    a = ap.parse_args()
    snaps, changes = read_jsonl(SNAPSHOTS), read_jsonl(CHANGES)
    if a.reset:
        snaps, changes = [s for s in snaps if not s.get("mock")], [c for c in changes if not c.get("mock")]
        for path, rows in ((SNAPSHOTS, snaps), (CHANGES, changes)):
            path.write_text("", encoding="utf-8")
            append_jsonl(path, rows)
    first_real, has_mock = {}, {s["page_id"] for s in snaps if s.get("mock")}
    for s in snaps:
        if not s.get("mock") and s["text"] and (s["page_id"] not in first_real or s["fetched_at"] < first_real[s["page_id"]]["fetched_at"]):
            first_real[s["page_id"]] = s
    used, new_snaps, new_changes = set(has_mock), [], []
    for fn, candidates in SCENARIOS:
        for pid in candidates:
            if pid in used or pid not in first_real:
                continue
            base = first_real[pid]
            steps = fn(base)
            if not steps:
                continue
            chain = [mock_snapshot(base, lines, shift(base["fetched_at"], days, 3)) for lines, days in steps] + [base]
            for prev, cur in zip(chain, chain[1:]):
                c = compare(prev, cur, cur["fetched_at"], mock=True)
                if c:
                    new_changes.append(c)
            new_snaps += chain[:-1]
            used.add(pid)
            print(f"{fn.__name__:32} {pid}: " + " | ".join(c["summary"] for c in new_changes if c["page_id"] == pid))
            break
    pages = {p["page_id"]: p for p in json.loads(PAGES.read_text(encoding="utf-8"))}
    t_ref = max(s["fetched_at"] for s in snaps if not s.get("mock"))
    bs, bc = seed_blocked(snaps, pages, t_ref)
    new_snaps += bs
    new_changes += bc
    append_jsonl(SNAPSHOTS, new_snaps)
    append_jsonl(CHANGES, new_changes)
    print(json.dumps({"mock_snapshots": len(new_snaps), "mock_changes": len(new_changes)}))


if __name__ == "__main__":
    main()
