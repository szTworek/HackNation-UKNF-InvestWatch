"""Klasyfikacja LLM w modułach 1–3 wewnątrz ai-service. Silnik wybiera zmienna środowiskowa:

  LLM_BACKEND=none    (domyślnie) tylko klasyfikator i reguły
  LLM_BACKEND=groq    Groq API (GROQ_API_KEY, LLM_MODEL domyślnie openai/gpt-oss-120b)
  LLM_BACKEND=ollama  lokalna Ollama (OLLAMA_URL, LLM_MODEL domyślnie Bielik 11B)

Prompt: classifier_prompt.md (ten sam, którego używa ml/scripts/classify_groq.py).
Wynik LLM nadpisuje moduł i poziom ryzyka; przy błędzie LLM zostaje wynik klasyfikatora z adnotacją.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

from . import keywords, knf

PROMPT = (Path(__file__).parent / "classifier_prompt.md").read_text(encoding="utf-8")
PROMPT_VERSION = hashlib.sha1(PROMPT.encode()).hexdigest()[:8]
BACKEND = os.environ.get("LLM_BACKEND", "none").lower()
DEFAULT_MODELS = {"groq": "openai/gpt-oss-120b", "ollama": "SpeakLeash/bielik-11b-v3.1-instruct:Q4_K_M"}
MODEL = os.environ.get("LLM_MODEL") or DEFAULT_MODELS.get(BACKEND, "")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434").rstrip("/")
BATCH = int(os.environ.get("LLM_BATCH", "6" if BACKEND == "groq" else "2"))
MAX_CHARS = int(os.environ.get("LLM_MAX_CHARS", "1500"))
MODULES = ("M1", "M2", "M3", "NONE")
VISUAL = {"4", "5", "6", "7", "8"}
_CACHE: dict[str, dict] = {}
_groq_key = 0  # indeks aktywnego klucza Groq


def enabled() -> bool:
    return BACKEND in ("groq", "ollama")


def info() -> dict[str, Any]:
    return {"backend": BACKEND, "model": MODEL if enabled() else None, "prompt": PROMPT_VERSION}


def publisher_status(who: str | None) -> str:
    if not who:
        return "UNKNOWN"
    reg = knf.register()
    hit = reg.lookup(who)
    if hit["status"] == "REGISTERED":
        return "REGISTERED"
    brand = (knf.tokens(who) or [""])[0]
    same = hit.get("relatedEntity") or next(
        (e["name"] for e in reg.entities if len(brand) >= 3 and (knf.tokens(e["name"]) or [""])[0] == brand), None)
    return f"SAME_BRAND:{same}" if same else hit["status"]


def build_input(item_id: str, text: str, author: str | None, sponsor: str | None, source: str | None,
                content_type: str | None, url: str | None) -> dict[str, Any]:
    reg = knf.register()
    return {"id": item_id, "source": source, "author": author, "sponsor": sponsor,
            "author_knf": publisher_status(sponsor or author), "mentioned_firms": sorted({e["name"] for e in reg.mentions(text)})[:5],
            "keywords": keywords.analyze(text), "content_type": content_type, "url": url, "text": text[:MAX_CHARS]}


def parse(text: str, key: str = "scores") -> list[dict]:
    """Tablica JSON albo kolejne obiekty (lokalne modele często pomijają tablicę)."""
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
    except json.JSONDecodeError:
        pass
    dec, out, i = json.JSONDecoder(), [], 0
    while (j := text.find("{", i)) >= 0:
        try:
            obj, end = dec.raw_decode(text, j)
        except json.JSONDecodeError:
            i = j + 1
            continue
        if isinstance(obj, dict) and key in obj:
            out.append(obj)
        i = end
    return out


def normalize(res: dict) -> dict | None:
    """Rozkład nad M1/M2/M3/NONE (suma 1), moduł = najwyższa wartość, pewność = jego udział."""
    s = res.get("scores")
    if not isinstance(s, dict) or not all(isinstance(s.get(k), (int, float)) for k in ("M1", "M2", "M3")):
        return None
    s.setdefault("NONE", max(0.0, 1 - s["M1"] - s["M2"] - s["M3"]))
    total = sum(max(float(s[k]), 0.0) for k in MODULES) or 1.0
    res["scores"] = {k: round(max(float(s[k]), 0.0) / total, 3) for k in MODULES}
    res["module"] = max(MODULES, key=res["scores"].get)
    res["confidence"] = res["scores"][res["module"]]
    return res


def enforce(res: dict, is_paid_ad: bool = False) -> dict:
    """Spójność: M1 i M2 oznaczają materiał Z PROBLEMEM, więc bez naruszenia reguły rekord trafia do NONE.

    Płatną reklamę z biblioteki oznacza platforma poza kreacją, więc brak oznaczenia w tekście nie jest naruszeniem.
    """
    res = {**res, "rules": [dict(r) for r in res.get("rules") or []]}
    if is_paid_ad:
        for r in res["rules"]:
            if str(r.get("id")) == "2" and r.get("status") == "VIOLATION":
                r["status"] = "NOT_CHECKED"
    module = res.get("module")
    if module in ("M1", "M2") and not any(r.get("status") == "VIOLATION" for r in res["rules"]):
        scores = dict(res["scores"])
        scores["NONE"] = round(scores.get("NONE", 0.0) + scores.get(module, 0.0), 3)
        scores[module] = 0.0
        res.update({"scores": scores, "module": "NONE", "confidence": scores["NONE"], "risk_level": "LOW",
                    "consistency": f"{module} -> NONE: model nie wskazał naruszonej reguły"})
    return res


_DISCLOSURE = re.compile(r"#?reklama|#ad\b|materia[lł]\w* sponsorowan|wsp[oó][lł]prac|partnerem|link\w* afiliac", re.I)


def ad_disclosure(rules: list[dict], is_paid_ad: bool, text: str) -> str:
    """DISCLOSED: oznaczona w treści; PLATFORM: płatna reklama, oznacza platforma; MISSING: brak; UNKNOWN: nie ustalono."""
    status = next((r.get("status") for r in rules if str(r.get("id", r.get("ruleId"))) == "2"), None)
    if status == "VIOLATION":
        return "MISSING"
    if status == "OK" or _DISCLOSURE.search(text or ""):
        return "DISCLOSED"
    return "PLATFORM" if is_paid_ad else "UNKNOWN"


def _call(items: list[dict], prompt: str = PROMPT, key: str = "scores") -> list[dict]:
    user = "Oceń rekordy:\n" + json.dumps(items, ensure_ascii=False)
    if BACKEND == "ollama":
        body = {"model": MODEL, "stream": False, "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": user}],
                "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": 700 * len(items) + 300}}
        r = httpx.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=900)
        r.raise_for_status()
        return parse(r.json()["message"]["content"], key)
    body = {"model": MODEL, "temperature": 0.1, "max_tokens": 900 * len(items) + 400,
            "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": user}]}
    if MODEL.startswith("openai/gpt-oss"):
        body["reasoning_effort"] = "low"
    global _groq_key
    keys = [k for k in (os.environ.get("GROQ_API_KEY"), os.environ.get("GROQ_API_KEY_2")) if k]
    for attempt in range(5 + len(keys)):
        key = keys[min(_groq_key, len(keys) - 1)] if keys else ""
        r = httpx.post("https://api.groq.com/openai/v1/chat/completions", json=body,
                       headers={"Authorization": f"Bearer {key}"}, timeout=180)
        if r.status_code == 429 and "per day" in r.text and _groq_key + 1 < len(keys):
            _groq_key += 1  # dzienny limit klucza: przejście na kolejny
            continue
        if r.status_code == 429 and "per day" not in r.text:
            time.sleep(min(float(r.headers.get("retry-after") or 15 * (attempt + 1)), 60))
            continue
        r.raise_for_status()
        return parse(r.json()["choices"][0]["message"]["content"], key)
    raise RuntimeError("Groq: limit zapytań")


def classify(inputs: list[dict]) -> dict[str, dict]:
    """id -> znormalizowany wynik albo {"error": ...}. Cache po treści i wersji promptu."""
    out: dict[str, dict] = {}
    todo = []
    for it in inputs:
        key = hashlib.sha1(f"{PROMPT_VERSION}|{MODEL}|{it['author']}|{it['text']}".encode()).hexdigest()
        if key in _CACHE:
            out[it["id"]] = _CACHE[key]
        else:
            todo.append((key, it))
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        try:
            got = {str(x.get("id")): x for x in _call([it for _, it in chunk])}
        except Exception as e:  # noqa: BLE001 - pojedyncza awaria LLM nie może zatrzymać analizy
            got = {}
            err = f"{type(e).__name__}: {str(e)[:120]}"
        else:
            err = "brak wyniku dla rekordu"
        for key, it in chunk:
            res = normalize(got[it["id"]]) if it["id"] in got else None
            if res is None and len(chunk) > 1:  # ponowienie pojedynczo
                try:
                    single = _call([it])
                    res = normalize(single[0]) if single else None
                except Exception as e:  # noqa: BLE001
                    err = f"{type(e).__name__}: {str(e)[:120]}"
            if res is not None:
                _CACHE[key] = res
                out[it["id"]] = res
            else:
                out[it["id"]] = {"error": err}
    return out


def _evidence(text: str, quote: str) -> list[dict]:
    q = (quote or "").strip()
    start = text.find(q) if q else -1
    if q and start < 0:
        start = text.lower().find(q.lower())
    return [{"section": "text", "start": start, "end": start + len(q), "text": text[start:start + len(q)]}] if start >= 0 else []


def decision(inp: dict, res: dict, links: list[str] | None = None) -> dict[str, Any]:
    """Ślad decyzji: co wpłynęło na wybór i skąd pochodzi materiał (do raportu, grafu i audytu)."""
    return {"publisher": {"name": inp.get("sponsor") or inp.get("author"), "knfStatus": inp.get("author_knf"),
                          "role": (res.get("publisher") or {}).get("role"),
                          "impersonates": (res.get("publisher") or {}).get("impersonates")},
            "firm": res.get("firm"), "mentionedFirms": inp.get("mentioned_firms", []), "keywordSignals": inp.get("keywords", {}),
            "ruleFindings": [{"ruleId": str(r.get("id")), "status": r.get("status"), "quote": r.get("quote", ""),
                              "comment": r.get("comment", "")} for r in res.get("rules") or []],
            "riskSignals": res.get("risk_signals", []),
            "sources": {"url": inp.get("url"), "outboundLinks": list(links or [])},
            "trace": {"backend": BACKEND, "model": MODEL, "promptVersion": PROMPT_VERSION,
                      "decidedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}}


def overlay(analysis: dict, res: dict, inp: dict | None = None, links: list[str] | None = None) -> dict:
    """Nakłada wynik LLM na analizę ai-service (format odpowiedzi /analyze)."""
    if "error" in res:
        analysis["llm"] = {"backend": BACKEND, "model": MODEL, "error": res["error"]}
        return analysis
    context = (analysis.get("scoringInput") or {}).get("context") or {}
    res = enforce(res, bool(context.get("is_paid_ad")))
    module = res["module"]
    analysis["llm"] = {"backend": BACKEND, "model": MODEL, "prompt": PROMPT_VERSION, "module": module,
                       "confidence": res["confidence"], "scores": res["scores"], "reason": res.get("reason", ""),
                       "riskLevel": res.get("risk_level"), "riskSignals": res.get("risk_signals", []),
                       "needsHuman": bool(res.get("needs_human")) or res["confidence"] < 0.6}
    if inp is not None:
        analysis["llm"]["decision"] = decision(inp, res, links)
    analysis["adDisclosure"] = ad_disclosure(res["rules"], bool(context.get("is_paid_ad")), analysis.get("analyzedText", ""))
    analysis["modules"] = [int(module[1])] if module != "NONE" else []
    level = res.get("risk_level") if res.get("risk_level") in ("LOW", "MEDIUM", "HIGH", "CRITICAL") else "MEDIUM"
    analysis["riskLevel"] = level if module != "NONE" else "LOW"
    analysis["riskScore"] = res["confidence"] if module != "NONE" else round(1 - res["scores"]["NONE"], 3)
    text = analysis.get("analyzedText", "")
    llm_rules = {}
    for r in res.get("rules") or []:
        rid = str(r.get("id"))
        if rid not in VISUAL and r.get("status") in ("VIOLATION", "OK"):
            llm_rules[rid] = {"ruleId": rid, "status": r["status"], "score": 0.8 if r["status"] == "VIOLATION" else 0.0,
                              "evidence": _evidence(text, r.get("quote", ""))}
    # reguły tekstowe pochodzą wyłącznie z LLM; 4–8 zostają z pomiarów wizualnych
    analysis["rules"] = [r if r["ruleId"] in VISUAL else llm_rules.pop(r["ruleId"], {**r, "status": "NOT_APPLICABLE", "score": 0.0, "evidence": []})
                         for r in analysis.get("rules", [])] + list(llm_rules.values())
    analysis["flags"] = {k: {"p": 0.0, "evidence": []} for k in analysis.get("flags", {})}
    if module == "NONE":
        analysis["scam"] = {"p": 0.0, "signals": []}
    analysis["modelVersion"] = f"{MODEL} + {analysis.get('modelVersion', '')}"
    return analysis
