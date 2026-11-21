"""Nauczyciel (LLM w Ollamie, domyślnie Bielik 11B) – etykietuje dokumenty do treningu klasyfikatorów.

Wyjście jest wymuszone JSON Schema (structured outputs Ollamy), cytaty-dowody są dopasowywane do offsetów
w `Doc.full_text()`. Długie dokumenty (transkrypcje) są dzielone na fragmenty, a wyniki łączone.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from typing import Any

import httpx
import ollama

from .labels import (
    CONTENT_TYPE_PRIORITY,
    CONTENT_TYPES,
    ENTITY_ROLES,
    FLAG_KEYS,
    FLAGS,
    INSTRUMENTS,
    SCAM_CONFIDENCE,
    TOPIC_PRIORITY,
    TOPICS,
)
from .schema import Doc
from .text import align_quote, chunk_spans

DEFAULT_MODEL = os.environ.get("TEACHER_MODEL", "SpeakLeash/bielik-11b-v3.1-instruct:Q4_K_M")
DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

KIND_PL = {"post": "post", "comment": "komentarz", "transcript": "transkrypcja filmu", "page": "strona www"}


def _bullets(d: dict[str, str]) -> str:
    return "\n".join(f"- {k}: {v}" for k, v in d.items())


def build_system_prompt() -> str:
    flags = "\n".join(f"- {f.key}: {f.definition}" for f in FLAGS)
    return f"""Jesteś analitykiem nadzoru rynku finansowego (UKNF). Klasyfikujesz polskie treści z mediów \
społecznościowych: posty, komentarze, opisy i transkrypcje filmów. Transkrypcje pochodzą z automatycznego \
rozpoznawania mowy – często nie mają interpunkcji i zawierają błędy, interpretuj je ze zrozumieniem.

Zwróć wyłącznie JSON zgodny ze schematem. Pola:

rationale – 1–2 krótkie zdania po polsku: czym jest ta treść i dlaczego tak ją klasyfikujesz.

topic – jedna wartość:
{_bullets(TOPICS)}

content_type – jedna wartość:
{_bullets(CONTENT_TYPES)}

instruments – lista instrumentów, których dotyczy treść (może być pusta):
{_bullets(INSTRUMENTS)}

is_scam – true, gdy treść nosi cechy oszustwa inwestycyjnego: fałszywa platforma lub oferta, gwarantowane albo \
nierealne zyski, „bot/AI zarabia za Ciebie”, podszywanie się pod znane osoby, firmy lub media, niski depozyt na \
start, „zostaw numer – konsultant oddzwoni”, presja czasu. false dla: ostrzeżeń przed oszustwami i edukacji o \
nich, legalnych reklam z informacją o ryzyku, zwykłych opinii i dyskusji.
scam_confidence – low / medium / high: pewność oceny is_scam.

flags – sygnały obecne w tekście. Dla każdej flagi podaj dosłowny cytat z tekstu: skopiuj fragment bez zmian, \
maksymalnie 25 słów. Każdą flagę podaj najwyżej 2 razy. Nie podawaj flagi, jeśli nie umiesz wskazać fragmentu. \
Flagi podawaj tylko dla twierdzeń, które autor treści sam wygłasza lub którymi zachęca – nie dla cytowanych, \
krytykowanych lub opisywanych cudzych twierdzeń (np. w ostrzeżeniu przed oszustwem). Definicje:
{flags}

entities – firmy, marki, platformy i osoby istotne dla oceny (maks. 8), z rolą:
{_bullets(ENTITY_ROLES)}

Zasady rozróżniania:
1. Ostrzeżenie przed oszustwem, nawet jeśli opisuje obietnice oszustów → content_type NEWS_EDU, is_scam false, \
bez flag oszustwa.
2. Doradztwo (PERSONALIZED_ADVICE) wymaga dopasowania do sytuacji konkretnej osoby. Ogólne „kupujcie X” to \
SPECIFIC_INSTRUMENT_CALL i content_type RECOMMENDATION.
3. FIRM_OWN_MARKETING – publikuje sama firma o swojej ofercie. THIRD_PARTY_PROMO – osoba trzecia poleca firmę lub \
produkt (współpraca, kod lub link polecający, „partnerem odcinka jest”).
4. Lokaty, konta oszczędnościowe, kredyty, ubezpieczenia → FINANCIAL_OTHER. Obligacje, akcje, fundusze, ETF, \
kryptowaluty, forex → INVESTMENT.
5. Jeśli treść ma kilka części (np. film edukacyjny z segmentem sponsorowanym), content_type wybierz według części \
najważniejszej dla nadzoru, w kolejności: {" > ".join(CONTENT_TYPE_PRIORITY[:-1])}.
6. Gdy topic nie jest INVESTMENT: content_type NONE, is_scam false, flagi tylko jeśli faktycznie występują.

