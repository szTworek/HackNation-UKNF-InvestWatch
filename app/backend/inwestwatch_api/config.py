import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "data"
EXPORT_DIR = DATA / "export"
SAMPLES_DIR = DATA / "samples"
MONITOR_DIR = DATA / "monitor"
KNF_FILE = Path(os.environ.get("KNF_FILE", REPO.parent / "data" / "knf_entities.json"))

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{(DATA / 'app.db').as_posix()}")
SCAN_INTERVAL_MIN = int(os.environ.get("SCAN_INTERVAL_MIN", "60"))
SCAN_ON_STARTUP = os.environ.get("SCAN_ON_STARTUP", "1") == "1"
MOCK_HISTORY = os.environ.get("MOCK_HISTORY", "1") == "1"
