"""Agregator: z prawdopodobieństw modelu + progów liczy reguły UKNF, moduły, scam i poziom ryzyka.

Czyste funkcje bez modelu – używane przez /analyze i /rescore (zmiana progów w panelu kalibracji
przelicza wyniki bez ponownej inferencji). Logika jest jawna i edytowalna.
"""

from __future__ import annotations

import re
from typing import Any

from .labels import FLAG_KEYS

DEFAULT_THRESHOLDS: dict[str, float] = {
    **{f"flags.{k}": 0.5 for k in FLAG_KEYS},
    "topic.INVESTMENT": 0.5,
    "contentType.FIRM_OWN_MARKETING": 0.35,
    "contentType.THIRD_PARTY_PROMO": 0.35,
    "contentType.SERVICE_OFFER": 0.35,
    "contentType.RECOMMENDATION": 0.35,
    "scam.p": 0.6,
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
    "M1_PROMO": ("Moduł 1: reklama firmy przez podmiot trzeci", True),
    "M3_ADVISORY": ("Moduł 3: możliwe doradztwo bez zezwolenia", True),
    "M3_RECOMMENDATION": ("Moduł 3: rekomendacja instrumentu do weryfikacji", True),
}

MARKETING_RULES = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12a", "12b", "13", "14", "15", "16", "17", "18"}
ADVISORY_INSTRUMENTS = {"CFD_FOREX", "STOCKS", "FUNDS_ETF", "BONDS", "OTHER_DERIVATIVES"}


_TAX_INDIVIDUAL = re.compile(r"indywidualn\w* sytuacj|sytuacj\w* (indywidualn|klienta|podatnika)", re.IGNORECASE)
_TAX_CHANGE = re.compile(r"(może|mogą|moze|moga) (ulec|podlegać|podlegac) zmian|(może|mogą) się zmieni", re.IGNORECASE)


def has_tax_disclaimer(text: str) -> bool:
    """Reguła 16 wymaga obu informacji: zależność od sytuacji klienta i możliwość zmian."""
    return bool(_TAX_INDIVIDUAL.search(text) and _TAX_CHANGE.search(text))


def normalize_thresholds(values: dict[str, float] | None) -> dict[str, float]:
    """Klucz progu oszustwa w kontrakcie to `scam.p`; starszy `scam` jest przyjmowany na wejściu."""
    out = dict(values or {})
    if "scam" in out:
        legacy = out.pop("scam")
        out.setdefault("scam.p", legacy)
    return out


def _t(th: dict[str, float], key: str) -> float:
    return th.get(key, DEFAULT_THRESHOLDS.get(key, 0.5))


