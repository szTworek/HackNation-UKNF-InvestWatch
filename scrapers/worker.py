"""scrape-worker: kolejka przebiegów kolektorów sterowana z aplikacji (przycisk i harmonogram).

Przebieg: kolektory -> adaptery -> pomijanie znanych adresów -> filtr języka -> LLM w ai-service -> gotowe rekordy.
Gotowe rekordy trafiają do Postgresa (items + findings), a API pobiera je na bieżąco przez GET /findings?after=N. Usługa słucha tylko w sieci wewnętrznej Compose.
Rekordy bez oceny LLM (np. po wyczerpaniu limitu) czekają na kolejny przebieg i nie trafiają do aplikacji.
Meta jest tylko ręczna: kolektor działa przez stronę WWW, a regulamin dopuszcza automatyczne zbieranie wyłącznie przez API.
"""
import importlib
import json
import os
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

APP = Path(__file__).resolve().parents[1]
for extra in (APP / "db", APP / "ml/scripts", APP / "scripts", APP / "preprocessing/ocr", APP, APP / "scrapers/poc"):
    sys.path.insert(0, str(extra))

JOBS = Path(os.environ.get("JOBS_DIR", "/jobs"))
STATE = JOBS / "state.json"
OUT = JOBS / "findings.jsonl"
AI_URL = os.environ.get("AI_URL", "http://ai-service:8000").rstrip("/")
API_URL = os.environ.get("API_URL", "http://api:4000").rstrip("/")
BATCH = 6
INTERVALS = (15, 30, 60, 180, 360)
ADAPTERS = {"youtube": "youtube", "tiktok": "tiktok", "google_ads_transparency": "google_ads",
            "meta_ad_library": "meta_ads", "microsoft_ad_library": "bing_ads"}
# (kolektor, etykieta, zapytania, ile zapytań na przebieg): rotacja, żeby nie uderzać w źródła tym samym
SOURCES = [
    ("bing_ads.ms_adlib", "Bing", ["inwestycje", "inwestuj", "broker", "trading", "kryptowaluty", "zarabiaj", "mentoring", "doradca",
                                   "konsultacje", "akademia"], 2),
    ("youtube_posts.ytdlp", "YouTube", ["sygnały forex", "gwarantowany zysk inwestycja", "grupa vip trading", "typy giełdowe",
                                        "pasywny dochód inwestycja", "kod polecający broker", "bot inwestycyjny", "zarabiaj na kryptowalutach"], 2),
    ("tiktok_posts.embed_ytdlp", "TikTok", ["@xtbpl", "@kacper_snela", "@profit_investing", "@wladcamonet", "@mr_pankracy"], 1),
    ("google_ads.atc_rpc", "Google", ["XTB", "mBank", "eToro", "Plus500", "Trading 212", "bossa.pl"], 1),
]
META = ("fb_ads.ad_library_web", "Meta", ["apartament inwestycyjny gwarantowany zysk", "zysk bez ryzyka", "pasywny dochód inwestycja",
                                          "grupa vip trading", "typy giełdowe", "pko inwestycje", "mbank inwestycje", "xtb społeczność"], 2)

lock = threading.RLock()
state = {"schedule": {"enabled": False, "intervalMin": 60, "nextRunAt": None}, "offsets": {}, "pending": [], "seen": [], "last": None}
live = {"running": False, "phase": "idle", "trigger": None, "startedAt": None, "done": 0, "total": 0, "current": None}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def log(msg: str) -> None:
    print(f"[worker] {msg}", flush=True)


def save() -> None:
    with lock:
        JOBS.mkdir(parents=True, exist_ok=True)
        tmp = STATE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        tmp.replace(STATE)


def http(method: str, url: str, payload=None, timeout: int = 900):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as res:  # noqa: S310 - adresy usług z konfiguracji
        return json.load(res)


def plan(include_meta: bool) -> list[tuple[str, str, str]]:
    out = []
    for collector, label, queries, n in SOURCES + ([META] if include_meta else []):
        start = state["offsets"].get(collector, 0)
        out += [(collector, label, queries[(start + i) % len(queries)]) for i in range(n)]
        state["offsets"][collector] = (start + n) % len(queries)
    return out


def clean_meta(raw: dict) -> dict:
    from convert_fb_ads_web import parse_ad

    text = "\n".join(s.get("text", "") for s in raw.get("text") or [] if isinstance(s, dict))
    start, meta, body, title, desc, cta, domain = parse_ad(text)
    raw["text"] = {k: v for k, v in (("ad_body", "\n".join(body)), ("title", title), ("link_description", desc), ("cta", cta)) if v}
    raw["published_at"] = start
    raw["links"] = [f"https://{domain.lower()}"] if domain else []
    raw["source_meta"] = {**(raw.get("source_meta") or {}), **meta}
    return raw


