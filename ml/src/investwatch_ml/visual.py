"""Reguły wizualne 4–8 z pomiarów kolektora stron (source_meta.risk_by_viewport, decyzja D3).

Kolektor mierzy ostrzeżenie o ryzyku na szerokościach 1440/768/375 px: czcionkę, kontrast, położenie, przesłonięcie,
ucięcie. Tu zamieniamy pomiary na werdykty. Bez pomiarów reguły zostają NOT_CHECKED (np. posty i reklamy tekstowe).
Werdykt to wskazówka do weryfikacji na zrzucie ekranu, nie stwierdzenie naruszenia.
"""

from __future__ import annotations

from typing import Any

# art. 44 ust. 2 lit. c rozp. 2017/565: czcionka ostrzeżenia co najmniej równa przeważającej czcionce materiału
MIN_FONT_RATIO = 1.0  # strony: rozmiar z CSS jest dokładny
MIN_IMAGE_FONT_RATIO = 0.85  # grafiki: wysokość ramki OCR ma błąd pomiaru, stąd tolerancja
MIN_FONT_PX_MOBILE = 12
MIN_CONTRAST = 4.5  # WCAG AA dla zwykłego tekstu


def _ev(text: str) -> list[dict[str, Any]]:
    return [{"section": "landing", "start": 0, "end": 0, "text": text}]


def evaluate(risk_by_viewport: dict[str, Any] | None) -> dict[str, tuple[str, float, list]]:
    """ruleId -> (status, score 0..1, evidence). Pusty słownik, gdy brak pomiarów."""
    if not isinstance(risk_by_viewport, dict) or not risk_by_viewport:
        return {}
    views = sorted((v for v in risk_by_viewport.values() if isinstance(v, dict)), key=lambda v: -int(v.get("viewport") or 0))
    if not views:
        return {}
    out: dict[str, tuple[str, float, list]] = {}
    found = [(v, v.get("disclaimer")) for v in views if v.get("disclaimer")]
    profit = any((v.get("profit_blocks") or 0) > 0 for v in views)

    if not found:
        status = "VIOLATION" if profit else "NOT_APPLICABLE"
        for rid in ("4", "5", "6", "8"):
            out[rid] = ("NOT_CHECKED" if profit else "NOT_APPLICABLE", 0.0, [])
        out["7"] = (status, 0.8 if profit else 0.0, _ev("Na stronie są treści o zyskach, ale nie znaleziono ostrzeżenia o ryzyku.") if profit else [])
        return out

    # 4: rozmiar czcionki względem przeważającej czcionki strony
    v, d = min(found, key=lambda x: x[1].get("font_ratio") or 1.0)
    ratio = float(d.get("font_ratio") or 1.0)
    if ratio < MIN_FONT_RATIO:
        out["4"] = ("VIOLATION", round(min(1.0, (MIN_FONT_RATIO - ratio) + 0.5), 3),
                    _ev(f"Ostrzeżenie ma {d.get('font_px')} px przy przeważających {v.get('dominant_font_px')} px "
                        f"({ratio:.0%}) na szerokości {v.get('viewport')} px."))
    else:
        out["4"] = ("OK", 0.0, _ev(f"Najmniejsza relacja czcionki ostrzeżenia do przeważającej: {ratio:.0%}."))

    # 5: kontrast (pomiar z pikseli zrzutu; kontrast z CSS bywa błędny przy przezroczystym tle)
    v, d = min(found, key=lambda x: x[1].get("contrast_px") or x[1].get("contrast") or 21)
    contrast = float(d.get("contrast_px") or d.get("contrast") or 21)
    if d.get("bg_image"):
        out["5"] = ("NOT_CHECKED", 0.0, _ev("Ostrzeżenie leży na grafice, kontrast trzeba ocenić na zrzucie."))
    elif contrast < MIN_CONTRAST:
        out["5"] = ("VIOLATION", round(min(1.0, (MIN_CONTRAST - contrast) / MIN_CONTRAST + 0.4), 3),
                    _ev(f"Kontrast ostrzeżenia {contrast:.1f}:1, poniżej {MIN_CONTRAST}:1, na szerokości {v.get('viewport')} px."))
    else:
        out["5"] = ("OK", 0.0, _ev(f"Najniższy kontrast ostrzeżenia {contrast:.1f}:1."))

    # 6: ukrycie (stopka, poniżej treści o zyskach, poza pierwszym ekranem)
    hidden = []
    for v, d in found:
        below_profit = v.get("first_profit_y") is not None and (d.get("y") or 0) > v["first_profit_y"]
        if d.get("in_footer"):
            hidden.append(f"w stopce ({v.get('viewport')} px)")
        elif below_profit and not d.get("above_fold") and not d.get("fixed"):
            hidden.append(f"dopiero pod treściami o zyskach ({v.get('viewport')} px)")
    occluded = [str(v.get("viewport")) for v, d in found if d.get("occluded") and not d.get("above_fold")]
    if hidden:
        out["6"] = ("VIOLATION", 0.7, _ev("Ostrzeżenie jest " + ", ".join(hidden) + "."))
    elif occluded:
        out["6"] = ("NOT_CHECKED", 0.3, _ev("Możliwe przesłonięcie ostrzeżenia przez inny element (" + ", ".join(occluded)
                                           + " px); sprawdź zrzut ekranu."))
    else:
        out["6"] = ("OK", 0.0, _ev("Ostrzeżenie widoczne na pierwszym ekranie lub przypięte do ekranu."))

    # 7: dostępność bez rozwijania (ucięty tekst, ostrzeżenie widoczne tylko na części szerokości)
    missing = [str(v.get("viewport")) for v in views if not v.get("disclaimer")]
    truncated = [str(v.get("viewport")) for v, d in found if d.get("truncated")]
    if truncated or (missing and profit):
        parts = ([f"ucięte na {', '.join(truncated)} px"] if truncated else []) + ([f"brak na {', '.join(missing)} px"] if missing else [])
        out["7"] = ("VIOLATION", 0.6, _ev("Ostrzeżenie wymaga rozwinięcia lub nie jest widoczne: " + "; ".join(parts) + "."))
    else:
        out["7"] = ("OK", 0.0, [])

    # 8: responsywność
    problems = []
    for v, d in found:
        vp = int(v.get("viewport") or 0)
        if v.get("horizontal_overflow") or d.get("offscreen_x"):
            problems.append(f"tekst wychodzi poza ekran ({vp} px)")
        if vp <= 400 and (d.get("font_px") or 99) < MIN_FONT_PX_MOBILE:
            problems.append(f"czcionka {d.get('font_px')} px na telefonie")
    if problems:
        out["8"] = ("VIOLATION", 0.5, _ev("; ".join(dict.fromkeys(problems)) + "."))
    else:
        out["8"] = ("OK", 0.0, [])
    return out


