# AWS Infrastructure for the Blinka Backend (ECS Fargate + network isolation)

> "We gave an AI agent the power to pay invoices, then hid it in a private subnet so it can't wander off. Just like the CFO."
> - El Barto

## Overview

**Request**: Build the AWS infrastructure for the backend. Only the entry point is public and everything else is isolated in private subnets. Retention and backups stay simple (it's a hackathon). Config comes from Parameter Store: non-sensitive values get defaults and sensitive ones get `assign_later`. The ECS task gets an IAM role with exactly the permissions it needs. There's no CI/CD, just a script that deploys a new image. The backend is consumed by a Next.js frontend hosted elsewhere (Vercel).

**Created**: 2026-10-17

## What

- A VPC with three tiers:
  - **public**: ALB and NAT Gateway
  - **private-app**: ECS Fargate tasks
  - **private-db**: RDS, with no internet route at all
- HTTPS at `api.<domain>`: a Route53 record, an ACM certificate, and an HTTP→HTTPS redirect.
- One Fargate task (1 vCPU / 2 GB, ARM64) running the FastAPI modular monolith.
- One RDS Postgres 17 `db.t4g.micro` instance holding both logical databases (`blinka_product`, `blinka_payments`).
- Every backend setting lives as an SSM parameter under `/blinka/prod/` and is injected into the container by ECS.
- A task role with least-privilege access to S3, Textract, Bedrock ApplyGuardrail, AppSync Events, and ECS Exec.
- A container entrypoint that creates the databases if they're missing, runs both Alembic migrations, and then starts uvicorn.
- `infra/deploy.sh`, which builds, pushes `:<git-sha>`, registers a new task-definition revision, deploys, and waits until the service is stable. It also has `--restart` and `--rollback <tag>` modes.

## Why

The backend only runs on a laptop today, and its AWS access goes through a personal IAM user profile. The hackathon needs a public, HTTPS-reachable API that the Vercel frontend can call and that Kapso and Composio webhooks can reach. The database and business logic must not be exposed to the internet.

## Impact

- `infra/` grows from 3 managed services to a full stack. It stays one Terraform root with local state.
- Small backend changes:
  - The `aws_profile` defaults become `None`. This fixes a `ProfileNotFound` crash on Fargate.
  - A new entrypoint script and a DB bootstrap helper.
  - The Dockerfile starts through the entrypoint and sets a longer uvicorn keep-alive.
- The JWT secret becomes Terraform-generated and is shared by the backend and the AppSync authorizer. Existing tokens are invalidated once, and local `.env` must copy the new value.
- Estimated cost is about **$100/month**:
  - NAT GW ~$35
  - ALB ~$18
  - Fargate ~$29
  - RDS ~$15
  - Everything else ~$3

## Flow

```
                 Internet
                    │
     Vercel (Next.js) ──HTTPS──┐        Composio / Kapso webhooks ──HTTPS──┐
                               ▼                                           ▼
┌──────────────────────────── VPC 10.20.0.0/16 ────────────────────────────────────┐
│  PUBLIC subnets (2 AZ)                                                          │
│    ALB :443 (ACM, api.<domain>)  ── :80 → redirect 443                          │
│    NAT Gateway (1 AZ) ◄──────────────────────────────┐ egress only            │
│          │ sg: alb → app:8000                        │                         │
│  PRIVATE-APP subnets (2 AZ)                          │                         │
│    ECS Fargate task "blinka-backend" (FastAPI monolith, all modules)           │
│          │  ├─► OpenRouter / Composio / Kapso / FX ─┘ (via NAT)               │
│          │  ├─► S3 evidence (S3 gateway endpoint, free)                        │
│          │  └─► Textract / Bedrock guardrail / AppSync Events (via NAT)       │
│          │ sg: app → db:5432                                                   │
│  PRIVATE-DB subnets (2 AZ, no internet route)                                  │
│    RDS Postgres 17  ── blinka_product, blinka_payments                         │
└─────────────────────────────────────────────────────────────────────────────────┘

Deploy (laptop): infra/deploy.sh → docker buildx (arm64) → ECR :<sha>
               → register task-def revision → update-service → wait stable
Config: SSM /blinka/prod/* → ECS injects at task start → env vars → pydantic-settings
```
