"""Agregator: z prawdopodobieństw modelu + progów liczy reguły UKNF, moduły, scam i poziom ryzyka.

Czyste funkcje bez modelu – używane przez /analyze i /rescore (zmiana progów w panelu kalibracji
przelicza wyniki bez ponownej inferencji). Logika jest jawna i edytowalna.
"""

from __future__ import annotations

from typing import Any

from .labels import FLAG_KEYS

DEFAULT_THRESHOLDS: dict[str, float] = {
    **{f"flags.{k}": 0.5 for k in FLAG_KEYS},
    "topic.INVESTMENT": 0.5,
    "contentType.FIRM_OWN_MARKETING": 0.35,
    "contentType.THIRD_PARTY_PROMO": 0.35,
    "contentType.SERVICE_OFFER": 0.35,
    "contentType.RECOMMENDATION": 0.35,
    "scam": 0.6,
    "risk.MEDIUM": 0.4,
    "risk.HIGH": 0.65,
    "risk.CRITICAL": 0.85,
}

# id reguły -> (nazwa, czy wykrywalna z tekstu)
RULES: dict[str, tuple[str, bool]] = {
    "1": ("Identyfikacja firmy", True),
    "2": ("Oznaczenie reklamy", True),
    "3": ("Informacja o ryzyku przy zyskach", True),
    "4": ("Rozmiar czcionki ryzyka", False),
    "5": ("Ekspozycja i kontrast ryzyka", False),
    "6": ("Zakrywanie / ukrywanie ryzyka", False),
    "7": ("Dostępność za 1 kliknięciem", False),
    "8": ("Responsywność", False),
    "9": ("Zrozumiałość dla grupy docelowej", False),
    "10": ("Spójność językowa", False),
    "11": ("Porównania produktów / usług", True),
    "12a": ("Wyniki historyczne – okres i zakres", False),
    "12b": ("Wyniki historyczne – warunki i waluta", False),
    "13": ("Dominacja wyników historycznych", False),
    "14": ("Ostrzeżenie przy wynikach historycznych", True),
    "15": ("Prognozy przyszłych wyników", True),
    "16": ("Informacja podatkowa", True),
    "17": ("Zakaz sugerowania aprobaty organu nadzoru", True),
    "18": ("Nadzór jako argument bezpieczeństwa", True),
    "M1": ("Moduł 1: reklama firmy przez podmiot trzeci", True),
    "M3": ("Moduł 3: możliwe doradztwo bez zezwolenia", True),
    "SCAM": ("Cechy oszustwa inwestycyjnego", True),
}

MARKETING_RULES = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12a", "12b", "13", "14", "15", "16", "17", "18"}
ADVISORY_INSTRUMENTS = {"CFD_FOREX", "STOCKS", "FUNDS_ETF", "BONDS", "OTHER_DERIVATIVES"}


def _t(th: dict[str, float], key: str) -> float:
    return th.get(key, DEFAULT_THRESHOLDS.get(key, 0.5))


