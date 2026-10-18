#!/usr/bin/env sh
set -eu

uv run --no-sync python -m core.db.bootstrap
uv run --no-sync alembic -n product upgrade head
uv run --no-sync alembic -n payments upgrade head

# Keep-alive must outlast the ALB idle timeout (120s in infra/edge.tf) or the ALB gets 502s.
exec uv run --no-sync uvicorn api.app:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 130
