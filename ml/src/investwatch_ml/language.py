"""Czy tekst reklamy jest po polsku. Odporne na krótkie tytuły i OCR bez polskich znaków.

Sam detektor języka myli się na krótkich reklamach („Otwórz Konto W Kilka Minut” → fiński), dlatego decyduje
porównanie charakterystycznych słów polskich i obcych, a detektor rozstrzyga tylko przypadki bez wyraźnych słów.
"""

from __future__ import annotations

import re

from langdetect import DetectorFactory, detect_langs

DetectorFactory.seed = 0
_POLISH = re.compile(
    r"\b(inwest\w*|pieni[aąę]d\w*|pienig\w*|do[lł][aą]cz\w*|otw[oó]rz\w*|ryzyk\w*|odpowiedzialn\w*|prowizj\w*|prowizi\w*|"
    r"rachun\w*|zyskaj\w*|zysk\w*|zarabia\w*|sprawd[zźž]\w*|oszcz[eę]d\w*|gie[lł]d\w*|firmow\w*|p[lł]atn\w*|p[lł]a[cć]\w*|"
    r"kart[ay]|polsk\w*|emerytur\w*|podatk\w*|notowani\w*|maklersk\w*|ubezpiecz\w*|kredyt\w*|bilet\w*|zacznij|pobierz|"
    r"odbierz|za[lł][oó][zżž]\w*|kup\w+|si[eę]|jest|oraz|dla|przez|mo[zż]esz|twoj\w*|swoim|nawet|ju[zż]|bez|czy|kt[oó]r\w*)\b",
    re.I)
_FOREIGN = re.compile(
    r"\b(the|your|you|with|and|for|from|this|that|are|our|get|start|trade|trading|invest|stocks?|shares|account|free|now|"
    r"und|mit|der|die|das|dein|ihr|f[uü]r|er[oö]ffnen|kostenlos\w*|konten?|jetzt|aktien|"
    r"le|la|les|votre|vous|avec|des|et|pour|une|tout|"
    r"di|il|per|con|su|tutto|migliori|cambio|"
    r"para|los|las|tu|desde|invierte|nuestro|com|comece|bolsa|valores|"
    r"[eé]s|sz[aá]ml[aá]\w*|nyiss|fektess|jutal[eé]k\w*|"
    r"a[zž]|voln[yý]ch|z[ií]skej|pro|tvoje|prost[rř]edk\w*|pove[cć]ajte|uz)\b", re.I)
_POLISH_LETTERS = re.compile(r"[ąćęłńśźż]", re.I)


def is_polish(text: str) -> bool:
    text = text or ""
    if re.search(r"[čřěůđ]", text, re.I) and len({m.group(0).lower() for m in _POLISH.finditer(text)}) < 4:
        return False  # litery czeskie i chorwackie; polski OCR ich praktycznie nie produkuje
    pl = {m.group(0).lower() for m in _POLISH.finditer(text)}
    foreign = {m.group(0).lower() for m in _FOREIGN.finditer(text)}
    letters = len(_POLISH_LETTERS.findall(text))
    if len(pl) >= 2 and len(pl) + min(letters, 3) > len(foreign):
        return True
    if len(foreign) >= 2 and len(foreign) >= len(pl):
        return False
    try:
        langs = detect_langs(text[:2000])
    except Exception:
        return False
    return next((x.prob for x in langs if x.lang == "pl"), 0.0) >= 0.7
