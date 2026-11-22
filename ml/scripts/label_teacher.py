"""Etykietowanie puli dokumentów nauczycielem (Bielik w Ollamie).

Przykłady (z katalogu ml/):
  uv run python scripts/label_teacher.py --smoke                       # tylko 12 przykładów testowych
  uv run python scripts/label_teacher.py --wait --smoke --follow       # czekaj na model, test, potem pula w pętli
  uv run python scripts/label_teacher.py --source-cap youtube=800,reddit=600

Wejście: data/pool/*.jsonl (format investwatch_ml.schema.Doc), wyjście: data/silver/teacher.jsonl.
Wznawialne: pomija dokumenty już oznaczone tą samą wersją promptu.
"""

from __future__ import annotations

import argparse
import glob
import json
import random
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

from investwatch_ml.schema import Doc, append_jsonl, read_jsonl
from investwatch_ml.smoke import smoke_docs
from investwatch_ml.teacher import DEFAULT_HOST, DEFAULT_MODEL, PROMPT_VERSION, GeminiTeacher, GroqTeacher, OpenRouterTeacher, Teacher, wait_for_model

ML_DIR = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)  # konsola Windows


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def parse_caps(s: str | None) -> dict[str, int]:
    caps: dict[str, int] = {}
    for part in (s or "").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            caps[k.strip()] = int(v)
    return caps


def labeled_state(out_path: Path) -> tuple[set[str], Counter]:
    done: set[str] = set()
    per_source: Counter = Counter()
    for r in read_jsonl(out_path):
        if r.get("prompt_version") == PROMPT_VERSION and r.get("id"):
            done.add(str(r["id"]))
            per_source[r.get("source", "?")] += 1
    return done, per_source


def load_pending(patterns: list[str], done: set[str], skip: set[str], caps: dict[str, int],
                 per_source: Counter) -> list[Doc]:
    docs: dict[str, Doc] = {}
    for pat in patterns:
        p = Path(pat)
        full = str(p if p.is_absolute() else ML_DIR / p)
        for path in sorted(glob.glob(full)):
            for row in read_jsonl(path):
                rid = str(row.get("id", ""))
                if not rid or rid in done or rid in skip or rid in docs:
                    continue
                try:
                    docs[rid] = Doc(**row)
                except Exception:
                    continue
    items = list(docs.values())
    random.Random(42).shuffle(items)  # przeplot źródeł i zapytań
    if caps:
        budget = {s: caps[s] - per_source.get(s, 0) for s in caps}
        kept = []
        for d in items:
            if d.source in budget:
                if budget[d.source] <= 0:
                    continue
                budget[d.source] -= 1
            kept.append(d)
        items = kept
    # przeplot źródeł (round-robin), żeby rzadkie źródła (scamy) nie czekały za tysiącami postów z Reddita
    by_src: dict[str, list[Doc]] = {}
    for d in items:
        by_src.setdefault(d.source, []).append(d)
    mixed: list[Doc] = []
    while any(by_src.values()):
        for src in list(by_src):
            if by_src[src]:
                mixed.append(by_src[src].pop())
    return mixed


def show_gpu_residency(host: str) -> None:
    try:
        ps = httpx.get(f"{host}/api/ps", timeout=5).json().get("models", [])
        for m in ps:
            size, vram = m.get("size", 0), m.get("size_vram", 0)
            pct = 100 * vram / size if size else 0
            log(f"[ollama] {m.get('name')}: {size / 2**30:.1f} GB, na GPU {pct:.0f}%"
                + ("" if pct > 99 else "  <-- część na CPU, będzie wolno (zmniejsz --num-ctx)"))
    except Exception as ex:
        log(f"[ollama] /api/ps niedostępne: {ex}")


def run_smoke(teacher: Teacher, out_dir: Path) -> None:
    log(f"[smoke] {len(smoke_docs())} przykładów, prompt {PROMPT_VERSION}")
    rows, ok = [], Counter()
    for doc, exp in smoke_docs():
        try:
            r = teacher.label_doc(doc)
        except Exception as ex:
            log(f"[smoke] {doc.id}: BŁĄD {ex}")
            continue
        lb = r["label"]
        hits = {k: lb[k] == exp[k] for k in ("topic", "content_type", "is_scam")}
        ok.update(k for k, v in hits.items() if v)
        flags = ",".join(sorted({f["flag"] for f in lb["flags"]}))
        unaligned = sum(1 for f in lb["flags"] if f["start"] is None)
        mark = lambda k: "✓" if hits[k] else f"✗(oczek. {exp[k]})"  # noqa: E731
        log(f"[smoke] {doc.id:34s} {r['stats']['wall_seconds']:5.1f}s | topic {lb['topic']} {mark('topic')} | "
            f"type {lb['content_type']} {mark('content_type')} | scam {lb['is_scam']}/{lb['scam_confidence']} "
            f"{mark('is_scam')}\n           flagi: {flags or '-'}" + (f"  (niedopasowane cytaty: {unaligned})" if unaligned else "")
            + f"\n           uzasadnienie: {lb['rationale'][:220]}")
        rows.append({**r, "source": "smoke", "expected": exp})
    n = len(rows) or 1
    log(f"[smoke] zgodność: topic {ok['topic']}/{n}, content_type {ok['content_type']}/{n}, is_scam {ok['is_scam']}/{n}")
    out = out_dir / f"smoke_{PROMPT_VERSION}.jsonl"
    out.unlink(missing_ok=True)
    append_jsonl(out, rows)
    log(f"[smoke] zapisano {out}")


