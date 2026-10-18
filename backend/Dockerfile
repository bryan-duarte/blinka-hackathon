FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN useradd --system --create-home --uid 10001 app

WORKDIR /code

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY container.py ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY api ./api
COPY clients ./clients
COPY contracts ./contracts
COPY core ./core
COPY modules ./modules
COPY scripts ./scripts
COPY docker-entrypoint.sh ./

USER app

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
