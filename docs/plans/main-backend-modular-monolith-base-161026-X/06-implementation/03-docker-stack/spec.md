# Docker Stack

## Overview

`backend/Dockerfile` + root `docker-compose.yml`: 3 PostgreSQL, MinIO, backend. `docker compose up --build` = full local stack.

## Files to Create

- `backend/.dockerignore`: `.venv/`, `.env`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `tests/`
- `backend/Dockerfile` (mirror the reference, Python 3.13):

```dockerfile
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN useradd --system --create-home --uid 10001 app
WORKDIR /code
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY alembic.ini ./
COPY alembic ./alembic
COPY api ./api
COPY clients ./clients
COPY contracts ./contracts
COPY core ./core
COPY modules ./modules
USER app
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

Alembic is copied so `docker compose exec backend uv run --no-sync alembic -n product upgrade head` works inside the container.

- `docker-compose.yml` (root):

```yaml
services:
  postgres-product:   # PG-1
    image: postgres:17-alpine
    environment: {POSTGRES_USER: blinka, POSTGRES_PASSWORD: blinka, POSTGRES_DB: blinka_product}
    ports: ["5432:5432"]
    volumes: [product-data:/var/lib/postgresql/data]
    healthcheck: {test: ["CMD-SHELL", "pg_isready -U blinka -d blinka_product"], interval: 5s, retries: 10}
  postgres-agent:     # PG-2 — main agent checkpoints
    image: postgres:17-alpine
    environment: {POSTGRES_USER: blinka, POSTGRES_PASSWORD: blinka, POSTGRES_DB: blinka_agent}
    ports: ["5433:5432"]
    volumes: [agent-data:/var/lib/postgresql/data]
    healthcheck: {test: ["CMD-SHELL", "pg_isready -U blinka -d blinka_agent"], interval: 5s, retries: 10}
  postgres-payments:  # PG-3
    image: postgres:17-alpine
    environment: {POSTGRES_USER: blinka, POSTGRES_PASSWORD: blinka, POSTGRES_DB: blinka_payments}
    ports: ["5434:5432"]
    volumes: [payments-data:/var/lib/postgresql/data]
    healthcheck: {test: ["CMD-SHELL", "pg_isready -U blinka -d blinka_payments"], interval: 5s, retries: 10}
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment: {MINIO_ROOT_USER: minioadmin, MINIO_ROOT_PASSWORD: minioadmin}
    ports: ["9000:9000", "9001:9001"]
    volumes: [minio-data:/data]
    healthcheck: {test: ["CMD", "mc", "ready", "local"], interval: 5s, retries: 10}
  backend:
    build: ./backend
    env_file: ./backend/.env
    environment:
      BLINKA_PRODUCT_DATABASE_URL: postgresql://blinka:blinka@postgres-product:5432/blinka_product
      BLINKA_AGENT_DATABASE_URL: postgresql://blinka:blinka@postgres-agent:5432/blinka_agent
      BLINKA_PAYMENTS_DATABASE_URL: postgresql://blinka:blinka@postgres-payments:5432/blinka_payments
      BLINKA_STORAGE__ENDPOINT_URL: http://minio:9000
    ports: ["8000:8000"]
    depends_on:
      postgres-product: {condition: service_healthy}
      postgres-agent: {condition: service_healthy}
      postgres-payments: {condition: service_healthy}
      minio: {condition: service_healthy}
volumes: {product-data: {}, agent-data: {}, payments-data: {}, minio-data: {}}
```

## Implementation Guidelines

- DB URLs must be overridable: `.env` carries `localhost` host + ports 5432/5433/5434 for host-run dev; compose injects service names. `backend/.env.example` documents the localhost variants.
- Don't run migrations automatically in CMD — run them manually (`just`/README command) or as a one-off `docker compose exec` step; keeps startup deterministic.
- MinIO bucket bootstrap happens app-side (FilesService at startup), not via a extra container.

## Dependencies

01-monorepo-restructure (paths), 02-backend-skeleton (pyproject/uv.lock for the image).

## Integration Notes

Service DNS names `postgres-product`, `postgres-agent`, `postgres-payments`, `minio` are the in-compose hostnames; `localhost:5432/5433/5434`, `localhost:9000` are the host ones. Both must work from the same `.env` templating.
