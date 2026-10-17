output "guardrail_id" {
  description = "Set as BLINKA_GUARDRAILS__GUARDRAIL_ID in backend/.env."
  value       = aws_bedrock_guardrail.email_input_guard.guardrail_id
}

output "guardrail_version" {
  description = "Set as BLINKA_GUARDRAILS__GUARDRAIL_VERSION in backend/.env."
  value       = aws_bedrock_guardrail_version.email_input_guard.version
}

output "guardrail_arn" {
  value = aws_bedrock_guardrail.email_input_guard.guardrail_arn
}