Odpowiedz wyłącznie jednym obiektem JSON (bez komentarzy i bez bloków ```), dokładnie w tym układzie:
{{"rationale": "...", "topic": "...", "content_type": "...", "instruments": ["..."], "is_scam": false, "scam_confidence": "low", "flags": [{{"flag": "PROFIT_CLAIM", "quote": "dosłowny fragment tekstu"}}], "entities": [{{"name": "...", "role": "investment_firm"}}]}}"""


def build_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "rationale": {"type": "string"},
            "topic": {"type": "string", "enum": list(TOPICS)},
            "content_type": {"type": "string", "enum": list(CONTENT_TYPES)},
            "instruments": {
                "type": "array",
                "items": {"type": "string", "enum": list(INSTRUMENTS)},
                "maxItems": len(INSTRUMENTS),
            },
            "is_scam": {"type": "boolean"},
            "scam_confidence": {"type": "string", "enum": SCAM_CONFIDENCE},
            "flags": {
                "type": "array",
                "maxItems": 16,
                "items": {
                    "type": "object",
                    "properties": {
                        "flag": {"type": "string", "enum": FLAG_KEYS},
                        "quote": {"type": "string"},
                    },
                    "required": ["flag", "quote"],
                    "additionalProperties": False,
                },
            },
            "entities": {
                "type": "array",
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "role": {"type": "string", "enum": list(ENTITY_ROLES)},
                    },
                    "required": ["name", "role"],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "rationale", "topic", "content_type", "instruments",
            "is_scam", "scam_confidence", "flags", "entities",
        ],
        "additionalProperties": False,
    }


def parse_label(content: str) -> dict[str, Any]:
    """Tolerancyjny parser odpowiedzi LLM: wycina JSON, uzupełnia braki, odrzuca wartości spoza taksonomii."""
    content = content or ""
    start = content.find("{")
    if start < 0:
        raise ValueError("brak JSON w odpowiedzi")
    d, _ = json.JSONDecoder().raw_decode(content[start:])  # pierwszy kompletny obiekt, reszta ignorowana
    topic = d.get("topic") if d.get("topic") in TOPICS else "NON_FINANCIAL"
    ctype = d.get("content_type") if d.get("content_type") in CONTENT_TYPES else "NONE"
    flags = []
    for f in d.get("flags") or []:
        if isinstance(f, str):
            f = {"flag": f, "quote": ""}
        if isinstance(f, dict) and f.get("flag") in FLAG_KEYS:
            flags.append({"flag": f["flag"], "quote": str(f.get("quote") or "")})
    ents = []
    for e in d.get("entities") or []:
        if isinstance(e, dict) and e.get("name"):
            ents.append({"name": str(e["name"]), "role": e.get("role") if e.get("role") in ENTITY_ROLES else "other"})
    fset = {f["flag"] for f in flags}
    if topic == "INVESTMENT" and ctype == "NONE":  # niespójność modelu – typ z flag
        if fset & {"PAID_ADVISORY_SERVICE", "PERSONALIZED_ADVICE"}:
            ctype = "SERVICE_OFFER"
        elif "AD_DISCLOSURE" in fset:
            ctype = "THIRD_PARTY_PROMO"
        elif "SPECIFIC_INSTRUMENT_CALL" in fset:
            ctype = "RECOMMENDATION"
        else:
            ctype = "NEWS_EDU"
    if topic != "INVESTMENT":
        ctype = "NONE"
    conf = d.get("scam_confidence") if d.get("scam_confidence") in SCAM_CONFIDENCE else "low"
    is_scam = d.get("is_scam")
    is_scam = is_scam if isinstance(is_scam, bool) else str(is_scam).lower() == "true"
    return {
        "rationale": str(d.get("rationale") or ""), "topic": topic, "content_type": ctype,
        "instruments": [i for i in (d.get("instruments") or []) if i in INSTRUMENTS],
        "is_scam": is_scam, "scam_confidence": conf, "flags": flags[:16], "entities": ents[:8],
    }


SYSTEM_PROMPT = build_system_prompt()
SCHEMA = build_schema()
PROMPT_VERSION = "v1-" + hashlib.sha1((SYSTEM_PROMPT + json.dumps(SCHEMA)).encode()).hexdigest()[:8]


def user_message(doc: Doc, chunk: str, part: int, parts: int) -> str:
    head = [f"Platforma: {doc.platform}", f"Rodzaj: {KIND_PL.get(doc.kind, doc.kind)}"]
    if doc.author:
        head.append(f"Autor: {doc.author}")
    if parts > 1:
        head.append(f"Fragment {part}/{parts} dłuższej treści")
    return " | ".join(head) + "\n\nTREŚĆ:\n" + chunk


# ---------------------------------------------------------------- Ollama helpers


def list_models(host: str = DEFAULT_HOST) -> list[str] | None:
    """Lista modeli w Ollamie albo None, gdy serwer nie odpowiada."""
    try:
        r = httpx.get(f"{host}/api/tags", timeout=5)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return None


def model_available(model: str, host: str = DEFAULT_HOST) -> bool | None:
    names = list_models(host)
    if names is None:
        return None
    want = model.lower()
    return any(n.lower() in (want, f"{want}:latest") for n in names)


def wait_for_model(model: str, host: str = DEFAULT_HOST, poll_s: int = 20, log=print) -> None:
    last = None
    while True:
        ok = model_available(model, host)
        if ok:
            log(f"[teacher] model dostępny: {model}")
            return
        state = "serwer Ollamy nie odpowiada" if ok is None else "model jeszcze niepobrany"
        if state != last:
            log(f"[teacher] czekam: {state} ({host}, {model}); sprawdzam co {poll_s}s")
            last = state
        time.sleep(poll_s)


# ---------------------------------------------------------------- Teacher


class Teacher:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        host: str = DEFAULT_HOST,
        num_ctx: int = 6144,
        chunk_chars: int = 6000,
        max_doc_chars: int = 12000,
        temperature: float = 0.0,
        num_predict: int = 1200,
        retries: int = 2,
    ):
        self.model = model
        self.host = host
        self.num_ctx = num_ctx
        self.chunk_chars = chunk_chars
        self.max_doc_chars = max_doc_chars
        self.temperature = temperature
        self.num_predict = num_predict
        self.retries = retries
        self._local = threading.local()
        self.use_format = True  # wyłączane automatycznie, gdy Ollama nie umie zbudować gramatyki

    @property
    def client(self) -> ollama.Client:
        c = getattr(self._local, "client", None)
        if c is None:
            c = ollama.Client(host=self.host, timeout=600)
            self._local.client = c
        return c

    def warmup(self) -> float:
        t = time.time()
        self.client.generate(model=self.model, prompt="OK", keep_alive="2h",
                             options={"num_ctx": self.num_ctx, "num_predict": 1})
        return time.time() - t

    def _call(self, user: str, temperature: float) -> tuple[dict[str, Any], dict[str, Any]]:
        kw = dict(
            model=self.model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
            options={"temperature": temperature, "num_ctx": self.num_ctx, "num_predict": self.num_predict, "seed": 42},
            keep_alive="2h",
        )
        if self.use_format:
            try:
                resp = self.client.chat(format=SCHEMA, **kw)
            except ollama.ResponseError as ex:
                if "sampler" not in str(ex).lower():
                    raise
                self.use_format = False
                resp = self.client.chat(**kw)
        else:
            resp = self.client.chat(**kw)
        data = parse_label(resp.message.content or "")
        stats = {
            "prompt_tokens": resp.prompt_eval_count,
            "output_tokens": resp.eval_count,
            "seconds": round((resp.total_duration or 0) / 1e9, 2),
        }
        return data, stats

    def _wait_backend(self) -> None:
        wait_for_model(self.model, self.host, poll_s=10, log=lambda _m: None)

    def label_doc(self, doc: Doc) -> dict[str, Any]:
        full = doc.full_text()
        truncated = len(full) > self.max_doc_chars
        text = full[: self.max_doc_chars]
        spans = chunk_spans(text, self.chunk_chars, overlap=300)
        chunk_results: list[dict[str, Any]] = []
        stats_total = {"prompt_tokens": 0, "output_tokens": 0, "seconds": 0.0}
        t0 = time.time()
        for i, (s, e) in enumerate(spans, start=1):
            user = user_message(doc, text[s:e], i, len(spans))
            last_err: Exception | None = None
            for attempt in range(self.retries + 1):
                try:
                    temp = self.temperature if attempt == 0 else 0.3
                    data, st = self._call(user, temp)
                    break
                except (ConnectionError, httpx.TransportError) as ex:  # restart Ollamy – czekamy, nie tracimy dok.
                    last_err = ex
                    self._wait_backend()
                except Exception as ex:  # zły JSON / timeout / błąd modelu
                    last_err = ex
                    time.sleep(5 * (attempt + 1))
            else:
                raise RuntimeError(f"chunk {i}/{len(spans)}: {type(last_err).__name__}: {last_err}")
            for k in stats_total:
                stats_total[k] += st.get(k) or 0
            chunk_results.append({"start": s, "end": e, "label": data})
        merged = merge_chunks(chunk_results, full)
        stats_total["wall_seconds"] = round(time.time() - t0, 2)
        return {
            "id": doc.id,
            "model": self.model,
            "prompt_version": PROMPT_VERSION,
            "label": merged,
            "chunks": chunk_results if len(chunk_results) > 1 else None,
            "n_chunks": len(chunk_results),
            "truncated": truncated,
            "stats": stats_total,
            "labeled_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }


def merge_chunks(chunks: list[dict[str, Any]], full_text: str) -> dict[str, Any]:
    """Łączy etykiety fragmentów w etykietę dokumentu i dopasowuje cytaty do offsetów w pełnym tekście."""
    labels = [c["label"] for c in chunks]
    topic = min((lb.get("topic", "NON_FINANCIAL") for lb in labels), key=TOPIC_PRIORITY.index)
    ctype = min((lb.get("content_type", "NONE") for lb in labels), key=CONTENT_TYPE_PRIORITY.index)
    if topic != "INVESTMENT":
        ctype = "NONE"
    instruments = sorted({i for lb in labels for i in lb.get("instruments", [])})
    conf_rank = {c: i for i, c in enumerate(SCAM_CONFIDENCE)}
    scam_votes = [lb for lb in labels if lb.get("is_scam")]
    is_scam = bool(scam_votes)
    pool = scam_votes or labels
    scam_conf = max((lb.get("scam_confidence", "low") for lb in pool), key=lambda c: conf_rank.get(c, 0))

    flags: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None]] = set()
    for c in chunks:
        chunk_text = full_text[c["start"] : c["end"]]
        for fh in c["label"].get("flags", []):
            al = align_quote(chunk_text, fh.get("quote", ""))
            start = end = score = None
            if al:
                start, end, score = c["start"] + al[0], c["start"] + al[1], al[2]
            key = (fh["flag"], start)
            if key in seen:
                continue
            seen.add(key)
            flags.append({"flag": fh["flag"], "quote": fh.get("quote", ""), "start": start, "end": end,
                          "align_score": score})

    entities: list[dict[str, str]] = []
    seen_e: set[str] = set()
    for lb in labels:
        for en in lb.get("entities", []):
            k = en.get("name", "").strip().lower()
            if k and k not in seen_e:
                seen_e.add(k)
                entities.append({"name": en["name"].strip(), "role": en.get("role", "other")})

    return {
        "rationale": " | ".join(lb.get("rationale", "") for lb in labels if lb.get("rationale")),
        "topic": topic,
        "content_type": ctype,
        "instruments": instruments,
        "is_scam": is_scam,
        "scam_confidence": scam_conf,
        "flags": flags,
        "entities": entities[:12],
    }


# ---------------------------------------------------------------- Gemini (drugi nauczyciel, tylko do danych)


def _strip_additional(schema: Any) -> Any:
    if isinstance(schema, dict):
        return {k: _strip_additional(v) for k, v in schema.items() if k not in ("additionalProperties", "maxItems")}
    if isinstance(schema, list):
        return [_strip_additional(v) for v in schema]
    return schema


def load_env(path: str | None = None) -> None:
    from pathlib import Path

    p = Path(path) if path else Path(__file__).resolve().parents[2] / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


class GeminiTeacher(Teacher):
    """Ten sam prompt i schemat co Bielik; wywołanie REST Gemini API. Obsługa limitów darmowego planu (429)."""

    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, model: str = "gemini-3.5-flash-lite", **kw: Any):
        load_env()
        super().__init__(model=model, **kw)
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("Brak GEMINI_API_KEY w ml/.env")
        self.max_doc_chars = kw.get("max_doc_chars", 30000)  # długi kontekst – bez dzielenia na fragmenty
        self.chunk_chars = kw.get("chunk_chars", 30000)
        self._http = httpx.Client(timeout=120)
        self._schema = _strip_additional(SCHEMA)
        self._use_schema = False  # Gemini odrzuca nasz schemat jako zbyt złożony – sam JSON + walidacja promptem

    def warmup(self) -> float:
        return 0.0

    def _wait_backend(self) -> None:
        """API w chmurze: czekaj na powrót sieci (maks. 30 min); nie pytaj lokalnej Ollamy o model, którego tam nie ma."""
        for _ in range(120):
            try:
                httpx.get(self.URL.split("/v1")[0] + "/", timeout=10)
                return
            except httpx.TransportError:
                time.sleep(15)

    def _call(self, user: str, temperature: float) -> tuple[dict[str, Any], dict[str, Any]]:
        body = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": temperature, "responseMimeType": "application/json",
                                 **({"responseJsonSchema": self._schema} if self._use_schema else {})},
        }
        t = time.time()
        for attempt in range(6):
            r = self._http.post(self.URL.format(model=self.model), json=body,
                                headers={"x-goog-api-key": self.api_key})
            if r.status_code == 400 and "generationConfig" in body and "responseJsonSchema" in body["generationConfig"]:
                body["generationConfig"].pop("responseJsonSchema")  # schemat za złożony – sam JSON + walidacja
                continue
            if r.status_code in (429, 500, 503):
                time.sleep(min(15 * (attempt + 1), 90))  # limit darmowego planu
                continue
            r.raise_for_status()
            d = r.json()
            text = d["candidates"][0]["content"]["parts"][0]["text"]
            um = d.get("usageMetadata", {})
            return parse_label(text), {"prompt_tokens": um.get("promptTokenCount"),
                                      "output_tokens": um.get("candidatesTokenCount"),
                                      "seconds": round(time.time() - t, 2)}
        raise RuntimeError(f"Gemini: limit / błąd {r.status_code}: {r.text[:200]}")


# ---------------------------------------------------------------- Groq (API zgodne z OpenAI, tylko do danych)


class GroqTeacher(Teacher):
    """Ten sam prompt co Bielik/Gemini; szybka inferencja w chmurze Groq. Obsługa limitów (429 + retry-after)."""

    URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, model: str = "llama-3.3-70b-versatile", **kw: Any):
        load_env()
        super().__init__(model=model, **kw)
        self.api_key = os.environ.get("GROQ_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("Brak GROQ_API_KEY w ml/.env")
        self.max_doc_chars = kw.get("max_doc_chars", 24000)
        self.chunk_chars = kw.get("chunk_chars", 12000)
        self._http = httpx.Client(timeout=120)

    def warmup(self) -> float:
        return 0.0

    def _wait_backend(self) -> None:
        """API w chmurze: czekaj na powrót sieci (maks. 30 min); nie pytaj lokalnej Ollamy o model, którego tam nie ma."""
        for _ in range(120):
            try:
                httpx.get(self.URL.split("/v1")[0] + "/", timeout=10)
                return
            except httpx.TransportError:
                time.sleep(15)

    def _call(self, user: str, temperature: float) -> tuple[dict[str, Any], dict[str, Any]]:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": self.num_predict,
            "response_format": {"type": "json_object"},
        }
        t = time.time()
        for attempt in range(8):
            r = self._http.post(self.URL, json=body, headers={"Authorization": f"Bearer {self.api_key}"})
            if r.status_code in (429, 500, 502, 503):
                wait = float(r.headers.get("retry-after") or 10 * (attempt + 1))
                time.sleep(min(wait, 90))
                continue
            r.raise_for_status()
            d = r.json()
            um = d.get("usage", {})
            return parse_label(d["choices"][0]["message"]["content"]), {
                "prompt_tokens": um.get("prompt_tokens"), "output_tokens": um.get("completion_tokens"),
                "seconds": round(time.time() - t, 2)}
        raise RuntimeError(f"Groq: limit / błąd {r.status_code}: {r.text[:200]}")
