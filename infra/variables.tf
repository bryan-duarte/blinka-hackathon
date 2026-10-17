variable "aws_profile" {
  description = "AWS CLI profile used for credentials."
  type        = string
  default     = "panoptico"
}

variable "aws_region" {
  description = "AWS region for Bedrock resources."
  type        = string
  default     = "us-east-1"
}

variable "guardrail_name" {
  description = "Name of the email input guardrail."
  type        = string
  default     = "blinka-email-input-guard"
}

variable "evidence_bucket_prefix" {
  description = "Evidence bucket name prefix; the account id is appended."
  type        = string
  default     = "blinka-evidence"
}

variable "backend_iam_user" {
  description = "IAM user behind the backend's AWS profile."
  type        = string
  default     = "Bryan-User"
}
