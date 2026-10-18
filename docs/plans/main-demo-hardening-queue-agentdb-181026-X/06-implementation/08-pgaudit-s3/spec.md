# PGAudit + S3 Audit Log Copies Implementation

## Overview

Enable pgaudit on both RDS instances (`blinka-prod` and `blinka-prod-agent`) through one shared parameter group, logging `ddl,write,role`. Export the Postgres logs to CloudWatch, and stream only audit lines to S3 through Firehose (one stream per instance) into a versioned, encrypted bucket with a lifecycle policy.

## Files to Modify/Create

- `infra/audit.tf` (new):
  - `aws_db_parameter_group.audit`
  - `aws_cloudwatch_log_group.rds` (for_each over the instances)
  - `aws_s3_bucket.db_audit` and its versioning, SSE, public-access-block, ownership and lifecycle resources
  - `aws_iam_role.firehose_db_audit` and its policy
  - `aws_iam_role.cwl_to_firehose` and its policy
  - `aws_kinesis_firehose_delivery_stream.db_audit` (for_each)
  - `aws_cloudwatch_log_subscription_filter.db_audit` (for_each)
- `infra/database.tf`: on `aws_db_instance.main` add `parameter_group_name = aws_db_parameter_group.audit.name`, `enabled_cloudwatch_logs_exports = ["postgresql"]` and `depends_on = [aws_cloudwatch_log_group.rds]`. The agent instance gets the same, through module 07.
- `infra/outputs.tf`: add `db_audit_bucket`.
- `backend/alembic/versions/product/<rev>_enable_pgaudit.py` (new) and `backend/alembic/versions/agent/<rev>_enable_pgaudit.py` (new): create the extension only when it is available.

## Implementation Guidelines

```hcl
# infra/audit.tf (orientative)
locals {
  audited_db_instances = {
    main  = "${local.name}-${local.env}"
    agent = "${local.name}-${local.env}-agent"
  }
}

resource "aws_db_parameter_group" "audit" {
  name   = "${local.name}-${local.env}-pg17-audit"
  family = "postgres17"

  parameter {
    name         = "shared_preload_libraries"
    value        = "pg_stat_statements,pgaudit"
    apply_method = "pending-reboot"
  }
  parameter {
    name  = "pgaudit.log"
    value = "ddl,write,role"
  }
  parameter {
    name  = "pgaudit.log_catalog"
    value = "0"
  }
  parameter {
    name  = "pgaudit.log_parameter"
    value = "0"
  }
  parameter {
    name  = "pgaudit.log_relation"
    value = "0"
  }
}

resource "aws_cloudwatch_log_group" "rds" {
  for_each          = local.audited_db_instances
  name              = "/aws/rds/instance/${each.value}/postgresql"
  retention_in_days = 30
}

resource "aws_s3_bucket" "db_audit" {
  bucket = "${local.name}-db-audit-${data.aws_caller_identity.current.account_id}"
}
# + aws_s3_bucket_versioning (Enabled), aws_s3_bucket_server_side_encryption_configuration (AES256),
#   aws_s3_bucket_public_access_block (all true), aws_s3_bucket_ownership_controls (BucketOwnerEnforced),
#   aws_s3_bucket_lifecycle_configuration: transition GLACIER_IR at 30d, expire 365d, noncurrent expire 30d.
#   Mirror the evidence bucket style in infra/evidence.tf:7-35.

resource "aws_kinesis_firehose_delivery_stream" "db_audit" {
  for_each    = local.audited_db_instances
  name        = "${local.name}-${local.env}-db-audit-${each.key}"
  destination = "extended_s3"

  extended_s3_configuration {
    role_arn            = aws_iam_role.firehose_db_audit.arn
    bucket_arn          = aws_s3_bucket.db_audit.arn
    prefix              = "pgaudit/${each.key}/!{timestamp:yyyy/MM/dd}/"
    error_output_prefix = "pgaudit-errors/${each.key}/!{firehose:error-output-type}/!{timestamp:yyyy/MM/dd}/"
    buffering_size      = 5
    buffering_interval  = 300
    compression_format  = "GZIP"

    processing_configuration {
      enabled = true
      processors {
        type = "Decompression"
        parameters {
          parameter_name  = "CompressionFormat"
          parameter_value = "GZIP"
        }
      }
      processors {
        type = "CloudWatchLogProcessing"
        parameters {
          parameter_name  = "DataMessageExtraction"
          parameter_value = "true"
        }
      }
    }
  }
}

resource "aws_cloudwatch_log_subscription_filter" "db_audit" {
  for_each        = local.audited_db_instances
  name            = "pgaudit-to-s3"
  log_group_name  = aws_cloudwatch_log_group.rds[each.key].name
  filter_pattern  = "AUDIT"
  destination_arn = aws_kinesis_firehose_delivery_stream.db_audit[each.key].arn
  role_arn        = aws_iam_role.cwl_to_firehose.arn
}
```