def compute(pred: dict[str, Any], entities: list[dict[str, Any]], thresholds: dict[str, float] | None = None,
            extra_scam_signals: list[str] | None = None, is_paid_ad: bool = False,
            is_polish: bool = True, tax_disclaimer: bool = False) -> dict[str, Any]:
    th = {**DEFAULT_THRESHOLDS, **normalize_thresholds(thresholds)}
    fp = {k: v["p"] for k, v in pred["flags"].items()}
    ev = {k: v.get("evidence", []) for k, v in pred["flags"].items()}
    on = {k: fp[k] >= _t(th, f"flags.{k}") for k in fp}
    ct = pred["contentType"]
    registered = [e for e in entities if e.get("knfRegister", {}).get("status") == "REGISTERED"]
    related = [e for e in entities if e.get("knfRegister", {}).get("relatedEntity")]
    publishers = [e for e in entities if e.get("publisher")]
    publisher_registered = any(e in registered for e in publishers)
    publisher_related = any(e in related for e in publishers)  # inna spółka tej samej marki: wymaga weryfikacji
    firm_known = bool(registered or related)
    # płatna reklama samej firmy z rejestru to M2, także gdy tekst (np. OCR) jest za słaby dla klasyfikatora
    topic_inv = pred["topic"].get("INVESTMENT", 0) >= _t(th, "topic.INVESTMENT")
    # bank reklamuje też konta i ubezpieczenia, więc u banku o M2 decyduje treść
    publisher_is_bank = any("BANK" in e.get("knfRegister", {}).get("lists", []) for e in publishers)
    own_ad = (is_paid_ad and is_polish and (publisher_registered or publisher_related)
              and (topic_inv or not publisher_is_bank))
    is_inv = own_ad or topic_inv
    own_marketing = own_ad or (ct.get("FIRM_OWN_MARKETING", 0) >= _t(th, "contentType.FIRM_OWN_MARKETING")
                               and (publisher_registered or publisher_related or (not publishers and firm_known)))
    third_party = (not publisher_registered and not publisher_related and firm_known
                   and (is_paid_ad or ct.get("THIRD_PARTY_PROMO", 0) >= _t(th, "contentType.THIRD_PARTY_PROMO")))
    is_ad = (own_marketing or third_party or ct.get("FIRM_OWN_MARKETING", 0) >= _t(th, "contentType.FIRM_OWN_MARKETING")
             or ct.get("THIRD_PARTY_PROMO", 0) >= _t(th, "contentType.THIRD_PARTY_PROMO"))
    # art. 44 rozp. 2017/565 dotyczy komunikacji marketingowej – dla opinii / newsów reguły „nie dotyczą”
    is_mkt = is_ad or ct.get("SERVICE_OFFER", 0) >= _t(th, "contentType.SERVICE_OFFER")
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
            if is_ad and is_paid_ad and not on["AD_DISCLOSURE"]:
                # płatną reklamę oznacza platforma poza treścią kreacji, której scraper nie widzi
                add(rid, "NOT_CHECKED")
            elif is_ad:
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
            if on["TAX_CLAIM"]:
                add(rid, "OK" if tax_disclaimer else "VIOLATION", 0.0 if tax_disclaimer else fp["TAX_CLAIM"] * 0.7, ev["TAX_CLAIM"])
            else:
                add(rid, "NOT_APPLICABLE")
        elif rid in ("17", "18"):
            add(rid, "VIOLATION" if on["SUPERVISOR_AS_SAFETY"] else "NOT_APPLICABLE", fp["SUPERVISOR_AS_SAFETY"],
                ev["SUPERVISOR_AS_SAFETY"])
        elif rid == "M1_PROMO":
            if third_party:
                viol = not (on["AD_DISCLOSURE"] or is_paid_ad) or (on["PROFIT_CLAIM"] and not on["RISK_WARNING"])
                strength = max(ct.get("THIRD_PARTY_PROMO", 0), 0.7 if is_paid_ad else 0)
                add(rid, "VIOLATION" if viol else "OK", strength * (1.0 if viol else 0.3), ev["AD_DISCLOSURE"])
            else:
                add(rid, "NOT_APPLICABLE")
        elif rid == "M3_ADVISORY":
            adv = max(fp["PERSONALIZED_ADVICE"], fp["PAID_ADVISORY_SERVICE"])
            advisory = on["PERSONALIZED_ADVICE"] or on["PAID_ADVISORY_SERVICE"]
            instruments_ok = bool(instr_on & ADVISORY_INSTRUMENTS) or not instr_on
            if advisory and instruments_ok:
                evidence = ev["PERSONALIZED_ADVICE"] + ev["PAID_ADVISORY_SERVICE"]
                # liczy się status oferenta: wzmianka o XTB w poście doradcy nie czyni go firmą z rejestru
                if publisher_registered or (not publishers and registered):
                    add(rid, "OK", 0.1, evidence)
                elif publisher_related or not publishers:
                    add(rid, "NOT_CHECKED", adv, evidence)
                else:
                    add(rid, "VIOLATION", adv, evidence)
            else:
                add(rid, "NOT_APPLICABLE")
        elif rid == "M3_RECOMMENDATION":
            # rekomendacja dla ogółu to nie porada dopasowana do klienta, więc status to „do weryfikacji”, nie naruszenie
            rec_p, call_p = ct.get("RECOMMENDATION", 0), fp["SPECIFIC_INSTRUMENT_CALL"]
            top_type = max(ct, key=ct.get) if ct else ""
            private = top_type in ("OPINION_DISCUSSION", "NEWS_EDU")  # własna relacja, opinia lub edukacja
            triggered = rec_p >= _t(th, "contentType.RECOMMENDATION") or on["SPECIFIC_INSTRUMENT_CALL"]
            instruments_ok = bool(instr_on & ADVISORY_INSTRUMENTS) or not instr_on
            if triggered and not private and instruments_ok:
                strength = max(rec_p, call_p)
                evidence = ev["SPECIFIC_INSTRUMENT_CALL"]
                if publisher_registered or (not publishers and registered):
                    add(rid, "OK", 0.1, evidence)
                else:
                    add(rid, "NOT_CHECKED", strength, evidence)
            else:
                add(rid, "NOT_APPLICABLE")
        else:
            add(rid, "NOT_CHECKED")

    scam_p = float(pred.get("scamText", 0.0))
    signals = list(extra_scam_signals or [])
    if scam_p >= _t(th, "scam.p"):
        signals.append("TEXT_MODEL")
    if signals and "TEXT_MODEL" not in signals:
        scam_p = max(scam_p, 0.7)  # silny sygnał spoza tekstu (lista CERT/KNF, podszywanie się)
    scam_on = is_inv and scam_p >= _t(th, "scam.p")

    # Moduły wg zadania: M1/M2 dotyczą firm z rejestru, M3 podmiotów spoza niego; scam ma własną ścieżkę.
    modules = []
    if is_inv and is_polish and not scam_on:
        if third_party:
            modules.append(1)
        if own_marketing:
            modules.append(2)
        if any((r["ruleId"] == "M3_ADVISORY" and r["status"] == "VIOLATION")
               or (r["ruleId"] == "M3_RECOMMENDATION" and r["status"] == "NOT_CHECKED") for r in rules):
            modules.append(3)

    viol_scores = [r["score"] for r in rules if r["status"] == "VIOLATION"]
    risk = max(viol_scores + [0.0])
    review = [r["score"] for r in rules if r["ruleId"] == "M3_RECOMMENDATION" and r["status"] == "NOT_CHECKED"]
    if review:  # samo „do weryfikacji” nie podnosi rekordu powyżej poziomu średniego
        risk = max(risk, min(review[0], min(0.6, _t(th, "risk.HIGH") - 0.01)))
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
