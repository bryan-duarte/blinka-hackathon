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
