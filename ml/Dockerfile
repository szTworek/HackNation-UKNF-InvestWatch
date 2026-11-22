# ai-service (FastAPI, port 8000). Wersje zależności wyłącznie z uv.lock.
#
# Targety:
#   dev         – CPU, instalacja editable, kod montowany z hosta, uvicorn --reload (compose.dev.yaml)
#   runtime-gpu – torch CUDA 12.8 (compose.gpu.yaml)
#   runtime-cpu – domyślny, lekki obraz bez bibliotek NVIDIA
# Modele NIE są w obrazie: montowane do /app/models.
FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.9.22 /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/opt/venv VIRTUAL_ENV=/opt/venv \
    UV_HTTP_TIMEOUT=900 UV_HTTP_RETRIES=10 UV_CONCURRENT_DOWNLOADS=2 \
    PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 \
    INVESTWATCH_MODELS=/app/models HF_HOME=/cache/huggingface
WORKDIR /app
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN useradd --system --uid 10001 --create-home --home-dir /home/app app \
    && mkdir -p /app/models /cache/huggingface \
    && chown -R app:app /app/models /cache

FROM base AS deps-cpu
# Te same wersje co w uv.lock, tylko torch z indeksu CPU i bez pakietów CUDA.
RUN --mount=type=cache,target=/root/.cache/uv sh -eu -c '\
    uv export --frozen --no-dev --no-hashes --no-emit-project --no-annotate --no-header > /tmp/locked.txt; \
    torch_version=$(sed -n "s/^torch==\([^+]*\)+.*/\1/p" /tmp/locked.txt); \
    test -n "$torch_version"; \
    grep -vE "^(torch|triton|nvidia-|cuda-)" /tmp/locked.txt > /tmp/requirements.txt; \
    uv venv /opt/venv; \
    uv pip install --no-deps --index-url https://download.pytorch.org/whl/cpu "torch==${torch_version}+cpu"; \
    uv pip install --no-deps -r /tmp/requirements.txt; \
    rm /tmp/locked.txt /tmp/requirements.txt'

FROM base AS deps-gpu
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project

FROM deps-cpu AS dev
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv pip install --no-deps -e .
ENV WATCHFILES_FORCE_POLLING=true
USER app
EXPOSE 8000
CMD ["uvicorn", "investwatch_ml.api:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/src"]

FROM deps-gpu AS runtime-gpu
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv pip install --no-deps . && rm -rf ./src /usr/local/bin/uv
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=300s --retries=3 \
  CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["uvicorn", "investwatch_ml.api:app", "--host", "0.0.0.0", "--port", "8000"]

FROM deps-cpu AS runtime-cpu
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv pip install --no-deps . && rm -rf ./src /usr/local/bin/uv
USER app
EXPOSE 8000
# start-period: pierwszy start z modelem pobiera embedder BGE-M3 do wolumenu HF
HEALTHCHECK --interval=30s --timeout=5s --start-period=300s --retries=3 \
  CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["uvicorn", "investwatch_ml.api:app", "--host", "0.0.0.0", "--port", "8000"]