import re as _re
from statistics import median as _median

RISK_LINE = _re.compile(r"ryzyk|strat|traci|kapita|dźwigni|dzwigni|cfd|odpowiedzialn|wyniki historyczne|nie gwarant", _re.I)
ENGLISH_RISK = _re.compile(r"\b(risk|lose|losing|capital at|invest responsibly|past performance)\b", _re.I)
MIN_IMAGE_RISK_PX = 9  # poniżej ok. 9 px wysokości liter tekst na grafice jest praktycznie nieczytelny


def evaluate_image(layout: dict | None) -> dict[str, tuple[str, float, list]]:
    """Reguły 4, 5, 6 i 10 dla grafiki. 7 i 8 nie dotyczą statycznej grafiki."""
    if not isinstance(layout, dict) or not layout.get("lines"):
        return {}
    lines = [ln for ln in layout["lines"] if ln.get("h") and (ln.get("conf") or 0) >= 0.5]
    img_h = (layout.get("image") or {}).get("h") or max(ln["y"] + ln["h"] for ln in lines)
    risk = [ln for ln in lines if RISK_LINE.search(ln["text"])]
    other = [ln for ln in lines if ln not in risk]
    out: dict[str, tuple[str, float, list]] = {"7": ("NOT_APPLICABLE", 0.0, []), "8": ("NOT_APPLICABLE", 0.0, [])}
    if not risk:
        for rid in ("4", "5", "6"):
            out[rid] = ("NOT_CHECKED", 0.0, _ev("Na grafice nie wykryto ostrzeżenia o ryzyku (sprawdź regułę 3)."))
        return out
    if not other:
        return {}
    risk_h = _median([ln["h"] for ln in risk])
    body_h = _median([ln["h"] for ln in other])
    head_h = max(ln["h"] for ln in other)
    ratio = risk_h / body_h if body_h else 1.0
    sample = risk[0]["text"][:80]
    if ratio < MIN_IMAGE_FONT_RATIO or risk_h < MIN_IMAGE_RISK_PX:
        out["4"] = ("VIOLATION", round(min(1.0, (1 - ratio) + 0.3), 3),
                    _ev(f"Ostrzeżenie („{sample}”) ma ok. {risk_h:.0f} px wysokości przy {body_h:.0f} px typowego tekstu "
                        f"({ratio:.0%}) i {head_h:.0f} px nagłówka."))
    else:
        out["4"] = ("OK", 0.0, _ev(f"Ostrzeżenie ok. {risk_h:.0f} px przy {body_h:.0f} px typowego tekstu ({ratio:.0%})."))
    worst = min(risk, key=lambda ln: ln.get("contrast") or 21)
    c = worst.get("contrast") or 21
    if c < MIN_CONTRAST:
        out["5"] = ("VIOLATION", round(min(1.0, (MIN_CONTRAST - c) / MIN_CONTRAST + 0.4), 3),
                    _ev(f"Kontrast ostrzeżenia ok. {c:.1f}:1 (pomiar z pikseli, przybliżony): „{worst['text'][:60]}”."))
    else:
        out["5"] = ("OK", 0.0, _ev(f"Najniższy kontrast ostrzeżenia ok. {c:.1f}:1."))
    bottom = all(ln["y"] > 0.85 * img_h for ln in risk)
    if bottom and ratio < 0.7:
        out["6"] = ("VIOLATION", 0.6, _ev("Ostrzeżenie jest drobnym tekstem przy samej krawędzi grafiki."))
    else:
        out["6"] = ("OK", 0.0, [])
    if all(ENGLISH_RISK.search(ln["text"]) for ln in risk):
        out["10"] = ("VIOLATION", 0.6, _ev(f"Ostrzeżenie po angielsku: „{sample}”."))
    return out


def evaluate_any(data: dict | None) -> dict[str, tuple[str, float, list]]:
    """Pomiary strony (risk_by_viewport) albo grafiki (ocr_layout z kluczem "lines")."""
    if isinstance(data, dict) and "lines" in data:
        return evaluate_image(data)
    return evaluate(data)
