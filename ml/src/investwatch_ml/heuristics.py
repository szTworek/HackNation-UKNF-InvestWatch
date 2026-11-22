"""Baseline 0: wzorce słownikowe dla flag i tematu.

Służy jako (1) model zastępczy w stubie API, zanim będzie wytrenowany klasyfikator, (2) baseline do porównań,
(3) dodatkowe cechy (np. regex na nierealne stopy zwrotu). Zwraca prawdopodobieństwa w formacie klasyfikatora.
"""

from __future__ import annotations

import re
import zlib
from typing import Any

from .labels import CONTENT_TYPES, FLAG_KEYS, INSTRUMENTS, TOPICS

_I = re.IGNORECASE

FLAG_PATTERNS: dict[str, list[str]] = {
    "PROFIT_CLAIM": [r"\bzarabia\w*", r"\bzarob\w*", r"\bzysk\w*", r"\bstop[aęy] zwrotu", r"\bzwrot\w* \d+", r"\d+\s?% (rocznie|miesięcznie|dziennie)"],
    "RISK_WARNING": [r"traci\w* pieniądze", r"ryzyk\w* (utraty|straty)", r"możesz stracić", r"możecie stracić",
                     r"wiąż\w* się z (dużym |wysokim )?ryzykiem", r"rachunków inwestorów detalicznych"],
    "AD_DISCLOSURE": [r"#reklama", r"#ad\b", r"#współpraca", r"materiał sponsorowany", r"partnerem (dzisiejszego )?odcinka",
                      r"link afiliacyjny", r"kod(em)? (polecający|rabatowy)", r"\breklama\b", r"współpraca reklamowa"],
    "PAST_PERFORMANCE": [r"zarobił\w* .{0,30}\d+[,.]?\d*\s?%", r"w (ubiegłym|zeszłym) roku .{0,40}\d+\s?%", r"stopa zwrotu za \d{4}"],
    "PAST_PERF_DISCLAIMER": [r"wyniki historyczne nie", r"przeszłe wyniki nie", r"nie gwarantują (osiągnięcia )?(podobnych|przyszłych)"],
    "FORECAST": [r"dojdzie do", r"pójdzie na \d+", r"\bprognoz\w*", r"(wzrośnie|urośnie) (do|o) \d+"],
    "FORECAST_DISCLAIMER": [r"prognoz\w* nie (jest|są) (wiarygodnym )?wskaźnik"],
    "TAX_CLAIM": [r"podat\w* belki", r"\bulg\w* podatk\w*", r"bez podatku", r"(nie )?(zapłacisz|płać|płacisz) podatk\w*", r"odlicz\w*.{0,40}(podatk|PIT)", r"(zwrot|odzysk\w*).{0,25}podatk\w*", r"zwolnien\w* z podatk\w*"],
    "PRODUCT_COMPARISON": [r"lepsz\w* niż", r"najniższ\w* prowizj\w*", r"najlepsz\w* (wynik|broker|oferta)", r"w przeciwieństwie do"],
    "SUPERVISOR_AS_SAFETY": [r"nadzor\w* (przez )?KNF.{0,60}bezpieczn", r"licencj\w* KNF", r"regulowan\w* przez KNF", r"KNF.{0,40}bezpieczn"],
    "PERSONALIZED_ADVICE": [r"dopasowan\w* do (twoich|twojej|ciebie)", r"indywidualn\w* (portfel|strategi|plan)", r"dobior\w* (ci|portfel)"],
    "PAID_ADVISORY_SERVICE": [r"konsultacj\w*", r"zarządza\w* portfel\w*", r"grup\w* (vip|premium)", r"sygnał\w*", r"mentoring\w*", r"opiekun\w* konta"],
    "SPECIFIC_INSTRUMENT_CALL": [r"\bkupuj\w*", r"\bsprzedawaj\w*", r"\bkupcie\b", r"\bwchodź\w* w\b", r"dokładam do pozycji"],
    "GUARANTEED_PROFIT": [r"gwarantowan\w* zysk", r"zysk\w* gwarantowan\w*", r"gwarancj\w* zysku", r"pewny zysk"],
    "NO_RISK_CLAIM": [r"bez ryzyka", r"zero ryzyka", r"w pełni bezpieczn\w*", r"nie (możesz|da się) stracić", r"100\s?% bezpieczn"],
    "UNREALISTIC_RETURNS": [r"\d{2,}\s?% (miesięcznie|w miesiąc|tygodniowo|dziennie)", r"\d+\s?% dziennie",
                            r"z \d[\d\s]* zł (zrobisz|masz|na) \d[\d\s]* zł", r"\d{2,3}\s?000 zł (miesięcznie|w miesiąc)"],
    "URGENCY_PRESSURE": [r"tylko dziś", r"ostatnie (\w+ )?miejsc", r"oferta wygasa", r"do północy", r"liczba miejsc ograniczona", r"nie czekaj"],
    "CELEBRITY_OR_BRAND_ENDORSEMENT": [r"zdradził\w*", r"znan\w* (prezenter|aktor|sportowiec|milioner)", r"wywiad\w* z"],
    "AUTOMATED_PROFIT": [r"sztuczn\w* inteligencj\w*.{0,40}(handluje|zarabia|inwestuje)", r"\bbot\w*", r"\bAI\b.{0,30}(zarabia|handluje)",
                         r"handluje za ciebie", r"automatyczn\w* (system|zarabian)"],
    "LOW_ENTRY_DEPOSIT": [r"(wpłat\w*|zacznij od|wystarczy) \d{2,4}\s?(usd|\$|zł|euro|eur)", r"\b250\s?(usd|\$)"],
    "OFF_PLATFORM_CONTACT": [r"zostaw (swój )?numer", r"konsultant\w* oddzwoni", r"\btelegram\w*", r"\bwhatsapp\w*", r"napisz (na )?priv", r"wiadomość prywatn"],
    "SECRECY_CONSPIRACY": [r"bank\w* (nie chc|ukrywa)", r"(rząd|politycy) nie chc", r"sekretn\w*", r"chciał\w* zablokować"],
    "FAKE_NEWS_FORMAT": [r"skandal na wizji", r"wywiad\w*,? (który|którego) usunięto", r"(tvn|polsat|tvp)\w*.{0,30}(wywiad|program)"],
}
_COMPILED = {k: [re.compile(p, _I) for p in v] for k, v in FLAG_PATTERNS.items()}

