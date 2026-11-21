# ai-service (FastAPI, port 8000). Wersje zależności wyłącznie z uv.lock (torch CUDA 12.8).
#
# Targety:
#   dev        – instalacja editable, kod montowany z hosta, uvicorn --reload (compose.dev.yaml)
#   (domyślny) – obraz produkcyjny. Modele NIE są w obrazie: montowane do /app/models.
FROM python:3.12-slim AS deps
COPY --from=ghcr.io/astral-sh/uv:0.9.22 /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_HTTP_TIMEOUT=900 UV_HTTP_RETRIES=10 UV_CONCURRENT_DOWNLOADS=2 \
    PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 \
    INVESTWATCH_MODELS=/app/models HF_HOME=/cache/huggingface
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
RUN useradd --system --uid 10001 --home-dir /app app \
    && mkdir -p /app/models /cache/huggingface \
    && chown -R app:app /app/models /cache

FROM deps AS dev
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev
ENV WATCHFILES_FORCE_POLLING=true
USER app
EXPOSE 8000
CMD ["uvicorn", "investwatch_ml.api:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/src"]

FROM deps AS runtime
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-editable && rm -rf ./src /usr/local/bin/uv
USER app
EXPOSE 8000
# start-period: pierwszy start z modelem pobiera embedder BGE-M3 do wolumenu HF
HEALTHCHECK --interval=30s --timeout=5s --start-period=300s --retries=3 \
  CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["uvicorn", "investwatch_ml.api:app", "--host", "0.0.0.0", "--port", "8000"]
