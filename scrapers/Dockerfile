# Kolektory InvestWatch (Playwright + Chrome, yt-dlp, faster-whisper, RapidOCR).
# Build z katalogu głównego repo: docker build -f scrapers/Dockerfile -t investwatch-collector .
# Model Whispera nie jest w obrazie: pobiera go dopiero tryb filmowy workera (SCRAPE_VIDEOS=1) do /cache/huggingface.
# Domyślnie: python -m registry [kolektor] [zapytanie]. Sesje, klucze i wyniki są poza obrazem.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright HF_HOME=/cache/huggingface
# upgrade: poprawki bezpieczeństwa Debiana, których obraz bazowy jeszcze nie ma (skan Grype w CD blokuje high z poprawką)
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY scrapers/poc/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt faster-whisper==1.2.1 "psycopg[binary]==3.2.9" \
    && playwright install --with-deps chromium chrome \
    && rm -rf /var/lib/apt/lists/*

COPY adapters ./adapters
COPY preprocessing ./preprocessing
COPY scrapers ./scrapers
COPY scripts/convert_fb_ads_web.py ./scripts/convert_fb_ads_web.py
COPY ml/scripts/build_findings.py ./ml/scripts/build_findings.py
# loader (db/load.py) i zapis z workera: migracje, linkowanie podmiotów, rejestr KNF (data/ montuje compose)
COPY db ./db
COPY ml/src/investwatch_ml/knf_register.json ./ml/src/investwatch_ml/knf_register.json
# Chrome (crashpad) wymaga zapisywalnego katalogu domowego
RUN useradd --system --uid 10001 --create-home --home-dir /home/app app \
    && mkdir -p /app/scrapers/poc/results /app/.secrets /cache/huggingface /jobs \
    && chown -R app:app /app/scrapers/poc/results /cache /jobs

WORKDIR /app/scrapers/poc
USER app
ENTRYPOINT ["python", "-m", "registry"]