def enrich_image(raw: dict) -> dict:
    """Reklama obrazkowa: tekst z OCR i pomiary układu do reguł 4–6."""
    refs = (raw.get("source_meta") or {}).get("image_refs") or []
    if not refs:
        return raw
    try:
        from layout import measure
        from rapid import ocr_image

        path = Path(refs[0])
        if not raw.get("text"):
            result = ocr_image(str(path))
            if result.get("text"):
                raw["text"] = [{"type": "ocr", "text": result["text"]}]
        layout = measure(path)
        if layout:
            raw["source_meta"]["ocr_layout"] = layout
    except Exception as e:  # pojedyncza grafika nie przerywa przebiegu
        log(f"OCR: {type(e).__name__}: {str(e)[:100]}")
    return raw


def to_record(raw: dict) -> dict | None:
    name = ADAPTERS.get(raw.get("source"))
    if not name:
        return None
    if raw["source"] == "meta_ad_library":
        raw = clean_meta(raw)
    if raw["source"] == "google_ads_transparency":
        raw = enrich_image(raw)
    if not raw.get("text"):
        return None
    return importlib.import_module(f"adapters.{name}").to_record(raw)


def text_of(record: dict) -> str:
    t = record.get("text")
    return "\n".join(str(v) for v in t.values()) if isinstance(t, dict) else str(t or "")


def persist(record: dict, finding: dict) -> None:
    """Zapis do Postgresa; bez bazy rekord zostaje tylko w findings.jsonl."""
    try:
        import store

        with store.connect() as conn, conn.cursor() as cur:
            iid = store.upsert_item(cur, record, "worker")
            store.link_item(cur, iid, record)  # nowy rekord od razu trafia na oś podmiotu
            store.save_finding(cur, iid, finding)
    except Exception as e:
        log(f"Postgres: {type(e).__name__}: {str(e)[:100]}")


def classify(records: list[dict], stats: Counter) -> list[dict]:
    """Zapisuje rekordy ocenione przez LLM. Zwraca te, które muszą poczekać."""
    import build_findings as bf

    cert = bf.load_cert_domains()
    waiting: list[dict] = []
    for i in range(0, len(records), BATCH):
        chunk = records[i:i + BATCH]
        live.update(phase="llm", current=f"ocena LLM {min(i + BATCH, len(records))}/{len(records)}")
        try:
            results = http("POST", f"{AI_URL}/ingest", {"records": chunk})["results"]
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            stats["llmErrors"] += 1
            log(f"ai-service: {e}")
            return waiting + records[i:]
        by_url = {r.get("source_url"): r for r in chunk}
        limited = False
        for x in results:
            analysis, url = x["analysis"], x["item"]["url"]
            llm = analysis.get("llm") or {}
            if "module" not in llm:
                stats["llmErrors"] += 1
                limited = limited or "429" in str(llm.get("error"))
                waiting.append(by_url[url])
                continue
            finding = bf.to_finding(x["item"], analysis, now(), cert, stats)
            persist(by_url[url], finding)
            with lock, open(OUT, "a", encoding="utf-8") as f:
                f.write(json.dumps(finding, ensure_ascii=False) + "\n")
                state["seen"].append(url)
            stats["classified"] += 1
            stats[f"module.{llm['module']}"] += 1
        save()
        if limited:
            stats["llmLimit"] = 1
            return waiting + records[i + BATCH:]
    return waiting


def run(trigger: str, include_meta: bool) -> None:
    stats: Counter = Counter()
    errors: list[str] = []
    started = now()
    try:
        health = http("GET", f"{AI_URL}/health", timeout=15)
        if not (health.get("llm") or {}).get("model"):
            raise RuntimeError("ai-service działa bez LLM: ustaw LLM_BACKEND=groq albo ollama")
        import registry

        with lock:
            jobs = plan(include_meta)
            pending = list(state["pending"])
            state["pending"] = []
        live.update(total=len(jobs), done=0)
        try:
            known = set(http("GET", f"{API_URL}/api/jobs/known", timeout=20)["urls"])
        except Exception:
            known = set()
        known |= set(state["seen"]) | {r.get("source_url") for r in pending}
        fresh: list[dict] = []
        for collector, label, query in jobs:
            live.update(phase="scraping", current=f"{label}: {query}")
            try:
                for raw in registry.collector(collector)(query, {}):
                    stats["fetched"] += 1
                    try:
                        record = to_record(raw)
                    except Exception as e:
                        stats["parseErrors"] += 1
                        log(f"{collector}: {type(e).__name__}: {str(e)[:100]}")
                        continue
                    url = (record or {}).get("source_url")
                    if not record or not url or url in known:
                        continue
                    known.add(url)
                    fresh.append(record)
            except Exception as e:  # awaria jednego źródła nie zatrzymuje pozostałych
                errors.append(f"{label} ({query}): {type(e).__name__}")
                log(traceback.format_exc(limit=2))
            live["done"] += 1
        stats["new"] = len(fresh)
        live.update(phase="language", current="filtr języka")
        polish: list[dict] = []
        if fresh:
            flags = http("POST", f"{AI_URL}/language", {"texts": [text_of(r) for r in fresh]})["polish"]
            polish = [r for r, ok in zip(fresh, flags) if ok]
            with lock:
                state["seen"] += [r["source_url"] for r, ok in zip(fresh, flags) if not ok]
        stats["polish"] = len(polish)
        stats["notPolish"] = len(fresh) - len(polish)
        waiting = classify(pending + polish, stats)
        with lock:
            state["pending"] = waiting[:1000]
        stats["pending"] = len(state["pending"])
        if stats.get("llmLimit"):
            errors.append("Limit LLM: pozostałe rekordy czekają na kolejny przebieg")
    except Exception as e:
        errors.append(str(e)[:200])
        log(traceback.format_exc(limit=3))
    finally:
        with lock:
            state["last"] = {"trigger": trigger, "includeMeta": include_meta, "startedAt": started, "finishedAt": now(),
                             "stats": dict(stats), "errors": errors[:6]}
            sch = state["schedule"]
            if sch["enabled"]:
                sch["nextRunAt"] = (datetime.now(timezone.utc) + timedelta(minutes=sch["intervalMin"])).isoformat(timespec="seconds").replace("+00:00", "Z")
            save()
        live.update(running=False, phase="idle", current=None)
        log(f"koniec przebiegu: {dict(stats)} {errors}")


