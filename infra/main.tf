locals {
  blocked_message = "Este correo fue bloqueado por las políticas de seguridad. / Blocked by policy."
  moderated_types = ["HATE", "INSULTS", "SEXUAL", "VIOLENCE", "MISCONDUCT"]

  # Standard tier requires cross-Region inference; us.guardrail.v1:0 routes
  # us-east-1 calls within the US geographic boundary.
  guardrail_profile_arn = "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:guardrail-profile/us.guardrail.v1:0"
}

data "aws_caller_identity" "current" {}

resource "aws_bedrock_guardrail" "email_input_guard" {
  name                      = var.guardrail_name
  description               = "Screens untrusted email text before any Blinka agent reads it."
  blocked_input_messaging   = local.blocked_message
  blocked_outputs_messaging = local.blocked_message

  content_policy_config {
    tier_config {
      tier_name = "STANDARD"
    }

    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE"
      input_action    = "BLOCK"
      input_enabled   = true
    }

    dynamic "filters_config" {
      for_each = local.moderated_types
      content {
        type            = filters_config.value
        input_strength  = "MEDIUM"
        output_strength = "NONE"
      }
    }
  }

  cross_region_config {
    guardrail_profile_identifier = local.guardrail_profile_arn
  }
}

resource "aws_bedrock_guardrail_version" "email_input_guard" {
  guardrail_arn = aws_bedrock_guardrail.email_input_guard.guardrail_arn
  description   = "email input guard"
}
