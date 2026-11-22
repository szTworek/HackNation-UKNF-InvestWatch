"""Build data/entity_fixtures.json from real sample records (data/export) and website monitor output (data/monitor; falls back to data/samples/firm_web_v1.jsonl).

Mock classifier (model "mock-v0"): keyword rules only. Page history before the real snapshot is synthetic (mock: true).
Run: python scripts/build_fixtures.py
"""
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parents[1]
sys.path.insert(0, str(BACKEND))
from inwestwatch_api.entities import GROUPS, link, registry_entries  # noqa: E402

rnd = random.Random(7)
NOW = datetime(2026, 11, 21, 22, 0, tzinfo=timezone.utc)
SOURCES = {"google_ads": ("ad", "google_ads"), "meta_ads": ("ad", "meta_ads"), "bing_ads": ("ad", "bing_ads"),
           "youtube": ("social", "youtube"), "tiktok": ("social", "tiktok")}
MAXTXT = 1800
MAXLINES = 60  # OCR lines kept per item (longest creatives have a few hundred)

RULES = {
    "R01": "Firm identification missing", "R02": "Not labelled as advertising", "R03": "Profit claim without risk information",
    "R04": "Risk warning font size", "R05": "Risk warning exposure and contrast", "R06": "Risk hidden in footnotes",
    "R07": "Risk info not within one click", "R08": "Responsiveness across devices", "R09": "Clarity for target audience",
    "R10": "Risk warning in another language", "R11": "Product comparison without source", "R12": "Historical performance: period and currency",
    "R13": "Historical performance dominates", "R14": "No past-performance disclaimer", "R15": "Forecast without disclaimer",
    "R16": "Tax treatment without caveat", "R17": "Suggests supervisor approval", "R18": "Supervision used as safety argument",
}
M1_LABELS = {"M1.REF": "Referral / affiliate promotion", "M1.NORISK": "Third-party promotion without risk info",
             "M1.PAID": "Paid placement by third party"}
M3_LABELS = {"M3.REC": "Buy/sell recommendation", "M3.RET": "Return promise", "M3.SIG": "Signals / closed group invite"}

RISK = re.compile(r"ryzyk|strat|risk|lose money|tracą|traci|odnotowuje straty|capital at risk", re.I)
PROFIT = re.compile(r"zarabia\w*|zysk\w*|0% prowizji|\d+[,.]?\d*\s?% (?:odsetek|rocznie|zwrotu)|odset\w+|darmo\w*|free (?:stock|share)\w*|bonus\w*|earn\w*|profit\w*|dywidend\w*|pasywn\w*", re.I)
HIST = re.compile(r"S&P ?500[^.]{0,60}\d|w latach \d{4}|średnioroczn\w+|historyczn\w+|past performance|wzrost o \d+", re.I)
HIST_OK = re.compile(r"nie stanowi\w* (?:wiarygodnego|gwarancji)|not a reliable|rzeczywisty wynik może być inny", re.I)
FORECAST = re.compile(r"\bbędzie\b[^.]{0,40}(?:rosn|zarab|wart)|wzrośnie|\bwill (?:grow|rise|earn)|prognoz\w+", re.I)
TAX = re.compile(r"\bIKE\b|\bIKZE\b|podat\w+|\btax\w*", re.I)
TAX_OK = re.compile(r"indywidualn\w+ sytuacji|individual circumstances", re.I)
SUPER = re.compile(r"\bKNF\b|nadzor\w*|regulowan\w+|regulated|CySEC|\bFCA\b|BaFin", re.I)
SAFE = re.compile(r"bezpieczn\w*|safe\w*|chronion\w*|protected", re.I)
REF = re.compile(r"kod\w* (?:polecaj\w+|referencyjn\w+|promocyjn\w+)|z kodem \w+|z (?:naszego|mojego) linku|link\w* (?:polecaj|w opisie)|referral|kod [A-Z]{4,}|\bpolecam\b", re.I)
REC = re.compile(r"\bkup(?:uj|ić|ię|iłem)?\b[^.]{0,30}akcj|sprzeda(?:j|ć)\b|polecam (?:kupić|akcje)|\bbuy\b|\bsell\b|cel cenowy|target price|wejdź w|warto kupić|lista akcji", re.I)
RET = re.compile(r"wzrost o \d+[,.]?\d*\s?%|\d+[,.]?\d*\s?% (?:zysku|miesięcznie|w miesiąc)|pewny zysk|gwarantowan\w+|1000 ?zł (?:miesięcznie|pasywnie)", re.I)
SIG = re.compile(r"whatsapp|telegram|sygnał\w*|grup\w+ (?:vip|zamknięt)|t\.me/", re.I)


