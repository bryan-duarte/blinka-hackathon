# Implementation Tasks

## Task Breakdown

### 1. Backend runtime (`backend/`)
- [x] `core/config.py`: set the `aws_profile` default to `None` in `StorageSettings`, `TextractSettings` and `RealtimeSettings`
- [x] New `core/db/bootstrap.py`: create `blinka_product` / `blinka_payments` if they're missing
- [x] New `docker-entrypoint.sh`: bootstrap DBs, run both Alembic upgrades, then exec uvicorn with `--timeout-keep-alive 130`
- [x] `Dockerfile`: copy the entrypoint and use `ENTRYPOINT`

### 2. Network (`infra/network.tf`)
- [x] Locals (`name`, `env`, `ssm_prefix`, `api_host`, `azs`) and the `aws_availability_zones` data source
- [x] VPC, IGW, 2 public + 2 private-app + 2 private-db subnets
- [x] EIP + NAT Gateway (1 AZ); route tables for public (IGW), app (NAT) and db (local only)
- [x] S3 gateway VPC endpoint on the app route tables
- [x] Security groups `alb`, `app`, `db`, chained by SG references

### 3. Edge (`infra/edge.tf`)
- [x] `data "aws_route53_zone"` for `var.domain_name`
- [x] ACM certificate for `api.<domain>`, plus validation records and `aws_acm_certificate_validation`
- [x] ALB (idle timeout 120), target group (ip:8000, `/health`), HTTPS listener, and an HTTP→HTTPS redirect listener
- [x] Route53 alias A record `api.<domain>` → ALB

### 4. Database (`infra/database.tf`)
- [x] `random_password.db_master`, a DB subnet group (db subnets)
- [x] `aws_db_instance.main`: Postgres 17, db.t4g.micro, 20 GB gp3, 1-day backups, no final snapshot

### 5. Config (`infra/ssm.tf`, `infra/realtime.tf`, `infra/variables.tf`, `infra/versions.tf`)
- [x] Add the `random` provider; add the variables `domain_name`, `api_subdomain`, `frontend_origin`, `vpc_cidr`; remove `jwt_secret`
- [x] `random_password.jwt_secret` and `random_password.demo_password`
- [x] Wire the Lambda authorizer `JWT_SECRET` to `random_password.jwt_secret.result`
- [x] `aws_ssm_parameter.managed` (Terraform-owned values) and `aws_ssm_parameter.operator` (seeded once, with `ignore_changes`)

### 6. Compute (`infra/compute.tf`)
- [x] ECR repo `blinka-backend` + a lifecycle policy that keeps the last 10 images
- [x] Log group `/ecs/blinka-backend` (7 days)
- [x] Execution role (managed policy + SSM read) and task role (evidence, realtime, guardrail, ECS Exec)
- [x] ECS cluster `blinka`, a Fargate ARM64 task definition (1 vCPU / 2 GB) with SSM `secrets`
- [x] ECS service: desired 0, min 0 / max 100, private subnets, ECS Exec, `ignore_changes = [task_definition, desired_count]`
- [x] `infra/outputs.tf`: new outputs for the deploy script and the user

### 7. Deploy script (`infra/deploy.sh`)
- [x] Default mode: build linux/arm64 → push `:<tag>` + `:latest` → register a revision → update the service (desired 1) → wait until stable
- [x] `--restart`: force a new deployment (picks up edited SSM values)
- [x] `--rollback <tag>`: register a revision with an existing tag and deploy it
- [x] Print the last 30 log lines if the wait fails

### 8. Bring-up (manual, once)
- [x] `terraform -chdir=infra init -upgrade && terraform -chdir=infra apply -var domain_name=... -var frontend_origin=...`
- [x] `infra/deploy.sh`, then `curl https://api.<domain>/health`
- [ ] Fill the `assign_later` params in the SSM console, then run `infra/deploy.sh --restart`
- [ ] Copy `terraform output -raw jwt_secret` into the local `backend/.env` (`BLINKA_JWT__SECRET`)
- [ ] Set `NEXT_PUBLIC_API_URL=https://api.<domain>` in Vercel; point the Composio trigger webhook at `https://api.<domain>/webhooks/mail`

### Post-Implementation Quality Gate
- [x] Run a two-subagent quality pass over the recently applied change:
  - [x] **Bug sweep**: launch a subagent to search the modified code (Terraform, entrypoint, bootstrap, deploy.sh, config.py) for bugs, issues and inconsistencies, such as logic errors, edge cases, broken contracts, dead code and regressions. Report concrete findings as `file:line` references. Include `terraform validate` and `bash -n infra/deploy.sh`.
  - [x] **Polish**: launch a subagent that invokes the `codebase-change` skill and applies polish directly to the changed files. It deletes unnecessary comments, makes the code self-explanatory, gives every variable an obvious purpose, maximizes readability and maintainability, and removes unnecessary complexity. It also resolves any real issues the bug sweep found.

## Task Order

```
1 backend ─────────────────────────────┐
2 network ─┬─► 3 edge ─┐               │
           ├─► 4 db ───┼─► 5 ssm ─► 6 compute ─► 7 deploy.sh ─► 8 bring-up ─► QA gate
           └───────────┘
```

## Deviations from the plan

- **DNS zone is created, not looked up.** `bryanjavier.com` lives in Cloudflare and the AWS account had no Route53 zones, so `edge.tf` creates `aws_route53_zone.main` for `var.domain_name = "blinka.bryanjavier.com"`, and Cloudflare delegates it with 4 NS records (manual, once). API host: `api.blinka.bryanjavier.com`. Bring-up therefore starts with `terraform apply -target=aws_route53_zone.main`.
- **`frontend_origin` is validated** (`https://` origin, no path or trailing slash), because a trailing slash silently breaks the CORS match.
- **`core.db.bootstrap` reads the DB URLs through `core.config.Settings`** instead of `os.environ` (codebase-change rule 11), and accepts `postgresql+psycopg://` URLs too.
- **`deploy.sh` also strips `enableFaultInjection`** from the cloned task definition, since the local AWS CLI (2.17.60) may not know that field.
- **Values live in `infra/terraform.tfvars`** (gitignored) so `plan`/`apply` need no `-var` flags.