def compute(pred: dict[str, Any], entities: list[dict[str, Any]], thresholds: dict[str, float] | None = None,
            extra_scam_signals: list[str] | None = None) -> dict[str, Any]:
    th = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    fp = {k: v["p"] for k, v in pred["flags"].items()}
    ev = {k: v.get("evidence", []) for k, v in pred["flags"].items()}
    on = {k: fp[k] >= _t(th, f"flags.{k}") for k in fp}
    ct = pred["contentType"]
    is_inv = pred["topic"].get("INVESTMENT", 0) >= _t(th, "topic.INVESTMENT")
    is_ad = (ct.get("FIRM_OWN_MARKETING", 0) >= _t(th, "contentType.FIRM_OWN_MARKETING")
             or ct.get("THIRD_PARTY_PROMO", 0) >= _t(th, "contentType.THIRD_PARTY_PROMO"))
    # art. 44 rozp. 2017/565 dotyczy komunikacji marketingowej – dla opinii / newsów reguły „nie dotyczą”
    is_mkt = is_ad or ct.get("SERVICE_OFFER", 0) >= _t(th, "contentType.SERVICE_OFFER")
    registered = [e for e in entities if e.get("knfRegister", {}).get("status") == "REGISTERED"]
    instr_on = {k for k, p in pred["instruments"].items() if p >= 0.5}

    rules: list[dict[str, Any]] = []

    def add(rid: str, status: str, score: float = 0.0, evidence: list | None = None) -> None:
        rules.append({"ruleId": rid, "status": status, "score": round(float(score), 3), "evidence": evidence or []})

    for rid, (_, detectable) in RULES.items():
        if not is_inv or (rid in MARKETING_RULES and not is_mkt):
            add(rid, "NOT_APPLICABLE")
            continue
        if rid == "1":
            if is_ad:
                firm = any(e.get("role") == "investment_firm" for e in entities)
                add(rid, "OK" if firm else "VIOLATION", 0.0 if firm else 0.5)
            else:
                add(rid, "NOT_APPLICABLE")
        elif rid == "2":
            if is_ad:
                add(rid, "OK" if on["AD_DISCLOSURE"] else "VIOLATION", 1 - fp["AD_DISCLOSURE"], ev["AD_DISCLOSURE"])
            else:
                add(rid, "NOT_APPLICABLE")
        elif rid == "3":
            if on["PROFIT_CLAIM"]:
                viol = not on["RISK_WARNING"]
                add(rid, "VIOLATION" if viol else "OK", min(fp["PROFIT_CLAIM"], 1 - fp["RISK_WARNING"]),
                    ev["PROFIT_CLAIM"] + (ev["RISK_WARNING"] if not viol else []))
            else:
                add(rid, "NOT_APPLICABLE")
        elif rid == "11":
            add(rid, "VIOLATION" if on["PRODUCT_COMPARISON"] else "NOT_APPLICABLE", fp["PRODUCT_COMPARISON"],
                ev["PRODUCT_COMPARISON"])
        elif rid == "14":
            if on["PAST_PERFORMANCE"]:
                viol = not on["PAST_PERF_DISCLAIMER"]
                add(rid, "VIOLATION" if viol else "OK", min(fp["PAST_PERFORMANCE"], 1 - fp["PAST_PERF_DISCLAIMER"]),
                    ev["PAST_PERFORMANCE"])
            else:
                add(rid, "NOT_APPLICABLE")
        elif rid == "15":
            if on["FORECAST"]:
                viol = not on["FORECAST_DISCLAIMER"]
                add(rid, "VIOLATION" if viol else "OK", min(fp["FORECAST"], 1 - fp["FORECAST_DISCLAIMER"]), ev["FORECAST"])
            else:
                add(rid, "NOT_APPLICABLE")
        elif rid == "16":
            add(rid, "VIOLATION" if on["TAX_CLAIM"] else "NOT_APPLICABLE", fp["TAX_CLAIM"] * 0.7, ev["TAX_CLAIM"])
        elif rid in ("17", "18"):
            add(rid, "VIOLATION" if on["SUPERVISOR_AS_SAFETY"] else "NOT_APPLICABLE", fp["SUPERVISOR_AS_SAFETY"],
                ev["SUPERVISOR_AS_SAFETY"])
        elif rid == "M1":
            promo = ct.get("THIRD_PARTY_PROMO", 0) >= _t(th, "contentType.THIRD_PARTY_PROMO")
            if promo:
                viol = not on["AD_DISCLOSURE"] or (on["PROFIT_CLAIM"] and not on["RISK_WARNING"])
                add(rid, "VIOLATION" if viol else "OK", ct["THIRD_PARTY_PROMO"] * (1.0 if viol else 0.3), ev["AD_DISCLOSURE"])
            else:
                add(rid, "NOT_APPLICABLE")
        elif rid == "M3":
            adv = max(fp["PERSONALIZED_ADVICE"], fp["PAID_ADVISORY_SERVICE"])
            advisory = on["PERSONALIZED_ADVICE"] or on["PAID_ADVISORY_SERVICE"]
            instruments_ok = bool(instr_on & ADVISORY_INSTRUMENTS) or not instr_on
            if advisory and instruments_ok:
                viol = not registered
                add(rid, "VIOLATION" if viol else "OK", adv if viol else 0.1,
                    ev["PERSONALIZED_ADVICE"] + ev["PAID_ADVISORY_SERVICE"])
            else:
                add(rid, "NOT_APPLICABLE")
        elif rid == "SCAM":
            pass  # niżej
        else:
            add(rid, "NOT_CHECKED")

    scam_p = float(pred.get("scamText", 0.0))
    signals = list(extra_scam_signals or [])
    if scam_p >= _t(th, "scam"):
        signals.append("TEXT_MODEL")
    if signals and "TEXT_MODEL" not in signals:
        scam_p = max(scam_p, 0.7)  # silny sygnał spoza tekstu (lista CERT/KNF, podszywanie się)
    scam_on = is_inv and scam_p >= _t(th, "scam")
    scam_ev = [e for k in ("GUARANTEED_PROFIT", "UNREALISTIC_RETURNS", "AUTOMATED_PROFIT", "OFF_PLATFORM_CONTACT",
                           "CELEBRITY_OR_BRAND_ENDORSEMENT", "LOW_ENTRY_DEPOSIT") for e in ev.get(k, [])]
    add("SCAM", "VIOLATION" if scam_on else ("OK" if is_inv else "NOT_APPLICABLE"), scam_p, scam_ev)

    modules = []
    if ct.get("THIRD_PARTY_PROMO", 0) >= _t(th, "contentType.THIRD_PARTY_PROMO") and is_inv:
        modules.append(1)
    if ct.get("FIRM_OWN_MARKETING", 0) >= _t(th, "contentType.FIRM_OWN_MARKETING") and is_inv:
        modules.append(2)
    if any(r["ruleId"] == "M3" and r["status"] != "NOT_APPLICABLE" for r in rules):
        modules.append(3)

    viol_scores = [r["score"] for r in rules if r["status"] == "VIOLATION"]
    risk = max(viol_scores + [0.0])
    if scam_on:
        risk = max(risk, scam_p, _t(th, "risk.CRITICAL"))
    if not is_inv:
        risk = min(risk, 0.1)
    level = "LOW"
    for lvl in ("MEDIUM", "HIGH", "CRITICAL"):
        if risk >= _t(th, f"risk.{lvl}"):
            level = lvl
    return {
        "rules": rules, "modules": modules, "riskScore": round(risk, 3), "riskLevel": level,
        "scam": {"p": round(scam_p, 3), "signals": signals if scam_on else []},
    }
