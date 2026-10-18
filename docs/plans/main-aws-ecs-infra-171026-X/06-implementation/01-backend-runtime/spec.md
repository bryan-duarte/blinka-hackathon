# Backend Runtime Implementation

## Overview

These changes make the existing image run on Fargate. Boto3 uses the task role's credentials. The container creates any missing databases and migrates them before uvicorn starts, and its keep-alive outlasts the ALB idle timeout.

## Files to Modify/Create

- `backend/core/config.py`: in `StorageSettings.aws_profile` (line 39), `TextractSettings.aws_profile` (line 50) and `RealtimeSettings.aws_profile` (line 116), change the default from `"panoptico"` to `None`. Change nothing else.
- `backend/core/db/bootstrap.py` (new): defines `ensure_databases(dsns: list[str]) -> None` and a `__main__` block that reads `BLINKA_PRODUCT_DATABASE_URL` and `BLINKA_PAYMENTS_DATABASE_URL` from `os.environ`.
- `backend/docker-entrypoint.sh` (new, `chmod +x`): runs the bootstrap, then both migrations, then starts uvicorn.
- `backend/Dockerfile`: `COPY docker-entrypoint.sh ./`, then replace `CMD [...]` with `ENTRYPOINT ["./docker-entrypoint.sh"]`.

## Implementation Guidelines

### `core/db/bootstrap.py` (orientative)
```python
import os

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

DATABASE_URL_VARS = ("BLINKA_PRODUCT_DATABASE_URL", "BLINKA_PAYMENTS_DATABASE_URL")


def ensure_databases(dsns: list[str]) -> None:
    for dsn in dsns:
        name = conninfo_to_dict(dsn)["dbname"]
        with psycopg.connect(make_conninfo(dsn, dbname="postgres"), autocommit=True) as conn:
            exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone()
            if not exists:
                conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    ensure_databases([os.environ[var] for var in DATABASE_URL_VARS])
```
- The DSNs arrive as plain `postgresql://...?sslmode=require`, and psycopg's `conninfo_to_dict` parses URLs directly. If the URL carries a `+psycopg` scheme suffix, strip it first, the same way `alembic/env.py:_sync_url` does. The values from SSM won't have one.
- `CREATE DATABASE` cannot run inside a transaction, which is why the connection uses `autocommit=True`.
- RDS master user `blinka` has `CREATEDB`, so this works on RDS. Locally, compose has already created both databases, so the script does nothing.

### `docker-entrypoint.sh` (orientative)
```bash
#!/usr/bin/env sh
set -eu

uv run --no-sync python -m core.db.bootstrap
uv run --no-sync alembic -n product upgrade head
uv run --no-sync alembic -n payments upgrade head

exec uv run --no-sync uvicorn api.app:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 130
```
- Use `sh`, not bash: `python:3.13-slim` has bash, but the script needs nothing beyond POSIX.
- `exec` makes uvicorn PID 1, so it receives ECS's SIGTERM and the lifespan shutdown runs, cancelling the registries.

### Dockerfile diff (orientative)
```diff
 COPY modules ./modules
+COPY docker-entrypoint.sh ./

 USER app

 EXPOSE 8000

-CMD ["uv", "run", "--no-sync", "uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
+ENTRYPOINT ["./docker-entrypoint.sh"]
```
- Make sure the file is executable in git (`git update-index --chmod=+x backend/docker-entrypoint.sh`), or add `RUN chmod +x` before `USER app`.

## Dependencies

- psycopg 3.3.6, which is already locked. No new packages.

## Integration Notes

- ECS injects both `BLINKA_*_DATABASE_URL` values as env vars (module 05). `alembic/env.py` reads them through `os.getenv`, with no change.
- Because `*_AWS_PROFILE` is absent on ECS, every `aioboto3.Session(profile_name=None)` falls back to the container credentials provider, which uses the task role from module 06.
- `docker-compose.yml` needs no change. Its `backend` service now auto-migrates on start.
