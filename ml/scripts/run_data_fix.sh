#!/usr/bin/env bash
# Czeka na koniec automatu w starym repo, synchronizuje dane, naprawia etykiety i porównuje model przed i po.
cd "$(dirname "$0")/.." || exit 1
A="../../UKNF/ml"
PY="$A/.venv/Scripts/python"
LOG=logs/data_fix.log
export PYTHONUTF8=1 PYTHONPATH=src HF_HUB_DISABLE_PROGRESS_BARS=1
say() { echo "$(date +%H:%M:%S) $*" >> "$LOG"; }

say "czekam na koniec automatu"
for _ in $(seq 1 240); do
  grep -q " koniec$" "$A/logs/autopilot.log" && break
  "$PY" -c "import time; time.sleep(30)"
done
say "autopilot: $(grep -E 'trening: exit' "$A/logs/autopilot.log" | tail -n 1)"
for d in pool silver gold; do cp -ru "$A/data/$d/." "data/$d/"; done
say "naprawa etykiet"
"$PY" scripts/curate_labels.py >> "$LOG" 2>&1 || { say "BLAD: curate"; exit 1; }
say "trening: etykiety oryginalne"
"$PY" scripts/train_heads.py --no-edge --out models_candidate/base_noedge > logs/train_base_noedge.log 2>&1 || { say "BLAD: trening base"; exit 1; }
say "trening: etykiety naprawione"
"$PY" scripts/train_heads.py --no-edge --curated data/curated/labels.jsonl --out models_candidate/curated_noedge > logs/train_curated_noedge.log 2>&1 || { say "BLAD: trening curated"; exit 1; }
say "porownanie"
"$PY" scripts/eval_edge.py models_candidate/base_noedge models_candidate/curated_noedge >> "$LOG" 2>&1 || { say "BLAD: ocena"; exit 1; }
say "koniec"
