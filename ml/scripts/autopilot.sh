#!/usr/bin/env bash
# Praca bez nadzoru: tłumaczenie lokalne -> czas na etykietowanie -> kopia modelu -> trening. Log: logs/autopilot.log
cd "$(dirname "$0")/.." || exit 1
export PYTHONUTF8=1 HF_HUB_DISABLE_PROGRESS_BARS=1
LOG=logs/autopilot.log
say() { echo "$(date +%H:%M:%S) $*" >> "$LOG"; }

say "start: tlumaczenie"
uv run --no-sync python scripts/translate_local.py >> logs/translate_local.log 2>&1
say "tlumaczenie: exit $?"
uv run --no-sync python scripts/ingest_scraper.py --export data/raw/scraper_live >> "$LOG" 2>&1

say "czekam 90 min na etykiety"
.venv/Scripts/python -c "import time; time.sleep(5400)"

backup="models_backup_$(date +%H%M)"
[ -f models/heads.joblib ] && cp -r models "$backup" && say "kopia modelu: $backup"
say "start: trening"
uv run --no-sync python scripts/train_heads.py >> logs/train_heads.log 2>&1
say "trening: exit $?"
grep -E "dokumenty z etykietami|train .* test|topic macro|content_type macro|scam: model" logs/train_heads.log | tail -n 5 >> "$LOG"
say "koniec"
