# Monorepo Restructure

## Overview

Move `apps/web` → `frontend/` and `apps/api` → `backend/` at the monorepo root; keep Turborepo + pnpm working.

## Files to Modify/Create

- `apps/web/` → `frontend/` — `git mv apps/web frontend`
- `apps/api/` → `backend/` — `git mv apps/api backend`
- `pnpm-workspace.yaml` — `packages: ["frontend", "backend"]`
- `turbo.json` — build task `outputs`: `["frontend/.next/**", "!.next/cache/**"]`
- `frontend/package.json` — name `@blinka/web` (scripts unchanged)
- `backend/package.json` — name `@blinka/backend`; scripts:
  - `dev`: `uv run uvicorn api.app:app --reload --port 8000`
  - `build`: `uv sync`
  - `lint`: `uv run ruff check . && uv run ruff format --check .`
  - `format`: `uv run ruff format . && uv run ruff check --fix .`
- `backend/app/` — DELETE (old stub `app/main.py`; the new structure is built by 02-backend-skeleton)
- Root `package.json` — unchanged scripts (`turbo run dev/build/lint`)

## Implementation Guidelines

1. Use `git mv` (preserves history). Run moves before editing configs.
2. `backend/.python-version` stays `3.13`. Regenerate `uv.lock` after pyproject changes in 02-backend-skeleton (`uv lock`, `uv sync`).
3. Do not touch any file inside `frontend/src/`.

## Dependencies

None (first task).

## Integration Notes

After this task: `pnpm install && pnpm dev` starts Next on :3000; backend dev script will fail until 02-backend-skeleton exists — acceptable intermediate state within the same implementation pass.
