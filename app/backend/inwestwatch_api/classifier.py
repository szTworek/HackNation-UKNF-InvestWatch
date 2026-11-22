"""Classifier interface + deterministic keyword mock ("mock-v0"). An LLM classifier implements the same classify()."""
import hashlib
import re
from datetime import datetime, timezone
from typing import Protocol

RULES = {
    "R01": "Misleading or unbalanced marketing claim",
    "R02": "Benefits shown without any risk information",
    "R03": "Risk warning not prominent (below the fold / small print)",
    "R04": "Missing CFD loss percentage",
    "R05": "Missing standard CFD risk warning",
    "R06": "Guaranteed profit / no-risk claim",
    "R07": "Past performance shown as a selling point",
    "R08": "Future performance forecast without basis",
    "R09": "Tax treatment claim without caveat",
    "R10": "Bonus or free-shares incentive",
    "R11": "Comparison with competitors without source",
    "R12": "Supervisor name used as endorsement",
    "R13": "Zero-commission claim without conditions",
    "R14": "Referral / affiliate code promotion",
    "R15": "Leverage promoted without risk context",
    "R16": "Urgency / pressure to act",
    "R17": "Trading signals / copy-trading by unlicensed author",
    "R18": "Paid promotion not disclosed",
}

# (rule_id, regex, weight). Polish + English, since a large part of the ads is EN/ES OCR.
PATTERNS = [
    ("R06", r"bez\s+ryzyka|gwarantowan\w*\s+zysk|pewny\s+zysk|zysk\w*\s+gwarantowan\w*|risk[- ]free|guaranteed\s+(profit|return)s?|no\s+risk", 0.6),
    ("R07", r"(wzr[oó]s\w*|zysk\w*|zarobi\w*|stop[aęy]\s+zwrotu|return\w*)\s+(o\s+|of\s+)?\+?\d{2,4}(,\d+)?\s?%|\+\d{2,4}(,\d+)?\s?%", 0.35),
    ("R08", r"(zarobisz|zarobi[cć]\s+\d|będziesz\s+zarabia\w*|pasywn\w+\s+doch\w*|you\s+will\s+earn|\d[\d\s]*\s?z[lł]\s+(miesięcznie|dziennie))", 0.3),
    ("R09", r"bez\s+podatk\w*|nie\s+płacisz\s+podatk\w*|tax[- ]free|zwolnion\w*\s+z\s+podatk\w*", 0.25),
    ("R10", r"akcj\w*\s+za\s+darmo|darmow\w*\s+akcj\w*|free\s+(stock|share)s?|bonus\w*|do\s+\d+\s?(€|eur|zł|pln|usd|\$)\s+w\s+akcj", 0.35),
    ("R11", r"najlepsz\w*\s+(broker|platform|aplikacj)|lepsz\w*\s+niż|best\s+broker|no\.?\s?1\b|nr\s?1\b", 0.2),
    ("R12", r"(nadzorowan\w*|licencjonowan\w*|regulowan\w*)\s+przez\s+knf|zatwierdzon\w*\s+przez\s+knf", 0.25),
    ("R13", r"0\s?%\s+prowizji|bez\s+prowizji|zero\s+(commission|prowizji)|commission[- ]free|0%\s+commission", 0.25),
    ("R14", r"kod\w*\s+(polecaj\w*|referencyjn\w*|promocyjn\w*|rabatow\w*)|referral\s+code|z\s+(mojego|naszego)\s+linku|link\w*\s+(w\s+opisie|afiliacyjn\w*|polecaj\w*)|wpisz\s*:?\s*[A-Z0-9]{3,}", 0.4),
    ("R15", r"(dźwigni\w*|lewar\w*|leverage)\s*(do\s+|up\s+to\s+|of\s+)?1\s?:\s?\d+", 0.3),
    ("R16", r"tylko\s+(dziś|dzis|teraz|do\s+końca)|ostatni\w*\s+szans\w*|oferta\s+ważna\s+do|\blimited\s+time\b|\bact\s+now\b|zostało\s+\d+", 0.25),
    ("R17", r"sygnał\w*\s+(forex|trading\w*|kupna|sprzedaży|inwestycyjn\w*)|sygnały|sygnaly|kopiuj\w*\s+moje\s+transakcj\w*|copy\s+my\s+trades|grup\w*\s+(na\s+)?(whatsapp|telegram)|kup\s+teraz|cel\s+cenowy|rekomendacj\w*\s+(kupna|sprzedaży)|polecam\s+(kupić|kupno)", 0.45),
    ("R17", r"t\.me/|whatsapp|telegram|copy\s?trad\w*|kopiuj\w*\s+transakcj\w*", 0.25),
]
_RX = [(rid, re.compile(rx, re.I), w) for rid, rx, w in PATTERNS]
# Context that voids a hit when found within ~40 chars around it (negation, demo accounts, discounts, bonds, disclaimers).
CONTEXT_EXCLUDE = {
    "R06": re.compile(r"\bdemo|\bnie\s+(ma|daje|gwarant)|\bno\s+guarantee|\bnot\b|obligacj|\bedo\b|ćwicze", re.I),
    "R08": re.compile(r"no\s+guarantee|\bnot\b|nie\s+ma\s+gwarancji|\bnie\s+(zarobisz|będziesz)", re.I),
    "R07": re.compile(r"zniżk|rabat|taniej|discount|\boff\b|promocj", re.I),
    "R17": re.compile(r"not\s+(amount\s+to|constitute)\s+investment\s+advice|nie\s+stanowi\s+rekomendacji", re.I),
}
# Third-party incentive hits count for an entity only if the entity is named near them.
NEAR_ENTITY = {"R10", "R13", "R14"}

