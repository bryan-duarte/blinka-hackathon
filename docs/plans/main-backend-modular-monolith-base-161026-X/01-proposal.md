# Backend Modular Monolith Base — Blinka

> "Let's build the cathedral. The stain glass comes in phase two."
> - El Barto

## Overview

**Request**: Bootstrap the backend of the blinka-hackathon monorepo as a Python **modular monolith**: folder structure, Dockerfile, docker-compose for local dev, and the first runnable vertical slice (auth, chat agent, background payment agent, file upload) — general structure only, no deep business logic yet.

**Created**: 2026-10-16

## What

- Restructure the monorepo root from `apps/web` + `apps/api` to **`frontend/` + `backend/`**.
- Build the backend as a modular monolith following the reference pattern (`hackathon-anonymous-oct`): top-level-by-role layering — `api/`, `contracts/`, `clients/`, `core/`, `modules/` — directly inside `backend/` (no extra brand package layer).
- Modules (one folder each, facade `__init__.py` + `service.py`): `auth`, `files`, `invoice_ingestor`, `guardrails` (stub), `llm_gateway`, `mcp_gateway` (skeleton), `prompts`, `tools` (skeleton), `sessions`, `orchestrator`, `payments`.
- Local infra via docker-compose: **3 PostgreSQL instances** + **MinIO (S3-compatible)** + the **backend** container.
- First vertical slice: JWT auth → file upload → chat (JSON + SSE streaming) with a DeepAgents main agent → `initiate_payments` tool → background payment-agent runs with polling.

## Why

The repo currently has only a `/health` FastAPI stub. Every later feature (agents, invoices, payments) needs the seams to exist first: module boundaries, contracts, clients, DB layout, and local infra. Establishing the modular-monolith skeleton now keeps future work additive instead of a refactor.

## Backend folder structure (chosen: Option A — layer-first)

```
backend/
├── api/                      # ALL HTTP lives here — modules never import FastAPI
│   ├── app.py                # create_app + lifespan
│   ├── deps.py               # GLOBAL deps only: settings, clients, current_user
│   └── routers/
│       ├── __init__.py       # api_router assembly
│       ├── auth.py           # routes + router-specific deps (inline)
│       ├── chat.py           # POST /chat, /chat/stream (SSE)
│       ├── files.py          # POST /files
│       └── payments.py       # POST /payments/runs, GET /runs/{id}
├── clients/                  # one seam per module (the ONLY way modules talk)
├── contracts/                # pydantic DTOs (StrictModel/ApiModel) per module
├── core/                     # config, logging, db/ (bases, engines, checkpointers)
├── modules/                  # framework-agnostic business logic
│   ├── auth/                 # models.py, service.py, repository.py, security.py, errors.py
│   ├── files/                # models.py, service.py, repository.py, storage.py, extract.py
│   ├── invoice_ingestor/     # models.py, service.py, repository.py, prompts.py
│   ├── guardrails/           # stub service
│   ├── llm_gateway/          # service.py (OpenRouter)
│   ├── mcp_gateway/          # skeleton
│   ├── prompts/              # main_agent.py, payment_agent.py registry
│   ├── tools/                # skeleton seam
│   ├── sessions/             # models.py, mutable + immutable repositories, service.py
│   ├── orchestrator/         # agent.py (main DeepAgent), service.py, tools.py
│   └── payments/             # models.py, agent.py, runner.py, repository.py, service.py
├── container.py              # composition root (Clients dataclass)
├── alembic/ + alembic.ini
├── pyproject.toml · Dockerfile · .env.example · package.json
```

## Impact

- `apps/` disappears; `frontend/` and `backend/` land at root; Turborepo/pnpm configs updated.
- `backend/` becomes a uv project (Python 3.13, ruff) with Alembic migrations and 3-DB wiring.
- New docker-compose.yml at root: full local stack (`docker compose up` = everything).

## Flow

```
                        ┌──────────────────────────── backend (FastAPI, async) ───────────────────────────┐
                        │                                                                                  │
  POST /auth/* ──────►  api/ ──► clients/auth ──────► modules/auth ───────► PG-1 (users)                 │
  POST /files  ──────►        ──► clients/files ─────► modules/files ──┬──► MinIO (S3 API)                │
                                                                      └──► PG-1 (files metadata)         │
  POST /chat  ───────►        ──► clients/guardrails ► modules/guardrails (stub: allowed)                │
                              ──► clients/orchestrator► modules/orchestrator ──┬──► DeepAgent (main)    │
                              ──► clients/llm ─────────► modules/llm_gateway ──┘    │ checkpoint       │
  POST /chat/stream ─►  (SSE)                                            ▼            PG-2              │
                                                          initiate_payments tool                          │
                              ──► clients/payments ─► modules/payments ──► background runner              │
                                                      (asyncio + runs/events log in PG-1)                 │
                                                          │ DeepAgent (payments) ── checkpoint ──► PG-3   │
  GET /payments/runs/{id} ► polling ◄──────────────────────┘                                               │
                              ──► clients/sessions ──► modules/sessions ──► mutable ──► PG-1              │
                                                                       └─► immutable ──► PG-3             │
  (later) email trigger ──────────────────────────────────► modules/invoice_ingestor (LLM invoice parse)  │
                        └──────────────────────────────────────────────────────────────────────────────────┘
```
