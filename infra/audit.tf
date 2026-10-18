locals {
  audited_db_instances = {
    main  = "${local.name}-${local.env}"
    agent = "${local.name}-${local.env}-agent"
  }
  db_audit_bucket_name             = "${local.name}-db-audit-${data.aws_caller_identity.current.account_id}"
  db_audit_log_filter              = "AUDIT"
  db_audit_log_retention_days      = 30
  db_audit_glacier_days            = 30
  db_audit_expiration_days         = 365
  db_audit_noncurrent_version_days = 30
}

resource "aws_db_parameter_group" "audit" {
  name        = "${local.name}-${local.env}-pg17-audit"
  family      = "postgres17"
  description = "pgaudit (ddl, write, role) for every Blinka Postgres instance"

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

# Created before the instances so RDS writes into a group with retention instead of its own.
resource "aws_cloudwatch_log_group" "rds" {
  for_each = local.audited_db_instances

  name              = "/aws/rds/instance/${each.value}/postgresql"
  retention_in_days = local.db_audit_log_retention_days
}

resource "aws_s3_bucket" "db_audit" {
  bucket = local.db_audit_bucket_name
}

resource "aws_s3_bucket_versioning" "db_audit" {
  bucket = aws_s3_bucket.db_audit.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "db_audit" {
  bucket                  = aws_s3_bucket.db_audit.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "db_audit" {
  bucket = aws_s3_bucket.db_audit.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "db_audit" {
  bucket = aws_s3_bucket.db_audit.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "db_audit" {
  bucket = aws_s3_bucket.db_audit.id

  rule {
    id     = "archive-then-expire"
    status = "Enabled"

    filter {}

    transition {
      days          = local.db_audit_glacier_days
      storage_class = "GLACIER_IR"
    }

    expiration {
      days = local.db_audit_expiration_days
    }

    noncurrent_version_expiration {
      noncurrent_days = local.db_audit_noncurrent_version_days
    }
  }
}

data "aws_iam_policy_document" "firehose_db_audit_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["firehose.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

data "aws_iam_policy_document" "firehose_db_audit" {
  statement {
    effect = "Allow"
    actions = [
      "s3:AbortMultipartUpload",
      "s3:GetBucketLocation",
      "s3:GetObject",
      "s3:ListBucket",
      "s3:ListBucketMultipartUploads",
      "s3:PutObject",
    ]
    resources = [aws_s3_bucket.db_audit.arn, "${aws_s3_bucket.db_audit.arn}/*"]
  }
}

resource "aws_iam_role" "firehose_db_audit" {
  name               = "${local.name}-${local.env}-firehose-db-audit"
  assume_role_policy = data.aws_iam_policy_document.firehose_db_audit_trust.json
}

resource "aws_iam_role_policy" "firehose_db_audit" {
  name   = "write-db-audit-bucket"
  role   = aws_iam_role.firehose_db_audit.id
  policy = data.aws_iam_policy_document.firehose_db_audit.json
}

resource "aws_kinesis_firehose_delivery_stream" "db_audit" {
  for_each = local.audited_db_instances

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

data "aws_iam_policy_document" "cwl_to_firehose_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["logs.${var.aws_region}.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"]
    }
  }
}

data "aws_iam_policy_document" "cwl_to_firehose" {
  statement {
    effect    = "Allow"
    actions   = ["firehose:PutRecord", "firehose:PutRecordBatch"]
    resources = [for stream in aws_kinesis_firehose_delivery_stream.db_audit : stream.arn]
  }
}

resource "aws_iam_role" "cwl_to_firehose" {
  name               = "${local.name}-${local.env}-cwl-to-firehose"
  assume_role_policy = data.aws_iam_policy_document.cwl_to_firehose_trust.json
}

resource "aws_iam_role_policy" "cwl_to_firehose" {
  name   = "put-db-audit-records"
  role   = aws_iam_role.cwl_to_firehose.id
  policy = data.aws_iam_policy_document.cwl_to_firehose.json
}

resource "aws_cloudwatch_log_subscription_filter" "db_audit" {
  for_each = local.audited_db_instances

  name            = "pgaudit-to-s3"
  log_group_name  = aws_cloudwatch_log_group.rds[each.key].name
  filter_pattern  = local.db_audit_log_filter
  destination_arn = aws_kinesis_firehose_delivery_stream.db_audit[each.key].arn
  role_arn        = aws_iam_role.cwl_to_firehose.arn

  depends_on = [aws_iam_role_policy.cwl_to_firehose]
}
