locals {
  evidence_bucket_arn         = "arn:aws:s3:::${var.evidence_bucket_prefix}-${data.aws_caller_identity.current.account_id}"
  guardduty_managed_rule_arn  = "arn:aws:events:${var.aws_region}:${data.aws_caller_identity.current.account_id}:rule/DO-NOT-DELETE-AmazonGuardDutyMalwareProtectionS3*"
  guardduty_service_principal = "malware-protection-plan.guardduty.amazonaws.com"
}

resource "aws_s3_bucket" "evidence" {
  bucket = "${var.evidence_bucket_prefix}-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_public_access_block" "evidence" {
  bucket                  = aws_s3_bucket.evidence.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

data "aws_iam_policy_document" "guardduty_scan_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = [local.guardduty_service_principal]
    }
  }
}

data "aws_iam_policy_document" "guardduty_scan" {
  statement {
    sid       = "AllowManagedRuleToSendS3EventsToGuardDuty"
    effect    = "Allow"
    actions   = ["events:PutRule", "events:DeleteRule", "events:PutTargets", "events:RemoveTargets"]
    resources = [local.guardduty_managed_rule_arn]

    condition {
      test     = "StringLike"
      variable = "events:ManagedBy"
      values   = [local.guardduty_service_principal]
    }
  }

  statement {
    sid       = "AllowGuardDutyToMonitorEventBridgeManagedRule"
    effect    = "Allow"
    actions   = ["events:DescribeRule", "events:ListTargetsByRule"]
    resources = [local.guardduty_managed_rule_arn]
  }

  statement {
    sid    = "AllowPostScanTag"
    effect = "Allow"
    actions = [
      "s3:PutObjectTagging",
      "s3:GetObjectTagging",
      "s3:PutObjectVersionTagging",
      "s3:GetObjectVersionTagging",
    ]
    resources = ["${local.evidence_bucket_arn}/*"]
  }

  statement {
    sid       = "AllowEnableS3EventBridgeEvents"
    effect    = "Allow"
    actions   = ["s3:PutBucketNotification", "s3:GetBucketNotification"]
    resources = [local.evidence_bucket_arn]
  }

  statement {
    sid       = "AllowPutValidationObject"
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${local.evidence_bucket_arn}/malware-protection-resource-validation-object"]
  }

  statement {
    sid       = "AllowCheckBucketOwnership"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [local.evidence_bucket_arn]
  }

  statement {
    sid       = "AllowMalwareScan"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:GetObjectVersion"]
    resources = ["${local.evidence_bucket_arn}/*"]
  }
}

resource "aws_iam_role" "guardduty_scan" {
  name               = "blinka-guardduty-s3-scan"
  assume_role_policy = data.aws_iam_policy_document.guardduty_scan_trust.json
}

resource "aws_iam_role_policy" "guardduty_scan" {
  name   = "scan-and-tag"
  role   = aws_iam_role.guardduty_scan.id
  policy = data.aws_iam_policy_document.guardduty_scan.json
}

# Tagging must be ENABLED at creation: objects uploaded before it are never tagged.
resource "aws_guardduty_malware_protection_plan" "evidence" {
  role = aws_iam_role.guardduty_scan.arn

  protected_resource {
    s3_bucket {
      bucket_name = aws_s3_bucket.evidence.id
    }
  }

  actions = [{
    tagging = [{
      status = "ENABLED"
    }]
  }]

  depends_on = [
    aws_iam_role_policy.guardduty_scan,
    aws_s3_bucket_public_access_block.evidence,
    aws_s3_bucket_ownership_controls.evidence,
    aws_s3_bucket_server_side_encryption_configuration.evidence,
  ]
}

data "aws_iam_policy_document" "backend_evidence" {
  statement {
    sid       = "EvidenceObjects"
    effect    = "Allow"
    actions   = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:GetObjectTagging"]
    resources = ["${aws_s3_bucket.evidence.arn}/*"]
  }

  statement {
    sid       = "EvidenceBucket"
    effect    = "Allow"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.evidence.arn]
  }

  statement {
    sid       = "InvoiceVisualExtraction"
    effect    = "Allow"
    actions   = ["textract:AnalyzeExpense"]
    resources = ["*"]
  }
}

resource "aws_iam_user_policy" "backend_evidence" {
  name   = "blinka-backend-evidence"
  user   = var.backend_iam_user
  policy = data.aws_iam_policy_document.backend_evidence.json
}
