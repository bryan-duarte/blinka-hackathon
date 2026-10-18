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

variable "events_api_name" {
  description = "Name of the AppSync Events API that pushes inbox activity."
  type        = string
  default     = "blinka-events"
}

variable "domain_name" {
  description = "Route53 zone Terraform creates for the API, delegated from the parent domain's DNS (e.g. blinka.bryanjavier.com)."
  type        = string
}

variable "api_subdomain" {
  description = "API host label; the API is served at <api_subdomain>.<domain_name>."
  type        = string
  default     = "api"
}

variable "frontend_origin" {
  description = "Origin of the Vercel frontend, e.g. https://blinka-web.vercel.app, no trailing slash."
  type        = string

  validation {
    condition     = can(regex("^https://[^/]+$", var.frontend_origin))
    error_message = "frontend_origin must be an https:// origin with no path or trailing slash."
  }
}

variable "vpc_cidr" {
  description = "CIDR range of the backend VPC."
  type        = string
  default     = "10.20.0.0/16"
}
