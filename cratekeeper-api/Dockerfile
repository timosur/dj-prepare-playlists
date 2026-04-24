FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY cratekeeper_api ./cratekeeper_api
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

# Install the project + the sibling cratekeeper-cli (path dep) lives outside —
# in compose we mount it. For local builds, install api deps only.
RUN uv pip install --system .

ENV PYTHONUNBUFFERED=1 \
    CRATEKEEPER_HOST=0.0.0.0 \
    CRATEKEEPER_PORT=8765

EXPOSE 8765

CMD ["sh", "-c", "alembic upgrade head && uvicorn cratekeeper_api.main:app --host $CRATEKEEPER_HOST --port $CRATEKEEPER_PORT"]
