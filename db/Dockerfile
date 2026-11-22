# Loader (db/load.py): migracje, rejestr KNF, podmioty, rekordy z data/ i oceny ai-service -> Postgres.
# Build z katalogu głównego repo: docker build -f db/Dockerfile -t investwatch-loader .
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir "psycopg[binary]==3.2.9" \
    && useradd --system --uid 10001 app
WORKDIR /app
COPY db ./db
COPY ml/scripts/build_findings.py ./ml/scripts/build_findings.py
COPY ml/src/investwatch_ml/knf_register.json ./ml/src/investwatch_ml/knf_register.json
USER app
# data/ montuje compose (tylko do odczytu)
ENTRYPOINT ["python", "/app/db/load.py"]