INVEST_RE = re.compile(r"inwest\w*|giełd\w*|akcj[ei]\b|akcji\b|obligacj\w*|\bETF\w*|fundusz\w*|krypto\w*|bitcoin\w*|\bBTC\b|"
                       r"forex|\bCFD\b|trading\w*|trader\w*|broker\w*|dywidend\w*|portfel\w*|\bGPW\b|\bcoin\w*|altcoin\w*|"
                       r"token\w*|sygnał\w*|zarab\w* na|platform\w* inwest\w*", _I)
FIN_OTHER_RE = re.compile(r"kredyt\w*|lokat\w*|konto oszczędn\w*|ubezpiecz\w*|hipote\w*|\bPIT\b|rat[ay] ", _I)
INSTR_RE: dict[str, re.Pattern] = {
    "CFD_FOREX": re.compile(r"\bCFD\b|forex|dźwigni\w*", _I),
    "STOCKS": re.compile(r"akcj\w*|spółk\w*|\bGPW\b", _I),
    "FUNDS_ETF": re.compile(r"\bETF\w*|fundusz\w*|\bTFI\b|\bIKE\b|\bIKZE\b", _I),
    "BONDS": re.compile(r"obligacj\w*", _I),
    "CRYPTO": re.compile(r"krypto\w*|bitcoin\w*|\bBTC\b|\bcoin\w*|token\w*|ethereum", _I),
    "OTHER_DERIVATIVES": re.compile(r"opcj[ei]\b|kontrakt\w* terminow\w*|futures", _I),
    "NON_INSTRUMENT": re.compile(r"złot[oa] fizyczn\w*|nieruchomoś\w*", _I),
}

