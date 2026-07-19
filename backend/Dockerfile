# ─── Stage 1: Base ───
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    tesseract-ocr-chi-tra \
    && rm -rf /var/lib/apt/lists/*

# ─── Stage 2: Dependencies ───
FROM base AS deps

COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[prod]"

# ─── Stage 3: Runtime ───
FROM deps AS runtime

COPY app/ ./app/
COPY scripts/ ./scripts/
RUN mkdir -p /app/data

EXPOSE 7800

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:7800/api/v1/health', timeout=5)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7800", "--workers", "2"]
