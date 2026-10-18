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

output "evidence_bucket_name" {
  description = "Set as BLINKA_STORAGE__BUCKET in backend/.env."
  value       = aws_s3_bucket.evidence.id
}

output "events_http_domain" {
  description = "Set as BLINKA_REALTIME__HTTP_DOMAIN in backend/.env and NEXT_PUBLIC_APPSYNC_EVENTS_ENDPOINT=https://<value>/event in frontend/.env.local."
  value       = aws_appsync_api.events.dns["HTTP"]
}

output "events_realtime_domain" {
  description = "Realtime WebSocket domain; Amplify derives it from the HTTP endpoint."
  value       = aws_appsync_api.events.dns["REALTIME"]
}

output "api_url" {
  description = "Set as NEXT_PUBLIC_API_URL in Vercel."
  value       = "https://${local.api_host}"
}

output "dns_zone_name_servers" {
  description = "Add these as NS records for the delegated subdomain at the parent domain's DNS provider."
  value       = aws_route53_zone.main.name_servers
}

output "ecr_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  value = aws_ecs_service.backend.name
}

output "task_family" {
  value = aws_ecs_task_definition.backend.family
}

output "container_name" {
  value = local.backend_container_name
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.backend.name
}

output "ssm_prefix" {
  value = local.ssm_prefix
}

output "db_endpoint" {
  value = aws_db_instance.main.address
}

output "agent_db_endpoint" {
  value = aws_db_instance.agent.address
}

output "db_audit_bucket" {
  description = "pgaudit log copies land under pgaudit/<instance>/ in this bucket."
  value       = aws_s3_bucket.db_audit.id
}

output "jwt_secret" {
  description = "Set as BLINKA_JWT__SECRET in backend/.env so local tokens pass the realtime authorizer."
  value       = random_password.jwt_secret.result
  sensitive   = true
}
