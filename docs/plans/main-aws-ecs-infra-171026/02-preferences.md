# User Preferences & Decisions

## 👤 Configuration Preferences

- **Context Level**: Moderado
- **Participation Level**: Equilibrado
- **Detail Level**: Neutral

## 💬 Q&A and Rationale

### 🏷️ Edge & Networking
**Q:** How does the public entry point (ALB) get HTTPS?
**A:** Route53 domain + ACM.
**Decision:** `data "aws_route53_zone"` by `var.domain_name`, ACM cert for `api.<domain>` with DNS validation, A-alias record → ALB, HTTP:80 → 301 to HTTPS.
**Rejected:** CloudFront (60s origin timeout vs ~60s malware-scan uploads); external registrar (manual pause).

**Q:** Which NAT for private egress?
**A:** NAT Gateway.
**Decision:** One NAT Gateway in the first public subnet; both private-app route tables use it. Private-db subnets get no default route.
**Rejected:** fck-nat instance (self-managed EC2).

### 🏷️ Frontend
**Q:** Where is the Next.js frontend deployed?
**A:** Vercel / outside this infra.
**Decision:** Not in Terraform. `var.frontend_origin` feeds `BLINKA_CORS__ALLOW_ORIGINS` and the Composio/Kapso callback URLs. The user sets `NEXT_PUBLIC_API_URL=https://api.<domain>` in Vercel.
**Rejected:** ECS frontend / Amplify Hosting (more infra, CI-like).

### 🏷️ Configuration
**Q:** How does the backend read config from Parameter Store?
**A:** ECS-native injection.
**Decision:** Task definition `secrets = [{ name = <ENV_VAR>, valueFrom = <ssm arn> }]` for every parameter under `/blinka/prod/`. No loader code. Alembic and import-time `CorsSettings()` work unchanged. Changing a value requires `deploy.sh --restart`.
**Rejected:** Startup loader in code (more code + task-role SSM perms for no hackathon benefit).

**Q:** JWT secret handling?
**A:** Terraform `random_password`.
**Decision:** `random_password.jwt_secret` → SSM `BLINKA_JWT__SECRET` (SecureString) and `aws_lambda_function.realtime_authorizer` env `JWT_SECRET`. Remove `var.jwt_secret`. Sensitive output `jwt_secret` so local `.env` can match.
**Rejected:** `var.jwt_secret` (manual), `assign_later` (Lambda would desync).

**Q:** Which feature flags are ON by default?
**A:** Demo mode, Guardrails enforce, Realtime, Malware scan + live FX (all of them).
**Decision:** `BLINKA_DEMO__ENABLED=true` with `BLINKA_DEMO__PASSWORD` from `random_password.demo_password` (validator requires it). `BLINKA_GUARDRAILS__ENFORCE=true` + id/version from `aws_bedrock_guardrail*`. `BLINKA_REALTIME__ENABLED=true` + `HTTP_DOMAIN` from `aws_appsync_api.events.dns["HTTP"]`. `BLINKA_STORAGE__MALWARE_SCAN_ENABLED=true`, `BLINKA_FX__LIVE_ENABLED=true`.

### 🏷️ Compute & Rollout
**Q:** Deploy rollout strategy?
**A:** 1 task, stop-then-start.
**Decision:** `desired_count = 1` (set by deploy.sh), `deployment_minimum_healthy_percent = 0`, `deployment_maximum_percent = 100`. ~1–2 min downtime per deploy, no overlapping tasks (startup sweeps are global, demo state is in-memory).
**Rejected:** start-then-stop (overlap fails in-flight work); multi-replica code fixes (out of scope).

**Q:** Sizing?
**A:** 1 vCPU / 2 GB ARM64 + db.t4g.micro.
**Decision:** `cpu = 1024`, `memory = 2048`, `runtime_platform { cpu_architecture = "ARM64", operating_system_family = "LINUX" }`. RDS `db.t4g.micro`, 20 GB gp3, single-AZ, Postgres 17.

### 🏷️ Migrations & Deploy
**Q:** How do Alembic migrations run?
**A:** Container entrypoint.
**Decision:** `backend/docker-entrypoint.sh`: `python -m core.db.bootstrap` (create missing DBs) → `alembic -n product upgrade head` → `alembic -n payments upgrade head` → `exec uvicorn`. Safe because only one task ever runs.
**Rejected:** One-off `run-task` (longer, more complex script).

**Q:** Image versioning?
**A:** Git SHA + new task-definition revision.
**Decision:** Tag `<short-sha>` (suffix `-dirty-<epoch>` when the tree has uncommitted changes) plus `:latest`. The script clones the latest ACTIVE revision of family `blinka-backend`, swaps the image, registers it, and updates the service. `--rollback <tag>` re-registers with an existing tag.
**Rejected:** `:latest` + force-new-deployment only (no traceability).

**Q:** Terraform layout & state?
**A:** Extend `infra/`, keep local state.
**Decision:** New flat files in `infra/` (no modules), same root, so they reference `aws_s3_bucket.evidence`, `aws_bedrock_guardrail.email_input_guard`, `aws_appsync_api.events` directly.
**Rejected:** S3 backend (single operator), separate root (extra wiring).

### 🏷️ Retention
**Q:** Retention & backup profile?
**A:** Minimal.
**Decision:** CloudWatch log group retention 7 days; RDS `backup_retention_period = 1`, `skip_final_snapshot = true`, `deletion_protection = false`; ECR lifecycle keeps the last 10 images; ECR `force_delete = true`.

### 🏷️ Agent-decided (not asked)
- **Region/profile:** keep `us-east-1`, `var.aws_profile = "panoptico"`.
- **Environment name:** `local.env = "prod"`, SSM prefix `/blinka/prod/`. No multi-env variables.
- **AZs:** 2. ALB and the RDS subnet group require 2. NAT is in 1 AZ.
- **VPC endpoints:** only the S3 gateway endpoint (free, also serves ECR layers). Interface endpoints (~$7/mo each) are skipped; that traffic goes through NAT.
- **ECS Exec:** enabled (`enable_execute_command = true`), so you can shell into the task to debug without a bastion.
- **Existing `Bryan-User` IAM user policies:** kept, for local development.
- **`aws_profile` fix:** change the defaults in `core/config.py` to `None` (one root fix) instead of patching each adapter.
- **ALB idle timeout:** 120s; uvicorn `--timeout-keep-alive 130`.
- **DB URL TLS:** append `?sslmode=require` (RDS PG17 forces SSL).
