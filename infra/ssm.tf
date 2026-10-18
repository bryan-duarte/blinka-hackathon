resource "random_password" "jwt_secret" {
  length  = 64
  special = false
}

resource "random_password" "kapso_webhook_secret" {
  length  = 48
  special = false
}

# Webhook handlers accept any non-empty secret, so the placeholder must be unguessable.
resource "random_password" "composio_webhook_secret_placeholder" {
  length  = 48
  special = false
}

locals {
  unassigned_placeholder = "assign_later"

  managed_params = {
    BLINKA_PRODUCT_DATABASE_URL          = { secure = true, value = "${local.db_server_url}/blinka_product?sslmode=require" }
    BLINKA_AGENT_DATABASE_URL            = { secure = true, value = "${local.agent_db_server_url}/blinka_agent?sslmode=require" }
    BLINKA_JWT__SECRET                   = { secure = true, value = random_password.jwt_secret.result }
    KAPSO_WEBHOOK_SECRET                 = { secure = true, value = random_password.kapso_webhook_secret.result }
    BLINKA_STORAGE__BUCKET               = { secure = false, value = aws_s3_bucket.evidence.id }
    BLINKA_STORAGE__REGION               = { secure = false, value = var.aws_region }
    BLINKA_TEXTRACT__REGION              = { secure = false, value = var.aws_region }
    BLINKA_GUARDRAILS__AWS_REGION        = { secure = false, value = var.aws_region }
    BLINKA_GUARDRAILS__GUARDRAIL_ID      = { secure = false, value = aws_bedrock_guardrail.email_input_guard.guardrail_id }
    BLINKA_GUARDRAILS__GUARDRAIL_VERSION = { secure = false, value = aws_bedrock_guardrail_version.email_input_guard.version }
    BLINKA_REALTIME__REGION              = { secure = false, value = var.aws_region }
    BLINKA_REALTIME__HTTP_DOMAIN         = { secure = false, value = aws_appsync_api.events.dns["HTTP"] }
    BLINKA_CORS__ALLOW_ORIGINS           = { secure = false, value = jsonencode([var.frontend_origin]) }
    BLINKA_KAPSO__WEBHOOK_URL            = { secure = false, value = "https://${local.api_host}/webhooks/whatsapp" }
    BLINKA_KAPSO__CALLBACK_URL           = { secure = false, value = "${var.frontend_origin}/inbox/whatsapp/callback" }
    BLINKA_COMPOSIO__CALLBACK_URL        = { secure = false, value = "${var.frontend_origin}/inbox/callback" }
    BLINKA_LLM__MODEL                    = { secure = false, value = var.bedrock_model_id }
    BLINKA_LLM__AWS_REGION               = { secure = false, value = var.aws_region }
    BLINKA_MEMORY__AWS_REGION            = { secure = false, value = var.aws_region }
  }

  # Seeded once; edit the value in the SSM console, then run `deploy.sh --restart`.
  operator_params = {
    COMPOSIO_API_KEY                        = { secure = true, value = local.unassigned_placeholder }
    COMPOSIO_WEBHOOK_SECRET                 = { secure = true, value = "${local.unassigned_placeholder}-${random_password.composio_webhook_secret_placeholder.result}" }
    KAPSO_API_KEY                           = { secure = true, value = local.unassigned_placeholder }
    BLINKA_COMPOSIO__GMAIL_AUTH_CONFIG_ID   = { secure = false, value = local.unassigned_placeholder }
    BLINKA_COMPOSIO__OUTLOOK_AUTH_CONFIG_ID = { secure = false, value = local.unassigned_placeholder }
    BLINKA_KAPSO__SANDBOX_PHONE_NUMBER_ID   = { secure = false, value = local.unassigned_placeholder }
    BLINKA_KAPSO__SANDBOX_DISPLAY_NUMBER    = { secure = false, value = local.unassigned_placeholder }
    BLINKA_JWT__EXPIRE_MINUTES              = { secure = false, value = "60" }
    BLINKA_GUARDRAILS__ENFORCE              = { secure = false, value = "true" }
    BLINKA_REALTIME__ENABLED                = { secure = false, value = "true" }
    BLINKA_DEMO__ENABLED                    = { secure = false, value = "true" }
    BLINKA_DEMO__EMAIL                      = { secure = false, value = "demo@blinka.dev" }
    BLINKA_DEMO__PASSWORD                   = { secure = true, value = local.unassigned_placeholder }
    BLINKA_DEMO__COMPANY_NAME               = { secure = false, value = "Andescape Labs, Inc." }
    BLINKA_STORAGE__MALWARE_SCAN_ENABLED    = { secure = false, value = "true" }
    BLINKA_FX__LIVE_ENABLED                 = { secure = false, value = "true" }
    BLINKA_LOG_FORMAT                       = { secure = false, value = "json" }
  }
}

resource "aws_ssm_parameter" "managed" {
  for_each = local.managed_params

  name  = "${local.ssm_prefix}/${each.key}"
  type  = each.value.secure ? "SecureString" : "String"
  value = each.value.value
}

resource "aws_ssm_parameter" "operator" {
  for_each = local.operator_params

  name  = "${local.ssm_prefix}/${each.key}"
  type  = each.value.secure ? "SecureString" : "String"
  value = each.value.value

  lifecycle {
    ignore_changes = [value]
  }
}

locals {
  backend_params = merge(aws_ssm_parameter.managed, aws_ssm_parameter.operator)
}

moved {
  from = aws_ssm_parameter.operator["KAPSO_WEBHOOK_SECRET"]
  to   = aws_ssm_parameter.managed["KAPSO_WEBHOOK_SECRET"]
}

moved {
  from = aws_ssm_parameter.managed["BLINKA_DEMO__PASSWORD"]
  to   = aws_ssm_parameter.operator["BLINKA_DEMO__PASSWORD"]
}

moved {
  from = aws_ssm_parameter.operator["BLINKA_LLM__MODEL"]
  to   = aws_ssm_parameter.managed["BLINKA_LLM__MODEL"]
}
