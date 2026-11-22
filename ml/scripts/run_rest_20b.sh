#!/usr/bin/env bash
# Rekordy z zipów bez oceny LLM -> gpt-oss-20b (oba klucze Groq) -> dane frontu -> baza -> restart API.
cd "$(dirname "$0")/../.." || exit 1
PY="../UKNF/ml/.venv/Scripts/python"
LOG=ml/logs/rest_20b.log
OUT=ml/data/skill/zip_rest_groq20b.jsonl
export PYTHONUTF8=1
"$PY" -I - >> "$LOG" 2>&1 <<'EOF'
import json, zipfile
done = {f["url"] for f in json.load(open("frontend/mock-server/data/findings.real.json", encoding="utf-8"))["findings"] if "llm" in f}
todo = {f["url"] for f in json.load(open("frontend/mock-server/data/findings.real.json", encoding="utf-8"))["findings"] if "llm" not in f}
rows = {}
for z in ("data/investwatch_samples_20261121.zip", "../UKNF/investwatch_samples_20261121.zip"):
    with zipfile.ZipFile(z) as a:
        for n in a.namelist():
            parts = n.replace(chr(92), "/").split("/")
            if parts[-1] == "records.jsonl" and "raw" not in parts:
                for line in a.read(n).decode("utf-8").splitlines():
                    if line.strip():
                        r = json.loads(line)
                        if r.get("source_url") in todo:
                            rows.setdefault(r["source_url"], r)
open("ml/data/skill/zip_rest.jsonl", "w", encoding="utf-8").writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows.values())
print("do oceny:", len(rows), "z", len(todo))
EOF
for key in GROQ_API_KEY_2 GROQ_API_KEY; do
  GROQ_KEY_NAME=$key "$PY" -I ml/scripts/classify_groq.py --input ml/data/skill/zip_rest.jsonl --model openai/gpt-oss-20b \
    --max-chars 1200 --out "$OUT" >> "$LOG" 2>&1
done
"$PY" -I ml/scripts/merge_llm.py --llm "$OUT" --export "ml/data/raw/scraper_live/__brak__*" >> "$LOG" 2>&1
"$PY" -I ml/scripts/build_db.py >> "$LOG" 2>&1
docker compose up -d --no-deps --force-recreate api >> "$LOG" 2>&1
echo "KONIEC $(date +%H:%M:%S)" >> "$LOG"