- **Provider check:** confirm that the `Decompression` and `CloudWatchLogProcessing` processor types are supported by the pinned AWS provider (`>= 6.9`). If they are not, drop `processing_configuration` and set `compression_format = "UNCOMPRESSED"`; CloudWatch data already arrives gzipped.
- **`pg_stat_statements`:** RDS's default `shared_preload_libraries` value includes it. Keep it alongside `pgaudit`.
- **Account ID:** reuse `data.aws_caller_identity.current` if it already exists (check `evidence.tf`). Otherwise declare it.
- **IAM roles:**
  - `firehose_db_audit`: trust `firehose.amazonaws.com` with condition `aws:SourceAccount`. Allow `s3:AbortMultipartUpload`, `GetBucketLocation`, `GetObject`, `ListBucket`, `ListBucketMultipartUploads` and `PutObject` on the bucket and `bucket/*`.
  - `cwl_to_firehose`: trust `logs.<region>.amazonaws.com` with condition `aws:SourceArn` = `arn:aws:logs:<region>:<account>:*`. Allow `firehose:PutRecord` and `firehose:PutRecordBatch` on both stream ARNs.

```python
# alembic migration (both chains; orientative)
def upgrade() -> None:
    connection = op.get_bind()
    is_available = connection.execute(
        sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'pgaudit'")
    ).scalar()
    if is_available:
        op.execute("CREATE EXTENSION IF NOT EXISTS pgaudit")

def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pgaudit")
```

- The `CREATE EXTENSION` succeeds only after the reboot has loaded the library. If the deploy runs before the reboot, the extension is still *available*, but creating it fails with "pgaudit must be loaded via shared_preload_libraries". Run the reboot **before** the deploy (see the apply sequence below). Or make the guard also check `current_setting('shared_preload_libraries') LIKE '%pgaudit%'`; this is preferred because it is safe in any order.

**Apply sequence:**
1. `terraform apply`. This creates the parameter group, the log groups, the bucket, Firehose and the filters, and attaches the group (status `pending-reboot`).
2. Scale ECS to 0, then run `aws rds reboot-db-instance --db-instance-identifier blinka-prod` (and `blinka-prod-agent`). Wait for both to be `available`.
3. `deploy.sh`. The migrations create the extension and the service starts.
4. Verify:
   - `SHOW shared_preload_libraries;` contains `pgaudit`;
   - an `AUDIT:` line appears in `/aws/rds/instance/blinka-prod/postgresql`;
   - after about 5 minutes, objects appear under `s3://blinka-db-audit-<acct>/pgaudit/main/`.

## Dependencies

- Module 07 (agent instance) for the `agent` key. Without it, apply with only `main` in `local.audited_db_instances`.

## Integration Notes

- **No application code reads the audit logs.** The only app-side change is the guarded extension migration in each Alembic chain.
- **Reads are not audited** (user choice).
- **Volume:** if checkpoint writes make the agent DB audit volume too high, see the mitigation in `05-risks.md`.
