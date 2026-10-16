# blinka-hackathon

Turborepo monorepo: Next.js frontend (`apps/web`) + FastAPI backend (`apps/api`, managed with uv).

## Setup

```sh
pnpm install
cd apps/api && uv sync
```

## Commands (from repo root)

| Command     | What it runs                                              |
| ----------- | --------------------------------------------------------- |
| `pnpm dev`  | web on http://localhost:3000 + api on http://localhost:8000 |
| `pnpm build`| builds all apps (api build = `uv sync`)                   |
| `pnpm lint` | ESLint (web) + ruff (api)                                 |

Backend endpoints: `GET http://localhost:8000/health`, docs at `/docs`.