RISK_RX = re.compile(r"ryzyk\w*|strat\w*|tracą|utrat\w*|risk|lose\s+money|losing|capital\s+at\s+risk|kapitał\s+zagrożony", re.I)
LOSS_PCT_RX = re.compile(r"\d{2}(,\d+)?\s?%\s*(rachunk|of\s+retail|retail|inwestor|klient)", re.I)
CFD_RX = re.compile(r"\bcfd|forex|dźwigni|lewar|leverage|kontrakt\w*\s+(na\s+)?różnic", re.I)
PROMO_RX = re.compile(r"\b(inwestuj\w*|zainwestuj|otwórz\s+konto|zarejestruj\w*|załóż\s+konto|zacznij\s+inwest\w*|invest(ing)?|trade|trading|sign\s+up|open\s+(an\s+)?account|kupuj|handluj|zarabiaj)\b", re.I)
AD_SECTIONS = ("ad_body", "title", "ocr", "post", "description", "link_description", "page", "transcript")

MODEL = "mock-v0"


class Classifier(Protocol):
    model: str

    def classify(self, item: dict) -> list[dict]: ...


def _snippet(text, start, end, pad=50):
    s, e = max(0, start - pad), min(len(text), end + pad)
    return ("…" if s else "") + text[s:e].replace("\n", " ") + ("…" if e < len(text) else "")


def _near_entity(eid, body, span, window=150):
    from .entities import mentions
    if not span:
        return True
    return mentions(eid, body[max(0, span[0] - window):span[1] + window])


def _severity(score):
    return "high" if score >= 0.8 else "medium" if score >= 0.5 else "low"


def _score(weights):
    p = 1.0
    for w in weights:
        p *= 1 - w
    return round(1 - p, 2)


class MockClassifier:
    """Deterministic keyword rules. Module routing:
    M2 = author is the entity; M3 = third party with advisory/signal hits; M1 = third party promoting the entity."""
    model = MODEL

    def classify(self, item: dict) -> list[dict]:
        text = {k: v for k, v in (item.get("text") or {}).items() if isinstance(v, str) and v.strip()}
        if not text or not item.get("entity_ids"):
            return []
        hits = []
        for sec, body in text.items():
            if sec not in AD_SECTIONS:
                continue
            for rid, rx, w in _RX:
                m = next((m for m in rx.finditer(body)
                          if not (rid in CONTEXT_EXCLUDE and CONTEXT_EXCLUDE[rid].search(body[max(0, m.start() - 40):m.end() + 40]))), None)
                if m and not any(h["rule_id"] == rid for h in hits):
                    hits.append({"rule_id": rid, "label": RULES[rid], "evidence": _snippet(body, *m.span()),
                                 "section": sec, "span": list(m.span()), "_w": w})
        full = "\n".join(text.values())
        main_sec = next((s for s in AD_SECTIONS if s in text), next(iter(text)))
        main = text[main_sec]
        has_risk = bool(RISK_RX.search(full))
        is_cfd = bool(CFD_RX.search(full))
        is_promo = bool(PROMO_RX.search(full)) or bool(hits)

        def absent(rid, w):
            hits.append({"rule_id": rid, "label": RULES[rid], "evidence": _snippet(main, 0, 0, 120),
                         "section": main_sec, "span": None, "_w": w})

        author_eid = item.get("author_entity_id")
        is_web = item.get("channel") == "website"
        if is_cfd and not has_risk:
            absent("R05", 0.5)
        if is_cfd and not LOSS_PCT_RX.search(full):
            absent("R04", 0.4)
        if is_promo and not has_risk and not is_cfd:
            absent("R02", 0.3)
        if is_web:
            rw = (item.get("source_meta") or {}).get("risk_warning") or {}
            if rw and rw.get("above_fold") is False:
                absent("R03", 0.35)
        sm = item.get("source_meta") or {}
        if not author_eid and sm.get("has_paid_product_placement") is False and any(h["rule_id"] == "R14" for h in hits):
            absent("R18", 0.3)

        findings = []
        now = item.get("_classified_at") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        def emit(eid, module, hs):
            if not hs:
                return
            score = _score(h["_w"] for h in hs)
            fid = "fnd_" + hashlib.sha1(f"{item['id']}|{eid}|{module}|{MODEL}".encode()).hexdigest()[:12]
            findings.append({"id": fid, "item_id": item["id"], "entity_id": eid, "module": module,
                             "score": score, "severity": _severity(score),
                             "rule_hits": [{k: v for k, v in h.items() if k != "_w"} for h in hs],
                             "model": MODEL, "created_at": now, "mock": bool(item.get("mock"))})

        if author_eid:
            emit(author_eid, "M2", [h for h in hits if h["rule_id"] != "R17"])
            return findings
        advisory = [h for h in hits if h["rule_id"] in ("R17", "R07", "R08", "R06")]
        strong = any(h["rule_id"] == "R17" and h["_w"] >= 0.45 for h in advisory)
        weak_plus = any(h["rule_id"] == "R17" for h in advisory) and any(h["rule_id"] != "R17" for h in advisory)
        for eid in item["entity_ids"]:
            if strong or weak_plus:
                emit(eid, "M3", advisory)
            if is_promo:
                emit(eid, "M1", [h for h in hits if h["rule_id"] != "R17"
                                 and (h["rule_id"] not in NEAR_ENTITY or _near_entity(eid, text[h["section"]], h["span"]))])
        return findings


classifier: Classifier = MockClassifier()
