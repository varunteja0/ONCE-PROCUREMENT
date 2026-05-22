# syntax=docker/dockerfile:1.7
# Once backend image. Multi-stage. Python 3.12 slim bookworm. Non-root runtime user.
# Playwright Chromium is always installed because BaseSubmitter relies on
# sync Playwright bridged via asyncio.to_thread; the same image is used for
# the web / worker / beat process groups on Fly.

ARG PYTHON_VERSION=3.12-slim-bookworm

############################
# Stage 1: builder — compile wheels into an isolated prefix
############################
FROM python:${PYTHON_VERSION} AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Cache-friendly: requirements first, source later.
COPY requirements.txt ./
RUN pip install --prefix=/install --upgrade pip setuptools wheel \
    && pip install --prefix=/install --no-cache-dir -r requirements.txt

############################
# Stage 2: runtime
############################
FROM python:${PYTHON_VERSION} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Runtime system deps: libpq for asyncpg/psycopg, curl for healthchecks,
# tini for proper PID 1 signal handling, ca-certificates for TLS.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
        tini \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Bring in the prebuilt Python packages.
COPY --from=builder /install /usr/local

WORKDIR /app

# Install Playwright Chromium + its system dependencies into a shared path
# BEFORE copying app source so the (large, slow) layer caches across rebuilds.
RUN mkdir -p "${PLAYWRIGHT_BROWSERS_PATH}" \
    && playwright install --with-deps chromium \
    && chmod -R a+rX "${PLAYWRIGHT_BROWSERS_PATH}"

# App source — copy only what the runtime needs (kept tight via .dockerignore).
COPY app /app/app
COPY alembic /app/alembic
COPY alembic.ini /app/
COPY entrypoint.sh /app/

# Non-root user.
RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --home-dir /app --shell /usr/sbin/nologin app \
    && chmod +x /app/entrypoint.sh \
    && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/v1/health" || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "./entrypoint.sh"]
CMD ["api"]
