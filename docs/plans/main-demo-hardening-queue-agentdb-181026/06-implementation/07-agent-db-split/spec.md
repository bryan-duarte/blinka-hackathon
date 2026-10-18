# Agent DB Split Implementation

## Overview

Move the LangGraph checkpoint database off the product RDS instance onto a dedicated instance, `blinka-prod-agent` (database `blinka_agent`). In code, rename the "payments DB" concept to "agent DB" everywhere. Product data, including the ledger, payments and `mailbox_connections`, stays on `blinka-prod`. Old checkpoints are not migrated.

## Files to Modify/Create

**Backend**
- `backend/core/config.py:164`: rename `payments_database_url: str` to `agent_database_url: str` (env `BLINKA_AGENT_DATABASE_URL`).
- `backend/core/db/base.py:17`: rename `PaymentsBase` to `AgentBase`.
- `backend/core/db/__init__.py`: update the export.
- `backend/core/db/engine.py`:
  - rename `Pools.payments` to `Pools.agent`;
  - `build_pools(product_dsn, agent_dsn, ...)`.
- `backend/core/db/checkpointers.py`:
  - rename `payments` to `agent` (attribute and constructor arg);
  - pool change from module 04.
- `backend/core/db/bootstrap.py:40`: `ensure_databases([settings.product_database_url, settings.agent_database_url])`. This already works across different hosts because each DSN carries its own host.
- `backend/api/app.py:113-115,140`: rename the arguments and attributes.
- `backend/container.py`: `checkpointers.payments` becomes `checkpointers.agent` wherever the agent graph receives its checkpointer.
- `backend/scripts/seed_demo.py:22-39`: rename.
- `backend/alembic.ini:5-17`: change section `[payments]` to `[agent]`, with `version_table = alembic_version_agent`, `version_locations = alembic/versions/agent`, and URL `localhost:5434/blinka_agent`.
- `backend/alembic/env.py:13-28`:
  - map `"agent": "BLINKA_AGENT_DATABASE_URL"`;
  - `if config.config_ini_section == "agent": from core.db.base import AgentBase as target_base`;
  - keep the `import modules.payments.models` line only if it registers tables on `AgentBase` (it does not; `PaymentsBase` had none). Remove it from the agent branch if it is unused.
- `git mv backend/alembic/versions/payments backend/alembic/versions/agent`. The existing chain (`ce5dde636187` create `session_executions`, then `255d510920f0` drop it) is net zero and applies cleanly on the fresh DB.
- `backend/docker-entrypoint.sh`: `alembic -n payments upgrade head` becomes `alembic -n agent upgrade head`.
- `backend/.env.example`: `BLINKA_PAYMENTS_DATABASE_URL` becomes `BLINKA_AGENT_DATABASE_URL=postgresql://blinka:blinka@localhost:5434/blinka_agent`.
- `docker-compose.yml`: service `postgres-payments` becomes `postgres-agent`, with `POSTGRES_DB=blinka_agent`, port 5434 and the volume renamed.
- Grep for leftovers with `rg -n "payments_database_url|PAYMENTS_DATABASE_URL|PaymentsBase|pools\.payments|checkpointers\.payments|-n payments"` and expect zero hits.

**Infra**
- `infra/database.tf`:
  - add `random_password.agent_db` (32 characters, `special = false`);
  - add `aws_db_instance.agent`;
  - add `local.agent_db_server_url`;
  - set `parameter_group_name = aws_db_parameter_group.audit.name` and `enabled_cloudwatch_logs_exports = ["postgresql"]` on both instances (module 08).
- `infra/ssm.tf:27`: replace `BLINKA_PAYMENTS_DATABASE_URL` with `BLINKA_AGENT_DATABASE_URL = { secure = true, value = "${local.agent_db_server_url}/blinka_agent?sslmode=require" }`.
- `infra/outputs.tf`: add `agent_db_endpoint`.

## Implementation Guidelines

```hcl
# infra/database.tf (orientative; mirror aws_db_instance.main at lines 16-37)
resource "aws_db_instance" "agent" {
  identifier                      = "${local.name}-${local.env}-agent"
  engine                          = "postgres"
  engine_version                  = "17"
  instance_class                  = "db.t4g.micro"
  allocated_storage               = 20
  storage_type                    = "gp3"
  storage_encrypted               = true
  db_name                         = "blinka_agent"
  username                        = local.db_username
  password                        = random_password.agent_db.result
  db_subnet_group_name            = aws_db_subnet_group.main.name     # reuse existing
  vpc_security_group_ids          = [aws_security_group.db.id]       # reuse existing (app SG → 5432)
  parameter_group_name            = aws_db_parameter_group.audit.name
  enabled_cloudwatch_logs_exports = ["postgresql"]
  publicly_accessible             = false
  multi_az                        = false
  backup_retention_period         = 1
  skip_final_snapshot             = true
  deletion_protection             = false
  apply_immediately               = true
  auto_minor_version_upgrade      = true
  depends_on                      = [aws_cloudwatch_log_group.rds]   # module 08: retention set before RDS creates it
}

locals {
  agent_db_server_url = "postgresql://${local.db_username}:${random_password.agent_db.result}@${aws_db_instance.agent.address}:${local.postgres_port}"
}
```

- Check the real names of the subnet group, security group and DB username locals in `database.tf` and `network.tf`, and reuse them.

**Cutover order:**
1. `terraform apply`. This creates the agent instance and changes the SSM URL.
2. `deploy.sh`. The entrypoint bootstrap creates `blinka_agent` if it is missing, runs `alembic -n agent upgrade head`, and `Checkpointers.open()` runs `setup()`.
3. Verify that a new run shows its trace.
4. Manually run `DROP DATABASE blinka_payments;` on the main instance through ECS exec with psql or a one-off Python psycopg call.

**Local dev:** the memory note says the dev containers are `blinka-dev-product` (55432) and `blinka-dev-payments` (55434). Point `BLINKA_AGENT_DATABASE_URL` at the 55434 container with db `blinka_agent`; the bootstrap creates it. Do not edit `.env` lock files or pins.

## Dependencies

- None upstream. Modules 04 (checkpointer pool) and 08 (parameter group, log groups) touch the same files, so coordinate the edits.

## Integration Notes

- `PaymentsService.trace` (`modules/payments/service.py:291-308`) reads from the checkpointer. For runs whose checkpoints stayed on the old DB, it returns `is_available=false`, which the UI already handles.
- **No product-DB schema change in this module.**