def start(trigger: str, include_meta: bool) -> bool:
    with lock:
        if live["running"]:
            return False
        live.update(running=True, phase="starting", trigger=trigger, startedAt=now(), done=0, total=0, current=None)
    threading.Thread(target=run, args=(trigger, include_meta), daemon=True).start()
    return True


def scheduler() -> None:
    while True:
        time.sleep(5)
        sch = state["schedule"]
        if sch["enabled"] and sch.get("nextRunAt") and now() >= sch["nextRunAt"]:
            start("auto", False)  # Meta nigdy w trybie automatycznym


def status() -> dict:
    with lock:
        total = sum(1 for _ in open(OUT, encoding="utf-8")) if OUT.exists() else 0
        return {"run": dict(live), "schedule": dict(state["schedule"]), "last": state["last"], "pending": len(state["pending"]),
                "collected": total, "intervals": list(INTERVALS),
                "sources": [s[1] for s in SOURCES], "manualOnly": [META[1]]}


class Handler(BaseHTTPRequestHandler):
    def reply(self, code: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n or n > 10000:
            return {}
        try:
            value = json.loads(self.rfile.read(n))
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}

    def do_GET(self):  # noqa: N802
        url = urlsplit(self.path)
        if url.path == "/health":
            return self.reply(200, {"status": "ok"})
        if url.path == "/status":
            return self.reply(200, status())
        if url.path == "/findings":
            try:
                after = max(0, int((parse_qs(url.query).get("after") or ["0"])[0]))
            except ValueError:
                return self.reply(400, {"error": "after"})
            lines = OUT.read_text(encoding="utf-8").splitlines() if OUT.exists() else []
            page = lines[after:after + 100]
            return self.reply(200, {"items": [json.loads(x) for x in page], "next": after + len(page), "total": len(lines)})
        return self.reply(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if urlsplit(self.path).path != "/run":
            return self.reply(404, {"error": "not found"})
        if not start("manual", self.body().get("includeMeta") is True):
            return self.reply(409, {"error": "Przebieg już trwa"})
        return self.reply(202, status())

    def do_PUT(self):  # noqa: N802
        if urlsplit(self.path).path != "/schedule":
            return self.reply(404, {"error": "not found"})
        b = self.body()
        with lock:
            sch = state["schedule"]
            if b.get("intervalMin") in INTERVALS:
                sch["intervalMin"] = b["intervalMin"]
            if isinstance(b.get("enabled"), bool):
                sch["enabled"] = b["enabled"]
            sch["nextRunAt"] = (datetime.now(timezone.utc) + timedelta(minutes=sch["intervalMin"])).isoformat(timespec="seconds").replace("+00:00", "Z") if sch["enabled"] else None
            save()
        return self.reply(200, status())

    def log_message(self, *_):
        return


def main() -> None:
    JOBS.mkdir(parents=True, exist_ok=True)
    if STATE.exists():
        state.update(json.loads(STATE.read_text(encoding="utf-8")))
    sch = state["schedule"]
    if sch["enabled"] and not sch.get("nextRunAt"):
        sch["nextRunAt"] = (datetime.now(timezone.utc) + timedelta(minutes=sch["intervalMin"])).isoformat(timespec="seconds").replace("+00:00", "Z")
    threading.Thread(target=scheduler, daemon=True).start()
    log("nasłuch na :8100")
    ThreadingHTTPServer(("0.0.0.0", 8100), Handler).serve_forever()  # noqa: S104 - tylko sieć Compose, port niepublikowany


if __name__ == "__main__":
    main()
