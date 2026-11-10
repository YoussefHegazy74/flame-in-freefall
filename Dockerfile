# syntax=docker/dockerfile:1
#
# Production image for the read-only FastAPI service.
#
# Canonical Parquet data and the generated retrieval index are not baked into
# this image. Mount them read-only at runtime:
#   /app/data/processed
#   /app/data/assistant
#
# Raw NASA files are never copied into the image.

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements-prod.txt ./
RUN python -m pip install --no-cache-dir -r requirements-prod.txt

COPY backend ./backend
COPY src ./src
COPY scripts ./scripts

# Committed metadata, registries, reports, and documentation are required for
# the API and for an in-memory retrieval-index rebuild if the mounted artifact
# is absent.
COPY DATA_DICTIONARY.md DATA_SOURCES.md PROJECT_ARCHITECTURE.md API_DOCUMENTATION.md ./
COPY docs ./docs
COPY data/registry ./data/registry
COPY data/metadata ./data/metadata
COPY data/reports ./data/reports
COPY data/fixtures ./data/fixtures

# The volume mount points exist even when the host directory is absent.
RUN mkdir -p /app/data/processed /app/data/assistant \
    && groupadd --system --gid 1001 appuser \
    && useradd --system --uid 1001 --gid appuser appuser \
    && chown -R appuser:appuser /app

USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)"]

CMD ["python", "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