def h(s, n=10):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:n]


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def hit(rule_id, label, section, text, m, pad=60):
    a, b = max(0, m.start() - pad), min(len(text), m.end() + pad)
    return {"rule_id": rule_id, "label": label, "evidence": ("…" if a else "") + text[a:b].strip() + ("…" if b < len(text) else ""),
            "section": section, "span": [m.start(), m.end()]}


def first(rx, text_map, skip=()):
    for sec, t in text_map.items():
        if sec in skip:
            continue
        m = rx.search(t)
        if m:
            return sec, t, m
    return None


def classify(item):
    """Return list of (module, score, rule_hits)."""
    tm, out, all_text = item["text"], [], " \n".join(item["text"].values())
    has_risk = bool(RISK.search(all_text))
    if item["author_is_entity"]:
        hits = []
        p = first(PROFIT, tm)
        if p and not has_risk:
            hits.append((0.35, hit("R03", RULES["R03"], *p)))
        x = first(HIST, tm)
        if x and not HIST_OK.search(all_text):
            hits.append((0.25, hit("R14", RULES["R14"], *x)))
        x = first(FORECAST, tm)
        if x:
            hits.append((0.2, hit("R15", RULES["R15"], *x)))
        x = first(TAX, tm)
        if x and not TAX_OK.search(all_text):
            hits.append((0.15, hit("R16", RULES["R16"], *x)))
        x = first(SUPER, tm)
        if x:
            safe = SAFE.search(all_text)
            hits.append((0.3, hit("R18" if safe else "R17", RULES["R18" if safe else "R17"], *x)))
        rk = first(RISK, tm)
        if rk and item.get("lang_pl") and re.search(r"risk|lose money", rk[2].group(0), re.I):
            hits.append((0.2, hit("R10", RULES["R10"], *rk)))
        if item["channel"] == "ad" and not has_risk and not p:
            sec = next(iter(tm))
            hits.append((0.15, {"rule_id": "R03", "label": RULES["R03"], "evidence": "No risk information found in ad text.",
                                "section": sec, "span": [0, 0]}))
        if hits:
            score = min(0.97, 0.3 + sum(w for w, _ in hits) + rnd.uniform(0, 0.12))
            out.append(("M2", score, [x for _, x in hits]))
    else:
        hits = []
        x = first(REF, tm)
        if x:
            hits.append((0.35, hit("M1.REF", M1_LABELS["M1.REF"], *x)))
        if item.get("paid"):
            sec = next(iter(tm))
            hits.append((0.2, {"rule_id": "M1.PAID", "label": M1_LABELS["M1.PAID"], "evidence": "Platform flag: includes paid promotion.",
                               "section": sec, "span": [0, 0]}))
        if not has_risk:
            p = first(PROFIT, tm)
            if p:
                hits.append((0.25, hit("M1.NORISK", M1_LABELS["M1.NORISK"], *p)))
        if hits or item["channel"] == "social":
            score = min(0.95, 0.25 + sum(w for w, _ in hits) + rnd.uniform(0, 0.1))
            if not hits:
                sec = next(iter(tm))
                hits.append((0, {"rule_id": "M1.NORISK", "label": M1_LABELS["M1.NORISK"],
                                 "evidence": "Entity promoted by a third party; no risk information.", "section": sec, "span": [0, 0]}))
            out.append(("M1", score, [x for _, x in hits]))
        hits = []
        for rid, rx in (("M3.REC", REC), ("M3.RET", RET), ("M3.SIG", SIG)):
            x = first(rx, tm)
            if x:
                hits.append(hit(rid, M3_LABELS[rid], *x))
        if hits:
            out.append(("M3", min(0.96, 0.4 + 0.18 * len(hits) + rnd.uniform(0, 0.1)), hits))
    return out


