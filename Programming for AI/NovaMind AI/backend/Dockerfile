# backend/Dockerfile

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System dependencies needed to build asyncpg/bcrypt wheels and provide a
# healthcheck client. Removed from the final layer's apt cache afterward
# to keep the image small.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Dependencies are copied and installed before application code so Docker's
# layer cache is reused on every rebuild that only changes app/ source —
# avoids reinstalling all packages on every code change.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Non-root user for the actual application process
RUN groupadd --gid 1000 novamind \
    && useradd --uid 1000 --gid novamind --shell /bin/bash --create-home novamind

COPY --chown=novamind:novamind . .

USER novamind

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]