def label_docs(teacher: Teacher, docs: list[Doc], out_path: Path, err_path: Path, workers: int,
               failed: set[str]) -> int:
    t0, n_ok, n_err = time.time(), 0, 0
    tokens = Counter()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(teacher.label_doc, d): d for d in docs}
        for i, fut in enumerate(as_completed(futs), start=1):
            d = futs[fut]
            try:
                res = fut.result()
                res["source"] = d.source
                append_jsonl(out_path, [res])
                n_ok += 1
                tokens.update({"in": res["stats"]["prompt_tokens"], "out": res["stats"]["output_tokens"]})
            except Exception as e:
                n_err += 1
                failed.add(d.id)
                append_jsonl(err_path, [{"id": d.id, "source": d.source, "error": str(e)[:500],
                                         "prompt_version": PROMPT_VERSION, "at": time.strftime("%H:%M:%S")}])
            if i % 10 == 0 or i == len(docs):
                el = time.time() - t0
                rate = i / el if el else 0
                eta = (len(docs) - i) / rate / 60 if rate else 0
                log(f"[label] {i}/{len(docs)} (ok {n_ok}, błędy {n_err}) | {rate * 60:.1f} dok/min | "
                    f"ETA {eta:.0f} min | śr. tokeny in/out {tokens['in'] / max(n_ok, 1):.0f}/{tokens['out'] / max(n_ok, 1):.0f}")
    return n_ok


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", nargs="*", default=["data/pool/*.jsonl"])
    ap.add_argument("--output", default="data/silver/teacher.jsonl")
    ap.add_argument("--backend", choices=["ollama", "gemini", "groq", "openrouter"], default="ollama")
    ap.add_argument("--model", default=None, help="domyślnie Bielik (ollama) / gemini-3.5-flash-lite")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--workers", type=int, default=2, help="równoległe zapytania (ustaw OLLAMA_NUM_PARALLEL >= tyle)")
    ap.add_argument("--num-ctx", type=int, default=6144)
    ap.add_argument("--chunk-chars", type=int, default=6000)
    ap.add_argument("--max-doc-chars", type=int, default=12000)
    ap.add_argument("--source-cap", default=None, help="np. youtube=800,reddit=600")
    ap.add_argument("--limit", type=int, default=None, help="maks. dokumentów w tym uruchomieniu")
    ap.add_argument("--wait", action="store_true", help="czekaj, aż Ollama i model będą dostępne")
    ap.add_argument("--smoke", action="store_true", help="najpierw 12 przykładów testowych")
    ap.add_argument("--smoke-only", action="store_true")
    ap.add_argument("--follow", action="store_true", help="po skończeniu puli czekaj na nowe dokumenty")
    ap.add_argument("--poll", type=int, default=60)
    args = ap.parse_args()

    out_path = ML_DIR / args.output
    err_path = out_path.with_name(out_path.stem + "_errors.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if args.backend == "openrouter":
        args.model = args.model or OpenRouterTeacher.DEFAULT
        teacher = OpenRouterTeacher(model=args.model)
        args.wait = False
    elif args.backend == "groq":
        args.model = args.model or "llama-3.3-70b-versatile"
        teacher = GroqTeacher(model=args.model)
        args.wait = False
    elif args.backend == "gemini":
        args.model = args.model or "gemini-3.5-flash-lite"
        teacher = GeminiTeacher(model=args.model)
        args.wait = False
    else:
        args.model = args.model or DEFAULT_MODEL
        teacher = Teacher(model=args.model, host=args.host, num_ctx=args.num_ctx, chunk_chars=args.chunk_chars,
                          max_doc_chars=args.max_doc_chars)
    log(f"[teacher] model {args.model} | prompt {PROMPT_VERSION} | num_ctx {args.num_ctx} | workers {args.workers}")

    if args.wait:
        wait_for_model(args.model, args.host, log=log)
    if args.backend == "ollama":
        log(f"[teacher] ładowanie modelu na GPU... ({teacher.warmup():.1f}s)")
        show_gpu_residency(args.host)

    if args.smoke or args.smoke_only:
        run_smoke(teacher, out_path.parent)
        if args.smoke_only:
            return

    caps = parse_caps(args.source_cap)
    failed: set[str] = set()
    total = 0
    announced_idle = False
    while True:
        done, per_source = labeled_state(out_path)
        pending = load_pending(args.input, done, failed, caps, per_source)
        if args.limit is not None:
            pending = pending[: max(args.limit - total, 0)]
        pending = pending[:60]  # małe porcje – nowe dokumenty z kolektorów wchodzą do przeplotu na bieżąco
        if pending:
            announced_idle = False
            log(f"[label] do oznaczenia: {len(pending)} | już oznaczone: {dict(per_source)}")
            total += label_docs(teacher, pending, out_path, err_path, args.workers, failed)
            if args.limit is not None and total >= args.limit:
                break
            continue
        if not args.follow:
            break
        if not announced_idle:
            log(f"[label] pula pusta – czekam na nowe dokumenty w {args.input} (co {args.poll}s)")
            announced_idle = True
        time.sleep(args.poll)
    done, per_source = labeled_state(out_path)
    log(f"[label] koniec. Oznaczone łącznie: {dict(per_source)} -> {out_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("[label] przerwane – wznowisz tym samym poleceniem")
        sys.exit(130)
    except Exception as e:  # czytelny błąd zamiast traceback'u w logu w tle
        log(f"[label] BŁĄD: {type(e).__name__}: {json.dumps(str(e), ensure_ascii=False)[:500]}")
        raise
