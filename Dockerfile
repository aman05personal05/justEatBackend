# ── Stage 1: Builder ─────────────────────────────────────────────────────────
# Full Python image with build tools — compiles C extensions (asyncpg, bcrypt).
FROM python:3.12-slim AS builder

WORKDIR /build

# Build-time deps: gcc + libpq headers required to compile asyncpg & psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install all packages into an isolated prefix so the runtime stage can
# COPY them cleanly without carrying any build toolchain along.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
# Lean production image — no compiler, no headers.
# Only libpq5 (shared library) is needed at run-time by asyncpg / psycopg2.
FROM python:3.12-slim AS runtime

# Prevent Python from buffering stdout/stderr (important for container logs)
# and from writing .pyc files (keeps container filesystem clean).
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Runtime-only system dep
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-built Python packages from the builder stage
COPY --from=builder /install /usr/local

# Copy application source (respects .dockerignore — excludes venv, tests, .env)
COPY . .

# Create and switch to a non-root user BEFORE the EXPOSE / CMD
# so the container never runs as root in production.
RUN adduser --disabled-password --gecos "" appuser \
 && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# 1. Apply any pending Alembic migrations (idempotent — safe on repeat starts)
# 2. Start Uvicorn with 2 workers
#    Use --workers 1 if the DATABASE_URL points to a connection-pooler (e.g. PgBouncer)
CMD ["/bin/sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"]
