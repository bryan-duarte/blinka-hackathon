# Infra — S3 Evidence Bucket + GuardDuty Malware Protection + Textract IAM

## Overview

Terraform provisions the AWS-side prerequisites: a private S3 evidence bucket, GuardDuty Malware Protection for S3 with scan-result tagging, and IAM policies for the backend user (`panoptico` profile → IAM user `Bryan-User`) covering the bucket and Textract.

## Files to Modify/Create

- `infra/evidence.tf` (new) — all resources below
- `infra/outputs.tf` — add `evidence_bucket_name`
- `backend/.env.example` + `backend/.env` — `BLINKA_STORAGE__BUCKET`, `BLINKA_STORAGE__AWS_PROFILE`, `BLINKA_STORAGE__REGION`
- `docker-compose.yml` — remove `minio` service and the backend `BLINKA_STORAGE__ENDPOINT_URL` override (see module 02 for the settings side)

## Implementation Guidelines

New `infra/evidence.tf` (orientative — verify resource shapes against the `hashicorp/aws ~> 6.0` provider docs at apply time):

```hcl
data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "evidence" {
  bucket = "blinka-evidence-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_public_access_block" "evidence {
  bucket = aws_s3_bucket.evidence.id
  block_public_acls = true; block_public_policy = true
  ignore_public_acls = true; restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  rule { object_ownership = "BucketOwnerEnforced" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "AES256" } }
}

# GuardDuty assumes this role to download + scan + tag objects
data "aws_iam_policy_document" "guardduty_scan_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole", "sts:SetSourceIdentity"]
    principals {
      type        = "Service"
      identifiers = ["malware-protection-plan.guardduty.amazonaws.com"] # verify exact principal in provider docs
    }
  }
}

data "aws_iam_policy_document" "guardduty_scan" {
  statement {
    effect = "Allow"
    actions = ["s3:GetObject", "s3:ListBucket", "s3:GetBucketLocation", "s3:PutObjectTagging"]
    resources = [aws_s3_bucket.evidence.arn, "${aws_s3_bucket.evidence.arn}/*"]
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

# Tagging MUST be enabled at creation, before the first upload.
resource "aws_guardduty_malware_protection_plan" "evidence" {
  role = aws_iam_role.guardduty_scan.arn
  protected_resource {
    s3_bucket { bucket_name = aws_s3_bucket.evidence.id }
  }
  actions {
    tag_resource { status = "ENABLED" }   # verify exact block schema in provider docs
  }
}

# Backend user (profile `panoptico` = IAM user Bryan-User) — S3 + Textract + tag read
data "aws_iam_policy_document" "backend_evidence" {
  statement {
    effect = "Allow"
    actions = [
      "s3:PutObject", "s3:GetObject", "s3:DeleteObject",
      "s3:GetObjectTagging", "s3:ListBucket", "s3:GetBucketLocation",
    ]
    resources = [aws_s3_bucket.evidence.arn, "${aws_s3_bucket.evidence.arn}/*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["textract:AnalyzeExpense", "textract:DetectDocumentText"]
    resources = ["*"]
  }
}
resource "aws_iam_user_policy" "backend_evidence" {
  name   = "blinka-backend-evidence"
  user   = "Bryan-User"
  policy = data.aws_iam_policy_document.backend_evidence.json
}
```

Also extend the existing S3 backend permissions if the bucket auto-create path (`ensure_bucket`) stays enabled — prefer disabling auto-create in code (module 02) since the bucket now exists via Terraform.

Apply + verify (manual, once):

```bash
cd infra && terraform apply
aws --profile panoptico s3 cp /tmp/test.pdf s3://<bucket>/test-upload.pdf
# within ~30s the object must show:
aws --profile panoptico s3api get-object-tagging --bucket <bucket> --key test-upload.pdf
# -> [{ "Key": "GuardDutyMalwareScanStatus", "Value": "NO_THREATS_FOUND" }]
```

If the tag never appears, the tagging action was not enabled correctly — fix before any backend work (see risks).

## Dependencies

- Terraform >= 1.9, provider `hashicorp/aws ~> 6.0` (already pinned in `infra/versions.tf`).
- AWS profile `panoptico` with permission to create these resources (region `us-east-1`).

## Integration Notes

- Exports `evidence_bucket_name`; the value is hand-copied into `backend/.env` exactly like the existing guardrail outputs (established repo pattern).
- GuardDuty is used in **independent mode** (no detector) — scan status comes solely from object tags; no EventBridge wiring needed.
- Textract usage is synchronous `AnalyzeExpense` only; `StartExpenseAnalysis`/SNS not required.