SCAM_FLAGS = ["GUARANTEED_PROFIT", "NO_RISK_CLAIM", "UNREALISTIC_RETURNS", "URGENCY_PRESSURE", "CELEBRITY_OR_BRAND_ENDORSEMENT",
              "AUTOMATED_PROFIT", "LOW_ENTRY_DEPOSIT", "OFF_PLATFORM_CONTACT", "SECRECY_CONSPIRACY", "FAKE_NEWS_FORMAT"]


def _jitter(text: str, key: str) -> float:
    """Deterministyczny mały szum, żeby rozkłady nie były zero-jedynkowe (panel kalibracji)."""
    return (zlib.crc32(f"{key}|{text[:200]}".encode()) % 1000) / 1000 * 0.15


def predict(text: str) -> dict[str, Any]:
    flags: dict[str, dict[str, Any]] = {}
    for key in FLAG_KEYS:
        ev = []
        for pat in _COMPILED.get(key, []):
            for m in pat.finditer(text):
                ev.append({"section": "text", "start": m.start(), "end": m.end(), "text": text[m.start():m.end()]})
                if len(ev) >= 2:
                    break
            if len(ev) >= 2:
                break
        p = min(0.6 + 0.15 * len(ev) + _jitter(text, key), 0.97) if ev else _jitter(text, key)
        flags[key] = {"p": round(p, 3), "evidence": ev}

    n_inv = len(INVEST_RE.findall(text))
    n_fin = len(FIN_OTHER_RE.findall(text))
    scam_hits = sum(1 for k in SCAM_FLAGS if flags[k]["evidence"])
    p_inv = min(0.15 + 0.2 * n_inv + 0.15 * scam_hits, 0.98)
    p_fin = min(0.1 + 0.25 * n_fin, 0.9) * (1 - p_inv)
    topic = {"INVESTMENT": round(p_inv, 3), "FINANCIAL_OTHER": round(p_fin, 3)}
    topic["NON_FINANCIAL"] = round(max(1 - p_inv - p_fin, 0.0), 3)

    f = {k: v["p"] for k, v in flags.items()}
    raw = {
        "NEWS_EDU": 0.3,
        "OPINION_DISCUSSION": 0.2,
        "FIRM_OWN_MARKETING": 0.15 + 0.3 * f["RISK_WARNING"]
        + 0.5 * max(f["PAST_PERFORMANCE"], f["SUPERVISOR_AS_SAFETY"], f["PRODUCT_COMPARISON"]),
        "THIRD_PARTY_PROMO": 0.1 + 0.8 * f["AD_DISCLOSURE"],
        "RECOMMENDATION": 0.1 + 0.7 * f["SPECIFIC_INSTRUMENT_CALL"],
        "SERVICE_OFFER": 0.1 + 0.6 * max(f["PAID_ADVISORY_SERVICE"], f["PERSONALIZED_ADVICE"], f["AUTOMATED_PROFIT"]),
    }
    s = sum(raw.values())
    content_type = {k: round(v / s, 3) for k, v in raw.items()}
    content_type["NONE"] = 0.0
    assert set(content_type) == set(CONTENT_TYPES) and set(topic) == set(TOPICS)

    instruments = {k: round(0.85 if INSTR_RE[k].search(text) else _jitter(text, k) / 2, 3) for k in INSTRUMENTS}
    scam_p = min(0.05 + 0.22 * scam_hits + 0.1 * f["PROFIT_CLAIM"] * (scam_hits > 0), 0.98)
    return {"topic": topic, "contentType": content_type, "instruments": instruments, "flags": flags,
            "scamText": round(scam_p, 3)}