def sev(score):
    return "high" if score >= 0.7 else "medium" if score >= 0.5 else "low"


def day_in_window(key, published):
    try:
        d = datetime.fromisoformat(published.replace("Z", "+00:00")) if published else None
        if d and d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
    except ValueError:
        d = None
    if d and NOW - timedelta(days=30) <= d <= NOW:
        return d
    r = int(h(key, 8), 16)
    # skew towards recent days so the trend rises
    days = int(29 * (1 - ((r % 1000) / 1000) ** 0.6))
    return NOW - timedelta(days=days, hours=r % 20, minutes=r % 59)


def trim_lines(lines):
    """First MAXLINES OCR lines plus every disclosure line further down (legibility_check refers to them)."""
    return lines[:MAXLINES] + [l for l in lines[MAXLINES:] if l["is_disclosure"]]


def load_items():
    items = []
    for src, (channel, platform) in SOURCES.items():
        for line in open(REPO / "data" / "export" / src / "records.jsonl", encoding="utf-8"):
            rec = json.loads(line)
            ids, author_eid = link(rec)
            if not ids:
                continue
            sm = rec.get("source_meta") or {}
            text = {k: (v[:MAXTXT] + "…" if len(v) > MAXTXT else v) for k, v in rec["text"].items() if isinstance(v, str) and v.strip()}
            if not text:
                continue
            iid = "itm_" + h(rec["source_url"] + json.dumps(rec["text"], ensure_ascii=False)[:200])
            items.append({
                "id": iid, "entity_ids": ids, "channel": channel, "platform": platform, "source_url": rec["source_url"],
                "author": rec.get("author") or rec.get("sponsor") or "unknown", "author_is_entity": author_eid is not None,
                "published_at": rec.get("published_at"), "fetched_at": rec["fetched_at"], "text": text,
                "media": rec.get("media") or [], "ocr_lines": trim_lines(sm.get("ocr_lines") or []),
                "legibility": sm.get("legibility"), "legibility_check": sm.get("legibility_check"), "mock": False,
                "lang_pl": bool(sm.get("lang_hint_pl")), "paid": bool(sm.get("has_paid_product_placement")),
            })
    seen, uniq = set(), []
    for it in items:
        if it["id"] not in seen:
            seen.add(it["id"])
            uniq.append(it)
    return uniq


CFD_PCT = re.compile(r"(\d{2})\s?% (?:rachunków|of retail|retail investor)", re.I)


def risk_warning(text):
    m = CFD_PCT.search(text)
    rw = RISK.search(text[:600])
    if not m and not rw:
        return {"present": False, "cfd_loss_pct": None, "text": None, "above_fold": False}
    start = (m or rw).start()
    a = text.rfind("\n", 0, start) + 1
    b = text.find("\n", start)
    return {"present": True, "cfd_loss_pct": int(m.group(1)) if m else None, "text": text[a:b if b > 0 else a + 300][:400],
            "above_fold": start < 600}


