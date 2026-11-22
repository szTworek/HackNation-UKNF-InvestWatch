"""Słowa kluczowe ze stemmingiem: deterministyczne sygnały dla modułów 1–3 (wejście dla LLM i reguły twarde).

Stemmer jest lekki: małe litery, bez polskich znaków (OCR często je gubi), obcięcie typowych końcówek fleksyjnych.
Leksykon to tematy (prefiksy) dopasowywane do tematów słów, więc „zarabiaj”, „zarobek”, „zarabianie” trafiają
w ten sam sygnał. Każde trafienie zwraca dosłowne słowo z tekstu jako dowód.
"""

from __future__ import annotations

import re
import unicodedata

_FOLD = str.maketrans("ąćęłńóśźż", "acelnoszz")
_SUFFIXES = sorted("""
ościami ościach owaniem owania owanie ującego ujących ujemy ujecie ujesz ujący owych owymi owego owej
ami ach ach ego emu ymi imi ich ych ej ów om ie ia ią ię iu ał ała ało ali ały aj ają ać eć ić yć
a e i o u y ą ę
""".split(), key=len, reverse=True)
_TOKEN = re.compile(r"[a-ząćęłńóśźż0-9$€%]+", re.I)


def fold(text: str) -> str:
    text = unicodedata.normalize("NFC", text.lower()).translate(_FOLD)
    return text


def stem(word: str) -> str:
    w = fold(word)
    if len(w) <= 4:
        return w
    for suf in _SUFFIXES:
        if w.endswith(fold(suf)) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


# grupa -> tematy (prefiksy po stemmingu i usunięciu polskich znaków); frazy wielowyrazowe jako regex
LEXICON: dict[str, list[str]] = {
    "risk_warning": ["ryzyk", "strat", "traci", "trac", "utrat", "kapital", "dzwigni", "odpowiedzialn"],
    "ad_disclosure": ["reklam", "wspolprac", "sponsor", "partner", "afiliac", "#ad", "#wspolpraca", "materialsponsor"],
    "profit_claim": ["zarab", "zarob", "zysk", "dochod", "odsetk", "procent", "%", "pracowac", "pomnoz", "zwrot", "dywidend"],
    # wabik pieniężny; samo „darmowy kurs/webinar/e-book” to nie wabik (frazy niżej łapią „darmowe akcje”)
    "lure": ["bonus", "gwarant", "pasywn", "100$", "100€", "400zl"],
    "pressure": ["ograniczon", "ostatni", "tylko", "zanim", "spiesz", "wygasa", "koniec"],
    "private_channel": ["telegram", "whatsapp", "discord", "t.me", "wa.me", "spolecznosc"],
    "service": ["sygnal", "typ", "kopiuj", "mentor", "konsultac", "doradz", "doradc", "zarzadz", "portfel", "strategi",
                "challenge", "challang", "szkoleni", "webinar", "akademi", "kurs", "analiz"],
    "tax": ["podatk", "podatek", "belk", "zwolnieni", "pit"],
    "ranking": ["najlepsz", "ranking", "top", "lepsz", "porown", "najnizsz"],
    "referral": ["kod", "link", "polecaj", "referenc", "rejestrac", "zarejestruj"],
    "non_instrument": ["flip", "apartament", "nieruchomos", "zlot", "krypto", "bitcoin", "token"],
}
PHRASES: dict[str, list[str]] = {
    "profit_claim": [r"pieniadz\w* (moga )?pracowa", r"pozwol swoim pieniadzom"],
    "lure": [r"(akcj\w*|\d+ ?(zl|\$|€|eur\w*)) za darmo", r"za darmo\W+\w* ?(akcj|\d)", r"darmow\w* (akcj|\d+ ?(\$|€|zl))",
             r"latw\w* (zarob|zysk|pieniadz)", r"bez ryzyka", r"szybk\w* (zarob|zysk)", r"zarob\w* \d+", r"pasywn\w* dochod"],
    "private_channel": [r"napisz (na priv|do nas|wiadomosc)", r"grup\w* (vip|premium|zamknie\w*|inwestycyjn)", r"zostaw (numer|telefon)", r"send message"],
    "pressure": [r"tylko dzis", r"ograniczony czas", r"ostatnie miejsca", r"juz teraz"],
}


def analyze(text: str) -> dict[str, list[str]]:
    """grupa -> lista dosłownych słów/fraz z tekstu (najwyżej 5 na grupę)."""
    hits: dict[str, list[str]] = {}
    for m in _TOKEN.finditer(text or ""):
        word = m.group(0)
        s = stem(word)
        f = fold(word)
        for group, stems in LEXICON.items():
            if any(s.startswith(p) or f.startswith(p) for p in stems):
                lst = hits.setdefault(group, [])
                if word.lower() not in (x.lower() for x in lst) and len(lst) < 5:
                    lst.append(word)
    folded = fold(text or "")
    for group, patterns in PHRASES.items():
        for p in patterns:
            m = re.search(p, folded)
            if m:
                lst = hits.setdefault(group, [])
                if len(lst) < 5 and m.group(0) not in lst:
                    lst.append(m.group(0))
    return hits
