"""Klasyfikacja rekordów scrapera w modułach 1–3 przez Groq (prompt: ml/src/investwatch_ml/classifier_prompt.md).

Paczki po kilka rekordów (prompt systemowy raz na paczkę), wynik cache'owany po treści i wersji promptu,
więc ten sam tekst nie jest oceniany dwa razy. Nieudana paczka jest ponawiana rekord po rekordzie.
Rekordy, które nie zmieściły się w limicie, zostają na kolejny przebieg (np. z crona).

  python ml/scripts/classify_groq.py --input ml/data/skill/zip_clean.jsonl --limit 20
  python ml/scripts/classify_groq.py --input "ml/data/raw/scraper_live/hunt_*/records.jsonl"
Wyjście: ml/data/skill/groq_labels.jsonl
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from investwatch_ml import keywords, knf  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
PROMPT_PATH = ROOT / "ml/src/investwatch_ml/classifier_prompt.md"
OUT = ROOT / "ml/data/skill/groq_labels.jsonl"
URL = "https://api.groq.com/openai/v1/chat/completions"
SECTIONS = ("title", "post", "ad_body", "description", "link_description", "cta", "transcript", "ocr", "page", "risk_disclaimer")


def log(m: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)


KEY_NAME = os.environ.get("GROQ_KEY_NAME", "GROQ_API_KEY")  # np. GROQ_API_KEY_2 dla drugiego klucza


def api_key() -> str:
    for env in (ROOT / "ml/.env", ROOT / ".env"):
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.startswith(KEY_NAME + "="):
                    return line.split("=", 1)[1].strip().strip('"')
    return os.environ["GROQ_API_KEY"]


def to_input(r: dict, max_chars: int) -> dict:
    """Rekord kolektora albo zip_clean -> zwięzłe wejście dla modelu."""
    sec = r.get("sections") or (r.get("text") if isinstance(r.get("text"), dict) else {"post": str(r.get("text") or "")})
    text = "\n".join(f"[{k}] {' '.join(str(sec[k]).split())}" for k in sorted(sec, key=lambda k: SECTIONS.index(k) if k in SECTIONS else 99) if str(sec[k]).strip())
    url = r.get("url") or r.get("source_url") or ""
    rid = r.get("id") or "u" + hashlib.sha1(url.encode()).hexdigest()[:12]
    reg = knf.register()
    who = r.get("sponsor") or r.get("author")
    status = "UNKNOWN"
    if who:
        hit = reg.lookup(who)
        status = hit["status"]
        if status != "REGISTERED":
            brand = (knf.tokens(who) or [""])[0]
            same = hit.get("relatedEntity") or next((e["name"] for e in reg.entities
                                                     if len(brand) >= 3 and (knf.tokens(e["name"]) or [""])[0] == brand), None)
            if same:
                status = f"SAME_BRAND:{same}"
    mentioned = sorted({e["name"] for e in reg.mentions(text)})[:5]
    return {"id": rid, "source": r.get("source") or r.get("folder"), "author": r.get("author"), "sponsor": r.get("sponsor"),
            "author_knf": status, "mentioned_firms": mentioned, "keywords": keywords.analyze(text), "content_type": r.get("content_type"), "url": url,
            "text": text[:max_chars]}


def content_key(item: dict, prompt_version: str) -> str:
    return hashlib.sha1(f"{prompt_version}|{item['author']}|{item['text']}".encode()).hexdigest()


def parse_array(text: str) -> list[dict]:
    """Tablica JSON albo jeden lub kilka obiektów jeden po drugim (lokalne modele często pomijają tablicę)."""
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            nested = next((v for v in data.values() if isinstance(v, list) and v and isinstance(v[0], dict) and "scores" in v[0]), None)
            return nested or [data]
    except json.JSONDecodeError:
        pass
    dec, out, i = json.JSONDecoder(), [], 0
    while i < len(text):
        j = text.find("{", i)
        if j < 0:
            break
        try:
            obj, end = dec.raw_decode(text, j)
        except json.JSONDecodeError:
            i = j + 1
            continue
        if isinstance(obj, dict) and "scores" in obj:
            out.append(obj)
        i = end
    if not out:
        raise ValueError("brak obiektów z wynikiem")
    return out


class Groq:
    def __init__(self, model: str, prompt: str, backend: str = "groq"):
        self.model, self.prompt, self.backend = model, prompt, backend
        headers = {"Authorization": f"Bearer {api_key()}"} if backend == "groq" else {}
        self.http = httpx.Client(timeout=900, headers=headers)
        self.tokens = 0

    def call_ollama(self, items: list[dict]) -> list[dict]:
        """Lokalny model przez Ollamę (np. Bielik). Bez wymuszania formatu: Ollama z Bielikiem go nie obsługuje."""
        body = {"model": self.model, "stream": False, "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": 700 * len(items) + 300},
                "messages": [{"role": "system", "content": self.prompt},
                             {"role": "user", "content": "Oceń rekordy:\n" + json.dumps(items, ensure_ascii=False)}]}
        r = self.http.post("http://localhost:11434/api/chat", json=body)
        r.raise_for_status()
        d = r.json()
        self.tokens += (d.get("prompt_eval_count") or 0) + (d.get("eval_count") or 0)
        return parse_array(d["message"]["content"])

    def call(self, items: list[dict]) -> list[dict]:
        if self.backend == "ollama":
            return self.call_ollama(items)
        body = {"model": self.model, "temperature": 0.1, "max_tokens": 900 * len(items) + 400,
                "messages": [{"role": "system", "content": self.prompt},
                             {"role": "user", "content": "Oceń rekordy:\n" + json.dumps(items, ensure_ascii=False)}]}
        if self.model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = "low"
        for attempt in range(6):
            try:
                r = self.http.post(URL, json=body)
            except httpx.TransportError:
                time.sleep(30)
                continue
            if r.status_code == 429:
                msg = r.text
                if "per day" in msg or "TPD" in msg or "RPD" in msg:
                    raise RuntimeError("dzienny limit Groq")
                time.sleep(min(float(r.headers.get("retry-after") or 20 * (attempt + 1)), 120))
                continue
            if r.status_code >= 500:
                time.sleep(15)
                continue
            r.raise_for_status()
            d = r.json()
            self.tokens += d.get("usage", {}).get("total_tokens", 0)
            return parse_array(d["choices"][0]["message"]["content"])
        raise RuntimeError("Groq: wyczerpane ponowienia")


def valid(res: dict) -> bool:
    s = res.get("scores")
    if not (isinstance(s, dict) and all(isinstance(s.get(k), (int, float)) for k in ("M1", "M2", "M3"))):
        return False
    s.setdefault("NONE", max(0.0, 1 - s["M1"] - s["M2"] - s["M3"]))
    total = sum(float(s[k]) for k in ("M1", "M2", "M3", "NONE")) or 1.0
    for k in ("M1", "M2", "M3", "NONE"):  # normalizacja: moduły się wykluczają
        s[k] = round(float(s[k]) / total, 3)
    res["module"] = max(("M1", "M2", "M3", "NONE"), key=s.get)
    res["confidence"] = s[res["module"]]
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="plik lub wzorzec glob (jsonl)")
    ap.add_argument("--model", default="openai/gpt-oss-120b")
    ap.add_argument("--batch", type=int, default=6)
    ap.add_argument("--max-chars", type=int, default=1500)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--backend", choices=("groq", "ollama"), default="groq")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    global OUT
    if args.out:
        OUT = Path(args.out)
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    version = hashlib.sha1(prompt.encode()).hexdigest()[:8]
    done = set()
    if OUT.exists():
        done = {json.loads(l)["key"] for l in OUT.read_text(encoding="utf-8").splitlines() if l.strip()
                and json.loads(l).get("model") == args.model}
    items, seen = [], set()
    for f in sorted(glob.glob(args.input)):
        for line in open(f, encoding="utf-8"):
            if not line.strip():
                continue
            it = to_input(json.loads(line), args.max_chars)
            k = content_key(it, version)
            if k in done or k in seen or len(it["text"]) < 20:
                continue
            seen.add(k)
            it["_key"] = k
            items.append(it)
    items = items[: args.limit] if args.limit else items
    log(f"do oceny: {len(items)} (prompt {version}, pominięte z cache: {len(done)})")
    groq = Groq(args.model, prompt, args.backend)
    ok = 0

    def save(it: dict, res: dict) -> None:
        nonlocal ok
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps({"key": it["_key"], "id": it["id"], "url": it["url"], "prompt": version, "model": args.model,
                                "result": res}, ensure_ascii=False) + "\n")
        ok += 1

    try:
        for i in range(0, len(items), args.batch):
            batch = items[i: i + args.batch]
            clean = [{k: v for k, v in it.items() if k != "_key"} for it in batch]
            try:
                res = {str(x.get("id")): x for x in groq.call(clean)}
                if not all(valid(res.get(it["id"], {})) for it in batch):
                    raise ValueError("niepełna odpowiedź")
                for it in batch:
                    save(it, res[it["id"]])
            except (ValueError, json.JSONDecodeError, KeyError, TypeError) as e:
                log(f"paczka {i // args.batch}: {type(e).__name__}; ponawiam pojedynczo")
                for it, c in zip(batch, clean):
                    try:
                        r = groq.call([c])
                        if r and valid(r[0]):
                            save(it, r[0])
                    except (ValueError, json.JSONDecodeError, KeyError, TypeError, httpx.HTTPError):
                        log(f"  {it['id']}: nieudane")
            log(f"{min(i + args.batch, len(items))}/{len(items)} | zapisane {ok} | tokeny {groq.tokens}")
    except RuntimeError as e:
        log(f"przerwano: {e}; reszta zostaje na kolejny przebieg")
    log(f"koniec: +{ok} -> {OUT}")


if __name__ == "__main__":
    main()
