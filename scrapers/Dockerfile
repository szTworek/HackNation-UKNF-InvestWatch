# Kolektory InvestWatch (Playwright + Chrome, yt-dlp, faster-whisper, RapidOCR).
# Build z katalogu głównego repo: docker build -f scrapers/Dockerfile -t investwatch-collector .
# Domyślnie: python -m registry [kolektor] [zapytanie]. Sesje, klucze i wyniki są poza obrazem.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright HF_HOME=/cache/huggingface
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY scrapers/poc/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt faster-whisper==1.2.1 \
    && playwright install --with-deps chromium chrome \
    && rm -rf /var/lib/apt/lists/*

COPY adapters ./adapters
COPY preprocessing ./preprocessing
COPY scrapers ./scrapers
# Chrome (crashpad) wymaga zapisywalnego katalogu domowego
RUN useradd --system --uid 10001 --create-home --home-dir /home/app app \
    && mkdir -p /app/scrapers/poc/results /app/.secrets /cache/huggingface \
    && chown -R app:app /app/scrapers/poc/results /cache

WORKDIR /app/scrapers/poc
USER app
ENTRYPOINT ["python", "-m", "registry"]