def pages_and_changes():
    mon = REPO / "data" / "monitor"
    if (mon / "pages.json").exists():
        pages = json.loads((mon / "pages.json").read_text(encoding="utf-8"))
        rd = lambda f: [json.loads(l) for l in open(mon / f, encoding="utf-8") if l.strip()] if (mon / f).exists() else []
        return pages, rd("snapshots.jsonl"), rd("changes.jsonl")
    pages, snaps, changes = [], [], []
    rows = [json.loads(l) for l in open(REPO / "data" / "samples" / "firm_web_v1.jsonl", encoding="utf-8")]
    for r in rows:
        ids, _ = link({**r, "text": {"page": r["text"]["page"][:3000]}})
        eid = next((e for e in GROUPS if any(d in r["source_url"] for d in GROUPS[e]["domains"])), ids[0] if ids else None)
        if not eid:
            continue
        path = re.sub(r"^https?://[^/]+", "", r["source_url"]).strip("/").split("/")
        slug = path[-1] if path and path[-1] not in ("", "pl", "pl-PL", "main") else "home"
        page_id = f"{eid}-{slug}"
        label = (r.get("title") or slug).split("|")[0].strip()[:70]
        text = r["text"]["page"][:5000]
        pages.append({"page_id": page_id, "entity_id": eid, "url": r["source_url"], "label": label})
        cur = {"id": "snp_" + h(page_id + "cur"), "page_id": page_id, "entity_id": eid, "url": r["source_url"],
               "fetched_at": r["fetched_at"], "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "text": text,
               "risk_warning": risk_warning(text), "mock": False}
        base_t = NOW - timedelta(days=12)
        prev_text = text
        lines = text.split("\n")
        rw = cur["risk_warning"]
        if rw["cfd_loss_pct"] and page_id in ("xtb-home", "plus500-home", "etoro-cfd"):
            old = rw["cfd_loss_pct"] - (2 if page_id != "plus500-home" else -1)
            prev_text = text.replace(f"{rw['cfd_loss_pct']}%", f"{old}%", 1)
        elif page_id == "etoro-interest-on-balance":
            prev_text = text.replace("3,80%", "3,50%")
        elif page_id == "revolut-home" and not rw["present"]:
            warn = "Inwestowanie wiąże się z ryzykiem. Wartość inwestycji może spaść, a Ty możesz odzyskać mniej, niż zainwestowałeś."
            prev_text = lines[0] + "\n" + warn + "\n" + "\n".join(lines[1:])
        elif page_id == "xtb-etf":
            idx = min(8, len(lines) - 1)
            prev_text = "\n".join(lines[:idx] + lines[idx + 1:])
        prev = {**cur, "id": "snp_" + h(page_id + "prev"), "fetched_at": iso(base_t), "text": prev_text,
                "text_sha256": hashlib.sha256(prev_text.encode()).hexdigest(), "risk_warning": risk_warning(prev_text), "mock": True}
        snaps += [prev, cur]
        if prev_text != text:
            pl, cl = prev_text.split("\n"), text.split("\n")
            added = [l for l in cl if l not in pl][:10]
            removed = [l for l in pl if l not in cl][:10]
            days_ago = {"xtb-home": 1, "revolut-home": 2, "etoro-interest-on-balance": 5, "xtb-etf": 9}.get(page_id, 3)
            changes.append({"id": "chg_" + h(page_id + "chg"), "page_id": page_id, "entity_id": eid, "from_snapshot": prev["id"],
                            "to_snapshot": cur["id"], "detected_at": iso(NOW - timedelta(days=days_ago, hours=3)),
                            "summary": f"{len(added)} lines added, {len(removed)} removed, 0 style changes", "added_lines": added,
                            "removed_lines": removed, "style_changes": [], "assessment": None, "mock": True})
    return pages, snaps, changes


