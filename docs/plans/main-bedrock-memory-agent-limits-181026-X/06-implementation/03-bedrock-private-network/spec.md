# Bedrock Private Network + IAM + SSM

## Overview

Route all `bedrock-runtime` traffic from ECS through an interface VPC endpoint with private DNS, grant the task role model invoke rights, and move the SSM config from OpenRouter to Bedrock.

## Files to Modify/Create

- `infra/network.tf`: add `aws_security_group.vpce`, `aws_vpc_security_group_ingress_rule.vpce_https_from_app` and `aws_vpc_endpoint.bedrock_runtime`.
- `infra/compute.tf`: add `data.aws_iam_policy_document.backend_bedrock_invoke`, `aws_iam_role_policy.backend_task_bedrock_invoke` and `aws_iam_user_policy.backend_bedrock_invoke` (local-dev user `var.backend_iam_user`, mirroring `aws_iam_user_policy.backend_evidence`).
- `infra/ssm.tf`:
  - Remove `OPENROUTER_API_KEY`, `BLINKA_LLM__MAIN_MODEL` and `BLINKA_LLM__PAYMENTS_MODEL` from `operator_params`.
  - Move `BLINKA_LLM__MODEL` to `managed_params` with value `var.bedrock_model_id`.
  - Add managed `BLINKA_LLM__AWS_REGION = var.aws_region` and `BLINKA_MEMORY__AWS_REGION = var.aws_region`.
- `infra/variables.tf`: add `variable "bedrock_model_id" { default = "global.anthropic.claude-haiku-5-5" }` and `variable "bedrock_embedding_model_id" { default = "amazon.titan-embed-text-v2:0" }`.

## Implementation Guidelines

```hcl
# orientative — network.tf
resource "aws_security_group" "vpce" {
  name        = "${local.name}-vpce"
  description = "Interface VPC endpoints, reachable only from backend tasks"
  vpc_id      = aws_vpc.main.id
}

resource "aws_vpc_security_group_ingress_rule" "vpce_https_from_app" {
  security_group_id            = aws_security_group.vpce.id
  referenced_security_group_id = aws_security_group.app.id
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
}

resource "aws_vpc_endpoint" "bedrock_runtime" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.app[*].id
  security_group_ids  = [aws_security_group.vpce.id]
  private_dns_enabled = true
  tags                = { Name = "${local.name}-bedrock-runtime" }
}
```
- The VPC already has `enable_dns_support` and `enable_dns_hostnames` set to true, which private DNS needs.
- The app SG already allows all egress, so no change is needed there.
- Keep the default endpoint policy (full access). IAM is the control point.
- The NAT stays.

```hcl
# orientative — compute.tf
data "aws_iam_policy_document" "backend_bedrock_invoke" {
  statement {
    sid       = "InvokeClaudeProfiles"
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = [
      "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/*anthropic.claude-haiku-5-5*",
    ]
  }
  statement {
    sid       = "InvokeClaudeViaProfile"
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = ["arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku-5-5*"]
    condition {
      test     = "StringLike"
      variable = "bedrock:InferenceProfileArn"
      values   = ["arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/*anthropic.claude-haiku-5-5*"]
    }
  }
  statement {
    sid       = "EmbedMemories"
    actions   = ["bedrock:InvokeModel"]
    resources = ["arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_embedding_model_id}"]
  }
}
```
- Global CRIS foundation-model ARNs may be region-less (`arn:aws:bedrock:::foundation-model/...`). The `arn:aws:bedrock:*::` wildcard covers both forms. If AccessDenied appears, check CloudTrail for the exact resource ARN and tighten the policy from there.
- Attach the policy to `aws_iam_role.backend_task` and to `var.backend_iam_user`, following the existing `backend_task_guardrail` and `backend_evidence` patterns.

```hcl
# orientative — ssm.tf
managed_params = {
  ...
  BLINKA_LLM__MODEL         = { secure = false, value = var.bedrock_model_id }
  BLINKA_LLM__AWS_REGION    = { secure = false, value = var.aws_region }
  BLINKA_MEMORY__AWS_REGION = { secure = false, value = var.aws_region }
}
moved {
  from = aws_ssm_parameter.operator["BLINKA_LLM__MODEL"]
  to   = aws_ssm_parameter.managed["BLINKA_LLM__MODEL"]
}
```
- Removing `operator["OPENROUTER_API_KEY"]`, `["BLINKA_LLM__MAIN_MODEL"]` and `["BLINKA_LLM__PAYMENTS_MODEL"]` destroys those parameters. That is intended: stale OpenRouter IDs must not override the Bedrock default.
- The `BLINKA_AGENT__*` and `BLINKA_MEMORY__*` tunables keep their code defaults. Don't add SSM params unless an override is needed.

**Rollout order:**
1. `terraform apply` (endpoint, IAM, SSM).
2. `infra/deploy.sh` (new image plus task def).
3. Smoke test through ECS Exec: `aws bedrock-runtime converse --model-id global.anthropic.claude-haiku-5-5 --messages '[{"role":"user","content":[{"text":"ping"}]}]'`.
4. Check that the CloudWatch `AWS/PrivateLinkEndpoints` BytesProcessed metric for the endpoint is greater than 0.
5. Revoke the OpenRouter key.

## Dependencies

- Module 02 (the code reads `BLINKA_LLM__AWS_REGION` and the new model ID).

## Integration Notes

- Private DNS makes the existing `BedrockGuardrailBackend` (`apply_guardrail`) traffic private with no code change.
- `BedrockEmbeddings` (module 05) uses the same endpoint and the `EmbedMemories` statement.
- Local dev is not affected by the endpoint. It uses the public regional endpoint with the `panoptico` profile and needs the user policy.
