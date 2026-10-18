# Implementation Tasks

## Task Breakdown

### 1. Backend runtime (`backend/`)
- [ ] `core/config.py`: set the `aws_profile` default to `None` in `StorageSettings`, `TextractSettings` and `RealtimeSettings`
- [ ] New `core/db/bootstrap.py`: create `blinka_product` / `blinka_payments` if they're missing
- [ ] New `docker-entrypoint.sh`: bootstrap DBs, run both Alembic upgrades, then exec uvicorn with `--timeout-keep-alive 130`
- [ ] `Dockerfile`: copy the entrypoint and use `ENTRYPOINT`

### 2. Network (`infra/network.tf`)
- [ ] Locals (`name`, `env`, `ssm_prefix`, `api_host`, `azs`) and the `aws_availability_zones` data source
- [ ] VPC, IGW, 2 public + 2 private-app + 2 private-db subnets
- [ ] EIP + NAT Gateway (1 AZ); route tables for public (IGW), app (NAT) and db (local only)
- [ ] S3 gateway VPC endpoint on the app route tables
- [ ] Security groups `alb`, `app`, `db`, chained by SG references

### 3. Edge (`infra/edge.tf`)
- [ ] `data "aws_route53_zone"` for `var.domain_name`
- [ ] ACM certificate for `api.<domain>`, plus validation records and `aws_acm_certificate_validation`
- [ ] ALB (idle timeout 120), target group (ip:8000, `/health`), HTTPS listener, and an HTTP→HTTPS redirect listener
- [ ] Route53 alias A record `api.<domain>` → ALB

### 4. Database (`infra/database.tf`)
- [ ] `random_password.db_master`, a DB subnet group (db subnets)
- [ ] `aws_db_instance.main`: Postgres 17, db.t4g.micro, 20 GB gp3, 1-day backups, no final snapshot

### 5. Config (`infra/ssm.tf`, `infra/realtime.tf`, `infra/variables.tf`, `infra/versions.tf`)
- [ ] Add the `random` provider; add the variables `domain_name`, `api_subdomain`, `frontend_origin`, `vpc_cidr`; remove `jwt_secret`
- [ ] `random_password.jwt_secret` and `random_password.demo_password`
- [ ] Wire the Lambda authorizer `JWT_SECRET` to `random_password.jwt_secret.result`
- [ ] `aws_ssm_parameter.managed` (Terraform-owned values) and `aws_ssm_parameter.operator` (seeded once, with `ignore_changes`)

### 6. Compute (`infra/compute.tf`)
- [ ] ECR repo `blinka-backend` + a lifecycle policy that keeps the last 10 images
- [ ] Log group `/ecs/blinka-backend` (7 days)
- [ ] Execution role (managed policy + SSM read) and task role (evidence, realtime, guardrail, ECS Exec)
- [ ] ECS cluster `blinka`, a Fargate ARM64 task definition (1 vCPU / 2 GB) with SSM `secrets`
- [ ] ECS service: desired 0, min 0 / max 100, private subnets, ECS Exec, `ignore_changes = [task_definition, desired_count]`
- [ ] `infra/outputs.tf`: new outputs for the deploy script and the user

### 7. Deploy script (`infra/deploy.sh`)
- [ ] Default mode: build linux/arm64 → push `:<tag>` + `:latest` → register a revision → update the service (desired 1) → wait until stable
- [ ] `--restart`: force a new deployment (picks up edited SSM values)
- [ ] `--rollback <tag>`: register a revision with an existing tag and deploy it
- [ ] Print the last 30 log lines if the wait fails

### 8. Bring-up (manual, once)
- [ ] `terraform -chdir=infra init -upgrade && terraform -chdir=infra apply -var domain_name=... -var frontend_origin=...`
- [ ] `infra/deploy.sh`, then `curl https://api.<domain>/health`
- [ ] Fill the `assign_later` params in the SSM console, then run `infra/deploy.sh --restart`
- [ ] Copy `terraform output -raw jwt_secret` into the local `backend/.env` (`BLINKA_JWT__SECRET`)
- [ ] Set `NEXT_PUBLIC_API_URL=https://api.<domain>` in Vercel; point the Composio trigger webhook at `https://api.<domain>/webhooks/mail`

### Post-Implementation Quality Gate
- [ ] Run a two-subagent quality pass over the recently applied change:
  - [ ] **Bug sweep**: launch a subagent to search the modified code (Terraform, entrypoint, bootstrap, deploy.sh, config.py) for bugs, issues and inconsistencies, such as logic errors, edge cases, broken contracts, dead code and regressions. Report concrete findings as `file:line` references. Include `terraform validate` and `bash -n infra/deploy.sh`.
  - [ ] **Polish**: launch a subagent that invokes the `codebase-change` skill and applies polish directly to the changed files. It deletes unnecessary comments, makes the code self-explanatory, gives every variable an obvious purpose, maximizes readability and maintainability, and removes unnecessary complexity. It also resolves any real issues the bug sweep found.

## Task Order

```
1 backend ─────────────────────────────┐
2 network ─┬─► 3 edge ─┐               │
           ├─► 4 db ───┼─► 5 ssm ─► 6 compute ─► 7 deploy.sh ─► 8 bring-up ─► QA gate
           └───────────┘
```