def main():
    items = load_items()
    findings = []
    for it in items:
        for module, score, hits in classify(it):
            for eid in it["entity_ids"]:
                created = day_in_window(it["id"] + module + eid, it["published_at"])
                findings.append({"id": "fnd_" + h(it["id"] + module + eid), "item_id": it["id"], "entity_id": eid, "module": module,
                                 "score": round(score, 2), "severity": sev(score), "rule_hits": hits, "model": "mock-v0",
                                 "created_at": iso(created)})
    for it in items:
        it.pop("lang_pl")
        it.pop("paid")
    pages, snaps, changes = pages_and_changes()

    alerts = []
    for f in sorted([f for f in findings if f["severity"] == "high"], key=lambda f: f["created_at"], reverse=True):
        item = next(i for i in items if i["id"] == f["item_id"])
        rh = f["rule_hits"][0]
        title = f"{f['module']} {rh['rule_id']}: {rh['label']} — {item['author']} ({item['platform']})"
        alerts.append({"id": "alr_" + h(f["id"]), "created_at": f["created_at"], "entity_id": f["entity_id"], "kind": "finding",
                       "severity": "high", "title": title, "ref": {"finding_id": f["id"], "change_id": None}, "status": "new"})
    alerts.sort(key=lambda a: a["created_at"], reverse=True)
    for i, a in enumerate(alerts):
        if a["created_at"] < iso(NOW - timedelta(days=6)):
            a["status"] = "ack" if i % 3 else "closed"

    reg = registry_entries()
    handles = {"xtb": {"youtube": "XTBPolska", "tiktok": "xtbpl"}, "etoro": {"tiktok": "etoro_official"},
               "plus500": {"tiktok": "plus500official"}, "trading212": {"tiktok": "trading212"}, "revolut": {"tiktok": "revolut"}}
    entities = []
    for eid, g in GROUPS.items():
        ef = [f for f in findings if f["entity_id"] == eid]
        top = sorted((f["score"] for f in ef), reverse=True)[:20]
        modules = {m: {"findings": len([f for f in ef if f["module"] == m]),
                       "avg_score": round(sum(f["score"] for f in ef if f["module"] == m) / max(1, len([f for f in ef if f["module"] == m])), 2)}
                   for m in ("M1", "M2", "M3")}
        eitems = [i for i in items if eid in i["entity_ids"]]
        entities.append({
            "id": eid, "name": g["name"], "registry_entries": [{"name": r["name"], "category": r["category"], "country": r["country"]} for r in reg.get(eid, [])],
            "domains": g["domains"], "monitored_pages": len([p for p in pages if p["entity_id"] == eid]), "social_handles": handles[eid],
            "kpis": {"items": len(eitems), "findings_open": len(ef),
                     "alerts_new": len([a for a in alerts if a["entity_id"] == eid and a["status"] == "new"]),
                     "risk_score": round(sum(top) / len(top), 2) if top else 0,
                     "pages_changed_7d": len({c["page_id"] for c in changes if c["entity_id"] == eid and c["detected_at"] >= iso(NOW - timedelta(days=7))})},
            "modules": modules, "platforms": dict(Counter(i["platform"] for i in eitems)),
        })

    by_day = defaultdict(lambda: {"M1": 0, "M2": 0, "M3": 0})
    for f in findings:
        by_day[f["created_at"][:10]][f["module"]] += 1
    days = [(NOW - timedelta(days=d)).strftime("%Y-%m-%d") for d in range(29, -1, -1)]
    rules = Counter((rh["rule_id"], rh["label"]) for f in findings for rh in f["rule_hits"])
    overview = {
        "totals": {"entities": len(entities), "items": len(items), "findings": len(findings),
                   "alerts_new": len([a for a in alerts if a["status"] == "new"]), "pages": len(pages),
                   "page_changes_30d": len(changes)},
        "findings_by_day": [{"date": d, **by_day[d]} for d in days],
        "items_by_platform": dict(Counter(i["platform"] for i in items)) | ({"website": len(pages)} if pages else {}),
        "heatmap": [{"entity_id": e["id"], **{m: e["modules"][m]["avg_score"] if e["modules"][m]["findings"] else 0 for m in ("M1", "M2", "M3")}} for e in entities],
        "top_rules": [{"rule_id": r, "label": l, "count": c} for (r, l), c in rules.most_common(10)],
    }
    out = {"generated_at": iso(NOW), "entities": entities, "items": items, "findings": findings, "pages": pages,
           "snapshots": snaps, "changes": changes, "alerts": alerts, "overview": overview}
    dst = REPO / "data" / "entity_fixtures.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"items={len(items)} findings={len(findings)} pages={len(pages)} changes={len(changes)} alerts={len(alerts)} "
          f"size={dst.stat().st_size // 1024}KB modules={Counter(f['module'] for f in findings)}")
    for e in entities:
        print(e["id"], e["kpis"], e["platforms"])


main()
